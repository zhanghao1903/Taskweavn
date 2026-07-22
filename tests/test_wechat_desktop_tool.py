from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app_control_protocol import ToolCommand, ToolEvent, ToolObservation

from taskweavn.integrations.wechat_tool import (
    SendBoundaryReconciliationEvidence,
    SendBoundaryStoreError,
    SqliteSendBoundaryStore,
    managed_send_boundary_key,
)
from taskweavn.observability import (
    build_disabled_logging_config,
    build_session_logging_config,
    get_logging_manager,
)
from taskweavn.tools import WeChatDesktopTool, WeChatDesktopToolConfig
from taskweavn.types.wechat_desktop import (
    WeChatDesktopAction,
    WeChatDesktopObservation,
)


@dataclass
class FakeWeChatPackageClient:
    next_observation: ToolObservation = field(
        default_factory=lambda: ToolObservation(
            command_id="cmd_focus",
            tool="wechat.desktop",
            operation="focus_contact",
            status="ok",
            success=True,
            summary="Contact focused.",
            observation={
                "currentChatTitle": "文件传输助手",
                "confidence": 0.95,
            },
            evidence={"phase": "focus_contact.verify"},
            metadata={"safe": True},
        )
    )
    commands: list[ToolCommand] = field(default_factory=list)

    def run_command(
        self,
        command: ToolCommand | dict[str, Any],
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        assert isinstance(command, ToolCommand)
        self.commands.append(command)
        if observer is not None and hasattr(observer, "on_event"):
            observer.on_event(
                ToolEvent(
                    command_id=command.command_id,
                    seq=1,
                    event_type="progress",
                    phase=f"{command.operation}.test",
                    summary="progress",
                    data={"rawMessage": "secret message"},
                )
            )
        return self.next_observation


def test_wechat_desktop_tool_builds_focus_contact_command() -> None:
    client = FakeWeChatPackageClient()
    tool = WeChatDesktopTool(client=client)

    observation = tool.execute(
        WeChatDesktopAction(
            operation="focus_contact",
            contact="文件传输助手",
            metadata={"source": "test"},
        )
    )

    command = client.commands[0]
    assert command.tool == "wechat.desktop"
    assert command.operation == "focus_contact"
    assert command.input["contact"] == "文件传输助手"
    assert command.metadata == {"source": "test"}
    assert observation.success is True
    assert observation.status == "ok"
    assert observation.metadata["observation"]["currentChatTitle"] == "文件传输助手"
    assert observation.metadata["evidence"] == {"phase": "focus_contact.verify"}
    assert observation.metadata["tool_events"][0]["phase"] == "focus_contact.test"
    assert observation.metadata["tool_events"][0]["dataKeys"] == ["rawMessage"]


def test_wechat_desktop_tool_builds_read_model_commands() -> None:
    client = FakeWeChatPackageClient()
    tool = WeChatDesktopTool(client=client)

    tool.execute(
        WeChatDesktopAction(
            operation="inspect_window",
            include_raw=False,
            include_actionables=True,
        )
    )
    tool.execute(
        WeChatDesktopAction(
            operation="list_contacts",
            limit=10,
            page_token="cursor-1",
        )
    )
    tool.execute(WeChatDesktopAction(operation="list_conversations", limit=11))
    tool.execute(
        WeChatDesktopAction(
            operation="open_contact",
            contact="文件传输助手",
        )
    )
    tool.execute(
        WeChatDesktopAction(
            operation="read_contact_messages",
            contact="文件传输助手",
            limit=12,
        )
    )

    command_facts = [(command.operation, command.input) for command in client.commands]
    assert command_facts == [
        (
            "inspect_window",
            {"includeRaw": False, "includeActionables": True},
        ),
        ("list_contacts", {"limit": 10, "pageToken": "cursor-1"}),
        ("list_conversations", {"limit": 11}),
        ("open_contact", {"contact": "文件传输助手"}),
        ("read_contact_messages", {"contact": "文件传输助手", "limit": 12}),
    ]


def test_wechat_desktop_tool_preserves_submit_unknown_failure() -> None:
    client = FakeWeChatPackageClient(
        ToolObservation(
            command_id="cmd_submit",
            tool="wechat.desktop",
            operation="submit_draft",
            status="unknown",
            success=False,
            summary="Submit result could not be verified.",
            observation={"sendAttempted": True},
            failure_kind="submit_unknown",
            message="Keyboard submit completed but verification was inconclusive.",
            recovery_hint="Check WeChat manually before retrying.",
            retryable=False,
        )
    )
    tool = WeChatDesktopTool(client=client)

    observation = tool.execute(WeChatDesktopAction(operation="submit_draft"))

    assert observation.success is False
    assert observation.status == "unknown"
    assert observation.metadata["failure_kind"] == "submit_unknown"
    assert observation.metadata["message"] == (
        "Keyboard submit completed but verification was inconclusive."
    )
    assert observation.metadata["recovery_hint"] == "Check WeChat manually before retrying."
    assert observation.metadata["retryable"] is False


def test_wechat_desktop_tool_emits_runtime_logs_without_raw_message(
    tmp_path: Path,
) -> None:
    session_id = "session-wechat-log"
    log_root = tmp_path / "logs"
    manager = get_logging_manager()
    manager.apply_config(build_session_logging_config(log_root, level="DEBUG"))
    try:
        client = FakeWeChatPackageClient(
            ToolObservation(
                command_id="cmd_draft",
                tool="wechat.desktop",
                operation="draft_message",
                status="ok",
                success=True,
                summary="Draft prepared.",
                observation={},
            )
        )
        tool = WeChatDesktopTool(client=client)

        tool.execute(
            WeChatDesktopAction(
                operation="draft_message",
                message="secret message",
                metadata={
                    "sessionId": session_id,
                    "taskId": "task-1",
                    "executionId": "exec-1",
                    "taskType": "communication.wechat.send_message",
                },
            )
        )

        runtime_log = log_root / "sessions" / session_id / "runtime.jsonl"
        rows = [
            json.loads(line)
            for line in runtime_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        events = [row["event"] for row in rows]
        assert "runtime_action" in events
        assert "runtime_observation" in events
        observation_row = next(row for row in rows if row["event"] == "runtime_observation")
        assert observation_row["context"]["task_id"] == "task-1"
        data = observation_row["data"]
        assert data["schema"] == "plato.runtime_observability.v1"
        assert data["runtime"] == "wechat_desktop_tool"
        assert data["messageHash"].startswith("sha256:")
        assert data["messageChars"] == 14
        assert data["metadata"]["packageEventCount"] == 1
        assert data["metadata"]["packageEvents"][0]["dataKeys"] == ["rawMessage"]
        assert "secret message" not in runtime_log.read_text(encoding="utf-8")
    finally:
        manager.apply_config(build_disabled_logging_config(tmp_path / "disabled-logs"))


def test_managed_send_boundary_replays_completed_result_without_second_call(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "tool-effects.sqlite"
    first_client = FakeWeChatPackageClient(_successful_send_observation())
    first_tool = _managed_send_tool(
        client=first_client,
        db_path=db_path,
        key="wechat-send:session-1:task-1",
    )
    action = _send_action()

    first = first_tool.execute(action)
    first_tool.shutdown()

    replay_client = FakeWeChatPackageClient(_successful_send_observation())
    replay_tool = _managed_send_tool(
        client=replay_client,
        db_path=db_path,
        key="wechat-send:session-1:task-1",
    )
    replay = replay_tool.execute(_send_action())
    replay_tool.shutdown()

    assert len(first_client.commands) == 1
    assert first_client.commands[0].idempotency_key == "wechat-send:session-1:task-1"
    assert replay_client.commands == []
    assert first.success is True
    assert replay.success is True
    assert replay.metadata["send_boundary"]["replayed"] is True
    assert "No additional WeChat send was attempted" in replay.summary


def test_managed_send_boundary_rejects_same_key_for_changed_message(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "tool-effects.sqlite"
    first_tool = _managed_send_tool(
        client=FakeWeChatPackageClient(_successful_send_observation()),
        db_path=db_path,
        key="wechat-send:session-1:task-1",
    )
    first_tool.execute(_send_action())
    first_tool.shutdown()

    conflict_client = FakeWeChatPackageClient(_successful_send_observation())
    conflict_tool = _managed_send_tool(
        client=conflict_client,
        db_path=db_path,
        key="wechat-send:session-1:task-1",
    )
    conflict = conflict_tool.execute(_send_action(message="changed"))
    conflict_tool.shutdown()

    assert conflict_client.commands == []
    assert conflict.success is False
    assert conflict.status == "failed"
    assert conflict.metadata["failure_kind"] == "idempotency_conflict"
    assert conflict.metadata["observation"]["sendAttempted"] is False


def test_managed_send_boundary_never_replays_unknown_outcome(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "tool-effects.sqlite"
    unknown_client = FakeWeChatPackageClient(
        ToolObservation(
            command_id="cmd_send_unknown",
            tool="wechat.desktop",
            operation="send_message",
            status="unknown",
            success=False,
            summary="Send could not be verified.",
            observation={"sendAttempted": True},
            failure_kind="send_unverified",
            message="Submit may have occurred.",
            recovery_hint="Inspect WeChat manually.",
            retryable=False,
        )
    )
    first_tool = _managed_send_tool(
        client=unknown_client,
        db_path=db_path,
        key="wechat-send:session-1:task-unknown",
    )
    first = first_tool.execute(_send_action())
    first_tool.shutdown()

    replay_client = FakeWeChatPackageClient(_successful_send_observation())
    replay_tool = _managed_send_tool(
        client=replay_client,
        db_path=db_path,
        key="wechat-send:session-1:task-unknown",
    )
    replay = replay_tool.execute(_send_action())
    replay_tool.shutdown()

    assert len(unknown_client.commands) == 1
    assert first.status == "unknown"
    assert replay_client.commands == []
    assert replay.status == "unknown"
    assert replay.metadata["failure_kind"] == "send_unverified"
    assert "was not replayed" in replay.summary


def test_managed_send_boundary_blocks_interrupted_in_progress_record(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "tool-effects.sqlite"
    first_store = SqliteSendBoundaryStore(db_path)
    first = first_store.claim(
        scope_id="session-1",
        idempotency_key="wechat-send:session-1:task-interrupted",
        request_hash="stable-request-hash",
    )
    first_store.close()

    reopened_store = SqliteSendBoundaryStore(db_path)
    replay = reopened_store.claim(
        scope_id="session-1",
        idempotency_key="wechat-send:session-1:task-interrupted",
        request_hash="stable-request-hash",
    )
    reopened_store.close()

    assert first.status == "acquired"
    assert replay.status == "in_progress"
    assert replay.record.observation is None


def test_unknown_send_boundary_can_be_manually_reconciled_without_losing_observation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "tool-effects.sqlite"
    key = "wechat-send:session-1:task-reconciled"
    request_hash = "request-hash"
    observation = _ambiguous_submitted_observation()
    with SqliteSendBoundaryStore(db_path) as store:
        store.claim(
            scope_id="session-1",
            idempotency_key=key,
            request_hash=request_hash,
        )
        store.complete(
            scope_id="session-1",
            idempotency_key=key,
            request_hash=request_hash,
            state="unknown",
            observation=observation,
        )
        reconciled = store.reconcile_unknown_to_completed(
            scope_id="session-1",
            idempotency_key=key,
            request_hash=request_hash,
            evidence=_manual_reconciliation_evidence(),
        )
        replay = store.claim(
            scope_id="session-1",
            idempotency_key=key,
            request_hash=request_hash,
        )

    assert reconciled.state == "completed"
    assert reconciled.observation == observation
    assert reconciled.reconciliation == _manual_reconciliation_evidence()
    assert reconciled.reconciled_at is not None
    assert replay.status == "replay"
    assert replay.record.observation == observation
    assert replay.record.reconciliation == _manual_reconciliation_evidence()


def test_manual_reconciliation_rejects_wrong_hash_without_mutating_unknown(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "tool-effects.sqlite"
    key = "wechat-send:session-1:task-unknown"
    with SqliteSendBoundaryStore(db_path) as store:
        store.claim(
            scope_id="session-1",
            idempotency_key=key,
            request_hash="expected-hash",
        )
        store.complete(
            scope_id="session-1",
            idempotency_key=key,
            request_hash="expected-hash",
            state="unknown",
            observation=_ambiguous_submitted_observation(),
        )
        with pytest.raises(SendBoundaryStoreError, match="request hash"):
            store.reconcile_unknown_to_completed(
                scope_id="session-1",
                idempotency_key=key,
                request_hash="wrong-hash",
                evidence=_manual_reconciliation_evidence(),
            )
        record = store.get(scope_id="session-1", idempotency_key=key)

    assert record is not None
    assert record.state == "unknown"
    assert record.reconciliation is None


def test_manual_reconciliation_rejects_evidence_mismatch_and_second_resolution(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "tool-effects.sqlite"
    key = "wechat-send:session-1:task-unknown"
    with SqliteSendBoundaryStore(db_path) as store:
        store.claim(
            scope_id="session-1",
            idempotency_key=key,
            request_hash="request-hash",
        )
        store.complete(
            scope_id="session-1",
            idempotency_key=key,
            request_hash="request-hash",
            state="unknown",
            observation=_ambiguous_submitted_observation(),
        )
        with pytest.raises(SendBoundaryStoreError, match="contact"):
            store.reconcile_unknown_to_completed(
                scope_id="session-1",
                idempotency_key=key,
                request_hash="request-hash",
                evidence=_manual_reconciliation_evidence(contact="wrong contact"),
            )
        store.reconcile_unknown_to_completed(
            scope_id="session-1",
            idempotency_key=key,
            request_hash="request-hash",
            evidence=_manual_reconciliation_evidence(),
        )
        with pytest.raises(SendBoundaryStoreError, match="only an unknown"):
            store.reconcile_unknown_to_completed(
                scope_id="session-1",
                idempotency_key=key,
                request_hash="request-hash",
                evidence=_manual_reconciliation_evidence(),
            )


def test_managed_replay_projects_reconciled_unknown_as_success_without_second_call(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "tool-effects.sqlite"
    key = "wechat-send:session-1:task-reconciled"
    message_hash = hashlib.sha256("你好".encode()).hexdigest()
    unknown_client = FakeWeChatPackageClient(
        ToolObservation(
            command_id="cmd_send_unknown",
            tool="wechat.desktop",
            operation="send_message",
            status="unknown",
            success=False,
            summary="Submitted message was not visible after send.",
            observation={
                "focusedContact": "文件传输助手",
                "messageHash": f"sha256:{message_hash}",
                "submitted": True,
            },
            failure_kind="send_unverified",
            retryable=False,
        )
    )
    first_tool = _managed_send_tool(client=unknown_client, db_path=db_path, key=key)
    first_tool.execute(_send_action())
    first_tool.shutdown()

    with SqliteSendBoundaryStore(db_path) as store:
        record = store.get(scope_id="session-1", idempotency_key=key)
        assert record is not None
        store.reconcile_unknown_to_completed(
            scope_id="session-1",
            idempotency_key=key,
            request_hash=record.request_hash,
            evidence=_manual_reconciliation_evidence(message_hash=message_hash),
        )

    replay_client = FakeWeChatPackageClient(_successful_send_observation())
    replay_tool = _managed_send_tool(client=replay_client, db_path=db_path, key=key)
    replay = replay_tool.execute(_send_action())
    replay_tool.shutdown()

    assert replay_client.commands == []
    assert replay.success is True
    assert replay.status == "ok"
    assert replay.metadata["replay_original_status"] == "unknown"
    assert replay.metadata["send_boundary"]["replayed"] is True
    assert replay.metadata["send_boundary"]["resolution"] == ("manual_reconciliation")


def test_wechat_action_schema_does_not_delegate_send_key_choice_to_llm() -> None:
    assert "idempotency_key" not in WeChatDesktopAction.model_json_schema()["properties"]


def test_managed_send_key_is_stable_and_task_scoped() -> None:
    assert managed_send_boundary_key("session-1", "task-1") == ("wechat-send:session-1:task-1")
    assert managed_send_boundary_key("session-1", "task-1") != (
        managed_send_boundary_key("session-1", "task-2")
    )


def _managed_send_tool(
    *,
    client: FakeWeChatPackageClient,
    db_path: Path,
    key: str | None,
) -> WeChatDesktopTool:
    return WeChatDesktopTool(
        client=client,
        config=_managed_send_tool_config(),
        send_boundary_store=SqliteSendBoundaryStore(db_path),
        send_boundary_scope="session-1",
        send_boundary_key=key,
    )


def _managed_send_tool_config() -> WeChatDesktopToolConfig:
    return WeChatDesktopToolConfig()


def _send_action(*, message: str = "你好") -> WeChatDesktopAction:
    return WeChatDesktopAction(
        operation="send_message",
        contact="文件传输助手",
        message=message,
        verify_after_submit=True,
    )


def _successful_send_observation() -> ToolObservation:
    return ToolObservation(
        command_id="cmd_send",
        tool="wechat.desktop",
        operation="send_message",
        status="ok",
        success=True,
        summary="Message submitted and observed.",
        observation={"sendAttempted": True, "submitted": True},
    )


def _ambiguous_submitted_observation() -> WeChatDesktopObservation:
    return WeChatDesktopObservation(
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


def _manual_reconciliation_evidence(
    *,
    contact: str = "文件传输助手",
    message_hash: str = "a" * 64,
) -> SendBoundaryReconciliationEvidence:
    return SendBoundaryReconciliationEvidence(
        source="manual_read_only_ui",
        operator="test-operator",
        expected_contact=contact,
        message_sha256=message_hash,
        observed_outgoing_count=1,
        exact_message_visible=True,
        chat_input_empty=True,
        observed_at=datetime(2026, 7, 21, 22, 24, tzinfo=UTC),
        note="Exact outgoing message appeared once and the input was empty.",
    )
