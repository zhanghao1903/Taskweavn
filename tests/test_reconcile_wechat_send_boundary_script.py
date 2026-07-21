from __future__ import annotations

import json
from pathlib import Path

import scripts.reconcile_wechat_send_boundary as reconciliation_script
from taskweavn.integrations.wechat_tool import SqliteSendBoundaryStore
from taskweavn.types.wechat_desktop import WeChatDesktopObservation


def test_reconciliation_command_archives_unknown_boundary_without_external_action(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "tool-effects.sqlite"
    output_path = tmp_path / "reconciliation.json"
    _seed_unknown_boundary(db_path)

    result = reconciliation_script.main(
        [
            "--effect-db",
            str(db_path),
            "--session-id",
            "session-1",
            "--task-id",
            "task-1",
            "--request-hash",
            "request-hash",
            "--contact",
            "文件传输助手",
            "--message-sha256",
            "a" * 64,
            "--observed-at",
            "2026-07-21T22:24:00+08:00",
            "--operator",
            "test-operator",
            "--note",
            "One exact outgoing message was visible and the input was empty.",
            "--confirm-exact-outgoing-count",
            "1",
            "--confirm-chat-input-empty",
            "--confirm-reconciliation",
            "COMPLETE",
            "--evidence-output",
            str(output_path),
        ]
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    with SqliteSendBoundaryStore(db_path) as store:
        replay = store.claim(
            scope_id="session-1",
            idempotency_key="wechat-send:session-1:task-1",
            request_hash="request-hash",
        )

    assert result == 0
    assert report["previousState"] == "unknown"
    assert report["state"] == "completed"
    assert report["externalActionAttempted"] is False
    assert replay.status == "replay"


def test_reconciliation_command_requires_explicit_completion_token(tmp_path: Path) -> None:
    db_path = tmp_path / "tool-effects.sqlite"
    _seed_unknown_boundary(db_path)

    result = reconciliation_script.main(
        [
            "--effect-db",
            str(db_path),
            "--session-id",
            "session-1",
            "--task-id",
            "task-1",
            "--request-hash",
            "request-hash",
            "--contact",
            "文件传输助手",
            "--message-sha256",
            "a" * 64,
            "--observed-at",
            "2026-07-21T22:24:00+08:00",
            "--operator",
            "test-operator",
            "--note",
            "One exact outgoing message was visible and the input was empty.",
            "--confirm-exact-outgoing-count",
            "1",
            "--confirm-chat-input-empty",
            "--confirm-reconciliation",
            "NO",
        ]
    )

    with SqliteSendBoundaryStore(db_path) as store:
        record = store.get(
            scope_id="session-1",
            idempotency_key="wechat-send:session-1:task-1",
        )
    assert result == 2
    assert record is not None
    assert record.state == "unknown"


def _seed_unknown_boundary(db_path: Path) -> None:
    observation = WeChatDesktopObservation(
        success=False,
        operation="send_message",
        status="unknown",
        summary="Submitted message was not visible after send.",
        metadata={
            "observation": {
                "focusedContact": "文件传输助手",
                "messageHash": f"sha256:{'a' * 64}",
                "submitted": True,
                "verified": False,
            }
        },
    )
    with SqliteSendBoundaryStore(db_path) as store:
        store.claim(
            scope_id="session-1",
            idempotency_key="wechat-send:session-1:task-1",
            request_hash="request-hash",
        )
        store.complete(
            scope_id="session-1",
            idempotency_key="wechat-send:session-1:task-1",
            request_hash="request-hash",
            state="unknown",
            observation=observation,
        )
