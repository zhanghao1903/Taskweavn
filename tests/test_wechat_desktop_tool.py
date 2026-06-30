from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app_control_protocol import ToolCommand, ToolEvent, ToolObservation

from taskweavn.observability import (
    build_disabled_logging_config,
    build_session_logging_config,
    get_logging_manager,
)
from taskweavn.tools import WeChatDesktopTool
from taskweavn.types.wechat_desktop import WeChatDesktopAction


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
                idempotency_key="idem-1",
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
