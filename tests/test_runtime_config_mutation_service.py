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
    resolve_default_runtime_config,
)


def test_runtime_config_mutation_service_accepts_and_persists_patch(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    patch = RuntimeConfigPatch(
        patch_id="patch-accepted",
        idempotency_key="idem-accepted",
        scope=scope,
        actor=_actor(),
        reason="lower max steps",
        values={"agent_loop.default_max_steps": 8},
        requested_at=_ts(),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )

        change = service.apply_patch(patch)

        assert change.status == "accepted"
        assert change.accepted_values == {"agent_loop.default_max_steps": 8}
        assert change.effective_status_by_key == {
            "agent_loop.default_max_steps": "pending_next_agent_run"
        }
        assert store.get_change(change.change_id) == change
        snapshot = store.get_snapshot(change.resulting_config_hash or "")
        assert snapshot is not None
        assert snapshot.created_by_change_id == change.change_id
        assert snapshot.effective_config.values["agent_loop.default_max_steps"].value == 8


def test_runtime_config_mutation_service_records_no_op_patch(tmp_path: Path) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    base_config = resolve_default_runtime_config(scope=scope)
    patch = RuntimeConfigPatch(
        patch_id="patch-no-op",
        idempotency_key="idem-no-op",
        scope=scope,
        actor=_actor(),
        values={"agent_loop.default_max_steps": 20},
        requested_at=_ts(),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )

        change = service.apply_patch(patch)

        assert change.status == "no_op"
        assert change.accepted_values == {}
        assert change.rejected_values == {}
        assert change.resulting_config_hash == base_config.config_hash
        assert store.get_change(change.change_id) == change
        assert store.get_snapshot(base_config.config_hash) is not None


def test_runtime_config_mutation_service_records_rejections(tmp_path: Path) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    patch = RuntimeConfigPatch(
        patch_id="patch-rejected",
        idempotency_key="idem-rejected",
        scope=scope,
        actor=_actor(),
        values={
            "unknown.key": "value",
            "agent_loop.default_max_steps": True,
        },
        requested_at=_ts(),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )

        change = service.apply_patch(patch)

        assert change.status == "rejected"
        assert change.accepted_values == {}
        assert change.resulting_config_hash is None
        assert change.rejected_values["unknown.key"].code == "unknown_key"
        assert (
            change.rejected_values["agent_loop.default_max_steps"].code
            == "invalid_value"
        )
        assert store.get_change(change.change_id) == change
        assert store.get_snapshot(change.base_config_hash) is None


def test_runtime_config_mutation_service_records_partial_acceptance(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    patch = RuntimeConfigPatch(
        patch_id="patch-partial",
        scope=scope,
        actor=_actor(),
        values={
            "logging.level": "DEBUG",
            "unknown.key": "value",
        },
        requested_at=_ts(),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )

        change = service.apply_patch(patch)

        assert change.status == "accepted"
        assert change.accepted_values == {"logging.level": "DEBUG"}
        assert change.rejected_values["unknown.key"].code == "unknown_key"
        assert change.effective_status_by_key == {"logging.level": "active"}
        assert store.get_change(change.change_id) == change


def test_runtime_config_mutation_service_can_disable_partial_acceptance(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    patch = RuntimeConfigPatch(
        patch_id="patch-no-partial",
        scope=scope,
        actor=_actor(),
        values={
            "logging.level": "DEBUG",
            "unknown.key": "value",
        },
        allow_partial_acceptance=False,
        requested_at=_ts(),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )

        change = service.apply_patch(patch)

        assert change.status == "rejected"
        assert change.accepted_values == {}
        assert change.rejected_values["unknown.key"].code == "unknown_key"
        assert change.rejected_values["logging.level"].code == "policy_denied"
        assert store.get_change(change.change_id) == change


def test_runtime_config_mutation_service_rejects_stale_base_hash(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    patch = RuntimeConfigPatch(
        patch_id="patch-stale",
        scope=scope,
        actor=_actor(),
        values={"logging.level": "DEBUG"},
        expected_base_config_hash="stale-hash",
        requested_at=_ts(),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )

        change = service.apply_patch(patch)

        assert change.status == "rejected"
        assert change.rejected_values["logging.level"].code == "stale_base_config"
        assert store.get_change(change.change_id) == change


def test_runtime_config_mutation_service_replays_idempotency_key(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    first_patch = RuntimeConfigPatch(
        patch_id="patch-first",
        idempotency_key="same-key",
        scope=scope,
        actor=_actor(),
        values={"agent_loop.default_max_steps": 8},
        requested_at=_ts(),
    )
    replay_patch = RuntimeConfigPatch(
        patch_id="patch-replay",
        idempotency_key="same-key",
        scope=scope,
        actor=_actor(),
        values={"agent_loop.default_max_steps": 12},
        requested_at=_ts(),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )

        first_change = service.apply_patch(first_patch)
        replayed_change = service.apply_patch(replay_patch)

        assert replayed_change == first_change
        assert store.list_changes(scope) == (first_change,)


def test_runtime_config_mutation_service_dry_run_does_not_persist(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    patch = RuntimeConfigPatch(
        patch_id="patch-dry-run",
        scope=scope,
        actor=_actor(),
        values={"logging.level": "DEBUG"},
        dry_run=True,
        requested_at=_ts(),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )

        change = service.apply_patch(patch)

        assert change.status == "accepted"
        assert store.get_change(change.change_id) is None
        assert store.list_changes(scope) == ()


def test_runtime_config_mutation_service_rejects_process_scope_patch(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="process")
    patch = RuntimeConfigPatch(
        patch_id="patch-process",
        scope=scope,
        actor=_actor(),
        values={"computer_use.backend": "macos"},
        requested_at=_ts(),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )

        change = service.apply_patch(patch)

        assert change.status == "rejected"
        assert change.rejected_values["computer_use.backend"].code == "unsupported_scope"
        assert store.get_change(change.change_id) == change


def _actor() -> RuntimeConfigActor:
    return RuntimeConfigActor(
        actor_type="test",
        actor_id="test-suite",
        display_name="Runtime config mutation tests",
    )


def _ts() -> datetime:
    return datetime(2026, 6, 24, 13, 0, tzinfo=UTC)
