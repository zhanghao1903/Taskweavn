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
)
from taskweavn.server.runtime_config_diagnostics import (
    DefaultRuntimeConfigDiagnosticsGateway,
)
from taskweavn.server.runtime_config_gateway import DefaultRuntimeConfigGateway


def test_runtime_config_diagnostics_gateway_combines_read_only_facts(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
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
    patch = RuntimeConfigPatch(
        patch_id="patch-runtime-diagnostics",
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
            RuntimeConfigMutationServiceConfig(store=store, config_bus=bus)
        )
        change = service.apply_patch(patch)
        gateway = DefaultRuntimeConfigGateway.from_process_inputs(
            {},
            workspace_id="w1",
            change_store=store,
        )
        diagnostics = DefaultRuntimeConfigDiagnosticsGateway(
            runtime_config_gateway=gateway,
            config_bus_publications=bus.publications,
        ).snapshot(
            RuntimeConfigScope(),
            explain_keys=("logging.level",),
            snapshot_hashes=(change.resulting_config_hash or "", "missing-hash"),
        )

    assert diagnostics.schema_version == "plato.runtime_config_diagnostics.v1"
    assert diagnostics.scope == RuntimeConfigScope()
    assert diagnostics.effective_config.scope == scope
    assert diagnostics.explained_values["logging.level"].key == "logging.level"
    assert diagnostics.changes == (change,)
    assert len(diagnostics.snapshot_records) == 1
    assert diagnostics.snapshot_records[0].config_hash == change.resulting_config_hash
    assert diagnostics.missing_snapshot_hashes == ("missing-hash",)
    assert diagnostics.config_bus.total_publication_count == 1
    assert diagnostics.config_bus.publications[0].change_id == change.change_id
    assert diagnostics.config_bus.publications[0].active_keys == ("logging.level",)
    assert diagnostics.config_bus.publications[0].pending_keys == (
        "agent_loop.default_max_steps",
    )


def test_runtime_config_diagnostics_gateway_handles_empty_store(
    tmp_path: Path,
) -> None:
    gateway = DefaultRuntimeConfigGateway.from_process_inputs({}, workspace_id="w1")
    diagnostics = DefaultRuntimeConfigDiagnosticsGateway(
        runtime_config_gateway=gateway,
        config_bus_publications=(),
    ).snapshot(
        RuntimeConfigScope(),
        explain_keys=("agent_loop.default_max_steps",),
        snapshot_hashes=("missing-hash",),
    )

    assert diagnostics.changes == ()
    assert diagnostics.snapshot_records == ()
    assert diagnostics.missing_snapshot_hashes == ("missing-hash",)
    assert diagnostics.config_bus.total_publication_count == 0
    assert (
        diagnostics.explained_values["agent_loop.default_max_steps"].key
        == "agent_loop.default_max_steps"
    )


def _actor() -> RuntimeConfigActor:
    return RuntimeConfigActor(
        actor_type="test",
        actor_id="test-suite",
        display_name="Runtime config diagnostics gateway tests",
    )


def _ts() -> datetime:
    return datetime(2026, 6, 24, 17, 0, tzinfo=UTC)
