"""Tests for durable WeChat send-boundary idempotency."""

from __future__ import annotations

from pathlib import Path

import pytest

from taskweavn.execution_plane import (
    SqliteWeChatSendBoundaryStore,
    WeChatSendBoundary,
    WeChatSendBoundaryConflictError,
    WeChatSendBoundaryStore,
    WeChatSendBoundaryTransitionError,
)


def test_sqlite_wechat_send_boundary_store_satisfies_protocol(tmp_path: Path) -> None:
    store = SqliteWeChatSendBoundaryStore(tmp_path / "wechat-send.sqlite")
    try:
        assert isinstance(store, WeChatSendBoundaryStore)
    finally:
        store.close()


def test_boundary_round_trip_and_restart_recovery(tmp_path: Path) -> None:
    db = tmp_path / "wechat-send.sqlite"
    first = SqliteWeChatSendBoundaryStore(db)
    boundary = _boundary()
    try:
        stored = first.put(boundary)
        drafted = first.transition(
            stored.execution_id,
            "drafted",
            draft_observation_ref="observe:draft-1",
        )
        requested = first.transition(
            stored.execution_id,
            "confirmation_requested",
            confirmation_id="confirmation-1",
        )
        assert drafted.draft_observation_ref == "observe:draft-1"
        assert requested.can_recover_to_confirmation is True
        assert requested.confirmation_id == "confirmation-1"
    finally:
        first.close()

    second = SqliteWeChatSendBoundaryStore(db)
    try:
        recovered = second.get(boundary.execution_id)
        assert recovered is not None
        assert recovered.status == "confirmation_requested"
        assert recovered.can_recover_to_confirmation is True
        assert recovered.draft_observation_ref == "observe:draft-1"
        assert recovered.confirmation_id == "confirmation-1"
    finally:
        second.close()


def test_duplicate_idempotency_key_same_identity_returns_existing(
    tmp_path: Path,
) -> None:
    store = SqliteWeChatSendBoundaryStore(tmp_path / "wechat-send.sqlite")
    boundary = _boundary()
    try:
        first = store.put(boundary)
        store.transition(first.execution_id, "drafted")
        store.transition(first.execution_id, "confirmation_requested")
        store.transition(first.execution_id, "confirmed")
        store.transition(first.execution_id, "send_attempted")
        sent = store.transition(
            first.execution_id,
            "sent",
            result_ref="result:wechat-send-1",
        )
        duplicate = store.put(boundary)
        assert duplicate.status == "sent"
        assert duplicate.result_ref == sent.result_ref
        assert duplicate.execution_id == first.execution_id
    finally:
        store.close()


def test_duplicate_idempotency_key_different_payload_raises_conflict(
    tmp_path: Path,
) -> None:
    store = SqliteWeChatSendBoundaryStore(tmp_path / "wechat-send.sqlite")
    try:
        store.put(_boundary(idempotency_key="idem-1", action_fingerprint="fp-1"))
        with pytest.raises(WeChatSendBoundaryConflictError):
            store.put(_boundary(idempotency_key="idem-1", action_fingerprint="fp-2"))
    finally:
        store.close()


def test_duplicate_action_fingerprint_different_key_raises_conflict(
    tmp_path: Path,
) -> None:
    store = SqliteWeChatSendBoundaryStore(tmp_path / "wechat-send.sqlite")
    try:
        store.put(_boundary(idempotency_key="idem-1", action_fingerprint="fp-1"))
        with pytest.raises(WeChatSendBoundaryConflictError):
            store.put(_boundary(idempotency_key="idem-2", action_fingerprint="fp-1"))
    finally:
        store.close()


def test_send_attempted_and_unknown_block_automatic_retry(tmp_path: Path) -> None:
    store = SqliteWeChatSendBoundaryStore(tmp_path / "wechat-send.sqlite")
    boundary = _boundary()
    try:
        store.put(boundary)
        store.transition(boundary.execution_id, "drafted")
        store.transition(boundary.execution_id, "confirmation_requested")
        store.transition(boundary.execution_id, "confirmed")
        attempted = store.transition(
            boundary.execution_id,
            "send_attempted",
            send_observation_ref="observe:send-click-1",
        )
        assert attempted.requires_manual_review is True
        assert attempted.is_terminal is False

        unknown = store.transition(
            boundary.execution_id,
            "unknown",
            error_ref="error:send-result-unknown",
        )
        assert unknown.requires_manual_review is True
        assert unknown.is_terminal is True
        assert unknown.error_ref == "error:send-result-unknown"

        with pytest.raises(WeChatSendBoundaryTransitionError):
            store.transition(boundary.execution_id, "send_attempted")
    finally:
        store.close()


def test_not_sent_is_terminal_and_requires_new_task(tmp_path: Path) -> None:
    store = SqliteWeChatSendBoundaryStore(tmp_path / "wechat-send.sqlite")
    boundary = _boundary()
    try:
        store.put(boundary)
        store.transition(boundary.execution_id, "drafted")
        not_sent = store.transition(
            boundary.execution_id,
            "not_sent",
            error_ref="error:user-rejected",
        )
        assert not_sent.is_terminal is True
        assert not_sent.error_ref == "error:user-rejected"

        with pytest.raises(WeChatSendBoundaryTransitionError):
            store.transition(boundary.execution_id, "confirmation_requested")
    finally:
        store.close()


def test_invalid_transition_is_rejected(tmp_path: Path) -> None:
    store = SqliteWeChatSendBoundaryStore(tmp_path / "wechat-send.sqlite")
    boundary = _boundary()
    try:
        store.put(boundary)
        with pytest.raises(WeChatSendBoundaryTransitionError):
            store.transition(boundary.execution_id, "sent")
    finally:
        store.close()


def _boundary(
    *,
    execution_id: str = "exec-1",
    idempotency_key: str = "idem-1",
    action_fingerprint: str = "fingerprint-1",
) -> WeChatSendBoundary:
    return WeChatSendBoundary(
        execution_id=execution_id,
        idempotency_key=idempotency_key,
        task_ref_kind="task",
        task_ref_id="task-1",
        contact_summary_hash="contact-hash-1",
        message_hash="message-hash-1",
        action_fingerprint=action_fingerprint,
    )
