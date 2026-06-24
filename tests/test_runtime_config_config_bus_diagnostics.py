from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from taskweavn.runtime_config import (
    DefaultRuntimeConfigMutationService,
    InMemoryRuntimeConfigBus,
    RuntimeConfigActor,
    RuntimeConfigBusConsumerResult,
    RuntimeConfigMutationServiceConfig,
    RuntimeConfigPatch,
    RuntimeConfigScope,
    SqliteRuntimeConfigChangeStore,
    runtime_config_bus_diagnostics_snapshot,
)


def test_runtime_config_bus_diagnostics_snapshot_summarizes_publications(
    tmp_path: Path,
) -> None:
    bus = InMemoryRuntimeConfigBus()
    bus.subscribe(
        "diagnostic-consumer",
        lambda event: RuntimeConfigBusConsumerResult(
            consumer_id="diagnostic-consumer",
            status="applied",
            applied_keys=tuple(event.active_values),
            skipped_keys=tuple(event.pending_values),
        ),
    )
    _publish_change(
        tmp_path,
        bus=bus,
        patch_id="patch-1",
        values={
            "logging.level": "DEBUG",
            "agent_loop.default_max_steps": 8,
        },
    )

    snapshot = runtime_config_bus_diagnostics_snapshot(bus.publications)

    assert snapshot.schema_version == "plato.runtime_config_configbus_diagnostics.v1"
    assert snapshot.total_publication_count == 1
    assert len(snapshot.publications) == 1
    publication = snapshot.publications[0]
    assert publication.patch_id == "patch-1"
    assert publication.accepted_keys == (
        "logging.level",
        "agent_loop.default_max_steps",
    )
    assert publication.active_keys == ("logging.level",)
    assert publication.pending_keys == ("agent_loop.default_max_steps",)
    assert publication.consumer_results == (
        RuntimeConfigBusConsumerResult(
            consumer_id="diagnostic-consumer",
            status="applied",
            applied_keys=("logging.level",),
            skipped_keys=("agent_loop.default_max_steps",),
        ),
    )


def test_runtime_config_bus_diagnostics_snapshot_limits_recent_publications(
    tmp_path: Path,
) -> None:
    bus = InMemoryRuntimeConfigBus()
    _publish_change(
        tmp_path,
        bus=bus,
        patch_id="patch-1",
        values={"logging.level": "DEBUG"},
    )
    _publish_change(
        tmp_path,
        bus=bus,
        patch_id="patch-2",
        values={"logging.level": "WARNING"},
    )

    snapshot = runtime_config_bus_diagnostics_snapshot(bus.publications, limit=1)

    assert snapshot.total_publication_count == 2
    assert tuple(publication.patch_id for publication in snapshot.publications) == (
        "patch-2",
    )


def test_runtime_config_bus_diagnostics_snapshot_rejects_negative_limit() -> None:
    try:
        runtime_config_bus_diagnostics_snapshot((), limit=-1)
    except ValueError as exc:
        assert str(exc) == "limit must be >= 0"
    else:  # pragma: no cover - assertion guard
        raise AssertionError("negative diagnostics limit should fail")


def _publish_change(
    tmp_path: Path,
    *,
    bus: InMemoryRuntimeConfigBus,
    patch_id: str,
    values: dict[str, object],
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    patch = RuntimeConfigPatch(
        patch_id=patch_id,
        scope=scope,
        actor=_actor(),
        values=values,
        requested_at=_ts(),
    )
    with SqliteRuntimeConfigChangeStore(tmp_path / f"{patch_id}.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store, config_bus=bus)
        )
        service.apply_patch(patch)


def _actor() -> RuntimeConfigActor:
    return RuntimeConfigActor(
        actor_type="test",
        actor_id="test-suite",
        display_name="Runtime config ConfigBus diagnostics tests",
    )


def _ts() -> datetime:
    return datetime(2026, 6, 24, 16, 0, tzinfo=UTC)
