from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from taskweavn.runtime_config import (
    DefaultRuntimeConfigMutationService,
    InMemoryRuntimeConfigBus,
    RuntimeConfigActor,
    RuntimeConfigBusConsumerResult,
    RuntimeConfigBusEvent,
    RuntimeConfigChange,
    RuntimeConfigMutationServiceConfig,
    RuntimeConfigPatch,
    RuntimeConfigScope,
    SqliteRuntimeConfigChangeStore,
    runtime_config_bus_event_from_change,
)


def test_runtime_config_bus_event_splits_active_and_pending_values(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    patch = RuntimeConfigPatch(
        patch_id="patch-mixed",
        scope=scope,
        actor=_actor(),
        values={
            "logging.level": "DEBUG",
            "agent_loop.default_max_steps": 8,
        },
        requested_at=_ts(),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )

        change = service.apply_patch(patch)

    event = runtime_config_bus_event_from_change(change)

    assert event.event_type == "runtime_config.changed"
    assert event.change_id == change.change_id
    assert event.accepted_values == {
        "logging.level": "DEBUG",
        "agent_loop.default_max_steps": 8,
    }
    assert event.active_values == {"logging.level": "DEBUG"}
    assert event.pending_values == {"agent_loop.default_max_steps": 8}
    assert event.effective_status_by_key == {
        "logging.level": "active",
        "agent_loop.default_max_steps": "pending_next_agent_run",
    }


def test_in_memory_runtime_config_bus_records_consumer_results(
    tmp_path: Path,
) -> None:
    bus = InMemoryRuntimeConfigBus()
    seen_events = []

    def handler(event: RuntimeConfigBusEvent) -> RuntimeConfigBusConsumerResult:
        seen_events.append(event)
        return RuntimeConfigBusConsumerResult(
            consumer_id="logging-consumer",
            status="applied",
            applied_keys=tuple(event.active_values),
            skipped_keys=tuple(event.pending_values),
        )

    bus.subscribe("logging-consumer", handler)
    change = _accepted_change(
        tmp_path,
        values={
            "logging.level": "DEBUG",
            "agent_loop.default_max_steps": 8,
        },
    )

    publication = bus.publish_change(change)

    assert publication is not None
    assert len(seen_events) == 1
    assert publication.event.change_id == change.change_id
    assert publication.consumer_results == (
        RuntimeConfigBusConsumerResult(
            consumer_id="logging-consumer",
            status="applied",
            applied_keys=("logging.level",),
            skipped_keys=("agent_loop.default_max_steps",),
        ),
    )
    assert bus.publications == (publication,)


def test_in_memory_runtime_config_bus_captures_consumer_failure(
    tmp_path: Path,
) -> None:
    bus = InMemoryRuntimeConfigBus()

    def broken_handler(_event: RuntimeConfigBusEvent) -> RuntimeConfigBusConsumerResult:
        raise RuntimeError("consumer failed")

    bus.subscribe("broken-consumer", broken_handler)
    change = _accepted_change(tmp_path, values={"logging.level": "DEBUG"})

    publication = bus.publish_change(change)

    assert publication is not None
    assert publication.consumer_results[0].consumer_id == "broken-consumer"
    assert publication.consumer_results[0].status == "failed"
    assert publication.consumer_results[0].skipped_keys == ("logging.level",)
    assert publication.consumer_results[0].error_type == "RuntimeError"
    assert publication.consumer_results[0].message == "consumer failed"


def test_in_memory_runtime_config_bus_captures_mismatched_consumer_result(
    tmp_path: Path,
) -> None:
    bus = InMemoryRuntimeConfigBus()

    def mismatched_handler(
        _event: RuntimeConfigBusEvent,
    ) -> RuntimeConfigBusConsumerResult:
        return RuntimeConfigBusConsumerResult(
            consumer_id="different-consumer",
            status="applied",
            applied_keys=("logging.level",),
        )

    bus.subscribe("logging-consumer", mismatched_handler)
    change = _accepted_change(tmp_path, values={"logging.level": "DEBUG"})

    publication = bus.publish_change(change)

    assert publication is not None
    assert publication.consumer_results == (
        RuntimeConfigBusConsumerResult(
            consumer_id="logging-consumer",
            status="failed",
            skipped_keys=("logging.level",),
            message="Consumer result ID must match subscription consumer_id.",
            error_type="RuntimeConfigBusError",
        ),
    )


def test_mutation_service_publishes_only_accepted_non_dry_run_changes(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    bus = InMemoryRuntimeConfigBus()

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store, config_bus=bus)
        )

        accepted = service.apply_patch(
            RuntimeConfigPatch(
                patch_id="patch-accepted",
                idempotency_key="idem-accepted",
                scope=scope,
                actor=_actor(),
                values={"logging.level": "DEBUG"},
                requested_at=_ts(),
            )
        )
        replayed = service.apply_patch(
            RuntimeConfigPatch(
                patch_id="patch-replayed",
                idempotency_key="idem-accepted",
                scope=scope,
                actor=_actor(),
                values={"logging.level": "ERROR"},
                requested_at=_ts(),
            )
        )
        no_op = service.apply_patch(
            RuntimeConfigPatch(
                patch_id="patch-no-op",
                scope=scope,
                actor=_actor(),
                values={"agent_loop.default_max_steps": 20},
                requested_at=_ts(),
            )
        )
        rejected = service.apply_patch(
            RuntimeConfigPatch(
                patch_id="patch-rejected",
                scope=scope,
                actor=_actor(),
                values={"unknown.key": "value"},
                requested_at=_ts(),
            )
        )
        dry_run = service.apply_patch(
            RuntimeConfigPatch(
                patch_id="patch-dry-run",
                scope=scope,
                actor=_actor(),
                values={"logging.level": "WARNING"},
                dry_run=True,
                requested_at=_ts(),
            )
        )

    assert accepted.status == "accepted"
    assert replayed == accepted
    assert no_op.status == "no_op"
    assert rejected.status == "rejected"
    assert dry_run.status == "accepted"
    assert len(bus.publications) == 1
    assert bus.publications[0].event.change_id == accepted.change_id
    assert bus.publications[0].event.active_values == {"logging.level": "DEBUG"}


def _accepted_change(
    tmp_path: Path,
    *,
    values: dict[str, object],
) -> RuntimeConfigChange:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    patch = RuntimeConfigPatch(
        patch_id=f"patch-{len(values)}",
        scope=scope,
        actor=_actor(),
        values=values,
        requested_at=_ts(),
    )
    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )
        return service.apply_patch(patch)


def _actor() -> RuntimeConfigActor:
    return RuntimeConfigActor(
        actor_type="test",
        actor_id="test-suite",
        display_name="Runtime config ConfigBus tests",
    )


def _ts() -> datetime:
    return datetime(2026, 6, 24, 14, 0, tzinfo=UTC)
