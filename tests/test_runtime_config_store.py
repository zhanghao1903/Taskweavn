from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from taskweavn.runtime_config import (
    RuntimeConfigActor,
    RuntimeConfigChange,
    RuntimeConfigChangeStoreError,
    RuntimeConfigRejection,
    RuntimeConfigScope,
    RuntimeConfigSnapshotRecord,
    SqliteRuntimeConfigChangeStore,
    resolve_default_runtime_config,
)


def test_sqlite_runtime_config_change_store_round_trips_accepted_change_and_snapshot(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="workspace-1")
    base_config = resolve_default_runtime_config(scope=scope)
    change = RuntimeConfigChange(
        change_id="change-accepted",
        patch_id="patch-accepted",
        idempotency_key="idem-accepted",
        scope=scope,
        actor=_actor(),
        reason="test accepted change",
        status="accepted",
        requested_values={"agent_loop.default_max_steps": 8},
        accepted_values={"agent_loop.default_max_steps": 8},
        base_config_hash=base_config.config_hash,
        resulting_config_hash="candidate-hash",
        effective_status_by_key={
            "agent_loop.default_max_steps": "pending_next_agent_run"
        },
        created_at=_ts(0),
    )
    snapshot = RuntimeConfigSnapshotRecord(
        snapshot_id="snapshot-accepted",
        config_hash=base_config.config_hash,
        scope=scope,
        effective_config=base_config,
        created_by_change_id=change.change_id,
        created_at=_ts(1),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        assert store.append_change(change) == change
        assert store.save_snapshot(snapshot) == snapshot

        assert store.get_change(change.change_id) == change
        assert (
            store.get_change_by_idempotency_key("idem-accepted", scope) == change
        )
        stored_snapshot = store.get_snapshot(base_config.config_hash)
        assert stored_snapshot is not None
        assert stored_snapshot.snapshot_id == snapshot.snapshot_id
        assert stored_snapshot.config_hash == snapshot.config_hash
        assert stored_snapshot.scope == snapshot.scope
        assert stored_snapshot.created_by_change_id == snapshot.created_by_change_id
        assert stored_snapshot.created_at == snapshot.created_at
        assert stored_snapshot.effective_config.config_hash == base_config.config_hash
        assert stored_snapshot.effective_config.scope == base_config.scope
        assert store.list_changes(scope) == (change,)


def test_sqlite_runtime_config_change_store_round_trips_rejected_and_no_op_changes(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="session", workspace_id="w1", session_id="s1")
    base_config = resolve_default_runtime_config(scope=scope)
    rejected = RuntimeConfigChange(
        change_id="change-rejected",
        patch_id="patch-rejected",
        idempotency_key="idem-rejected",
        scope=scope,
        actor=_actor(),
        reason="test rejected change",
        status="rejected",
        requested_values={"unknown.key": "value"},
        rejected_values={
            "unknown.key": RuntimeConfigRejection(
                code="unknown_key",
                message="unknown runtime config key",
                details={"key": "unknown.key"},
            )
        },
        base_config_hash=base_config.config_hash,
        created_at=_ts(0),
    )
    no_op = RuntimeConfigChange(
        change_id="change-no-op",
        patch_id="patch-no-op",
        idempotency_key="idem-no-op",
        scope=scope,
        actor=_actor(),
        reason="test no-op change",
        status="no_op",
        requested_values={"agent_loop.default_max_steps": 20},
        base_config_hash=base_config.config_hash,
        resulting_config_hash=base_config.config_hash,
        created_at=_ts(1),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        store.append_change(no_op)
        store.append_change(rejected)

        assert store.get_change(rejected.change_id) == rejected
        assert store.get_change(no_op.change_id) == no_op
        assert store.list_changes(scope) == (rejected, no_op)


def test_sqlite_runtime_config_change_store_idempotency_lookup_is_scope_bound(
    tmp_path: Path,
) -> None:
    workspace_scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    session_scope = RuntimeConfigScope(
        level="session",
        workspace_id="w1",
        session_id="s1",
    )
    workspace_config = resolve_default_runtime_config(scope=workspace_scope)
    session_config = resolve_default_runtime_config(scope=session_scope)
    workspace_change = RuntimeConfigChange(
        change_id="change-workspace",
        patch_id="patch-workspace",
        idempotency_key="same-key",
        scope=workspace_scope,
        actor=_actor(),
        status="accepted",
        requested_values={"agent_loop.default_max_steps": 9},
        accepted_values={"agent_loop.default_max_steps": 9},
        base_config_hash=workspace_config.config_hash,
        resulting_config_hash="workspace-result",
        effective_status_by_key={
            "agent_loop.default_max_steps": "pending_next_agent_run"
        },
        created_at=_ts(0),
    )
    session_change = RuntimeConfigChange(
        change_id="change-session",
        patch_id="patch-session",
        idempotency_key="same-key",
        scope=session_scope,
        actor=_actor(),
        status="accepted",
        requested_values={"agent_loop.default_max_steps": 10},
        accepted_values={"agent_loop.default_max_steps": 10},
        base_config_hash=session_config.config_hash,
        resulting_config_hash="session-result",
        effective_status_by_key={
            "agent_loop.default_max_steps": "pending_next_agent_run"
        },
        created_at=_ts(1),
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        store.append_change(workspace_change)
        store.append_change(session_change)

        assert (
            store.get_change_by_idempotency_key("same-key", workspace_scope)
            == workspace_change
        )
        assert (
            store.get_change_by_idempotency_key("same-key", session_scope)
            == session_change
        )
        assert (
            store.get_change_by_idempotency_key(
                "missing",
                workspace_scope,
            )
            is None
        )


def test_sqlite_runtime_config_change_store_rejects_duplicate_idempotency_in_scope(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="w1")
    base_config = resolve_default_runtime_config(scope=scope)
    first = RuntimeConfigChange(
        change_id="change-1",
        patch_id="patch-1",
        idempotency_key="duplicate-key",
        scope=scope,
        actor=_actor(),
        status="accepted",
        requested_values={"agent_loop.default_max_steps": 11},
        accepted_values={"agent_loop.default_max_steps": 11},
        base_config_hash=base_config.config_hash,
        resulting_config_hash="result-1",
        effective_status_by_key={
            "agent_loop.default_max_steps": "pending_next_agent_run"
        },
        created_at=_ts(0),
    )
    second = first.model_copy(
        update={
            "change_id": "change-2",
            "patch_id": "patch-2",
            "requested_values": {"agent_loop.default_max_steps": 12},
            "accepted_values": {"agent_loop.default_max_steps": 12},
            "resulting_config_hash": "result-2",
            "created_at": _ts(1),
        }
    )

    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        store.append_change(first)
        with pytest.raises(RuntimeConfigChangeStoreError, match="idempotency"):
            store.append_change(second)


def test_sqlite_runtime_config_change_store_connection_closes(tmp_path: Path) -> None:
    store = SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db")
    store.close()

    with pytest.raises(sqlite3.ProgrammingError):
        store.get_change("change-id")


def _actor() -> RuntimeConfigActor:
    return RuntimeConfigActor(
        actor_type="test",
        actor_id="test-suite",
        display_name="Runtime config tests",
    )


def _ts(offset_seconds: int) -> datetime:
    return datetime(2026, 6, 24, 12, 0, tzinfo=UTC) + timedelta(
        seconds=offset_seconds
    )
