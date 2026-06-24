from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from taskweavn.runtime_config import (
    DefaultRuntimeConfigMutationService,
    RuntimeConfigActor,
    RuntimeConfigMutationServiceConfig,
    RuntimeConfigPatch,
    RuntimeConfigScope,
    SqliteRuntimeConfigChangeStore,
)
from taskweavn.server.runtime_config_gateway import DefaultRuntimeConfigGateway


def test_runtime_config_gateway_queries_change_store(tmp_path: Path) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    patch = RuntimeConfigPatch(
        patch_id="patch-accepted",
        idempotency_key="idem-accepted",
        scope=scope,
        actor=_actor(),
        values={"agent_loop.default_max_steps": 8},
        requested_at=_ts(),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )
        change = service.apply_patch(patch)
        gateway = DefaultRuntimeConfigGateway.from_process_inputs(
            {},
            workspace_id="w1",
            change_store=store,
        )

        assert gateway.get_change(change.change_id) == change
        assert (
            gateway.get_change_by_idempotency_key(
                "idem-accepted",
                RuntimeConfigScope(),
            )
            == change
        )
        assert gateway.list_changes(RuntimeConfigScope()) == (change,)
        snapshot = gateway.get_snapshot(change.resulting_config_hash or "")
        assert snapshot is not None
        assert snapshot.created_by_change_id == change.change_id


def test_runtime_config_gateway_without_store_returns_empty_change_queries() -> None:
    gateway = DefaultRuntimeConfigGateway.from_process_inputs({}, workspace_id="w1")

    assert gateway.get_change("missing") is None
    assert gateway.get_change_by_idempotency_key("missing", RuntimeConfigScope()) is None
    assert gateway.get_snapshot("missing") is None
    assert gateway.list_changes(RuntimeConfigScope()) == ()


def _actor() -> RuntimeConfigActor:
    return RuntimeConfigActor(
        actor_type="test",
        actor_id="test-suite",
        display_name="Runtime config gateway tests",
    )


def _ts() -> datetime:
    return datetime(2026, 6, 24, 14, 0, tzinfo=UTC)
