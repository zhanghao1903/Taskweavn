from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app_control_protocol import ToolCommand, ToolEvent, ToolObservation

import scripts.manual_wechat_desktop_tool_smoke as smoke


class _FakeUnixSocketServiceClient:
    operations: list[str] = []
    socket_path: str | None = None
    token: str | None = None
    timeout: float | None = None

    def __init__(
        self,
        socket_path: str,
        *,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        type(self).socket_path = socket_path
        type(self).token = token
        type(self).timeout = timeout

    def run_command(
        self,
        command: dict[str, Any],
        *,
        action: str = "run",
        request_id: str | None = None,
    ) -> list[dict[str, Any]]:
        tool_command = ToolCommand.from_dict(command)
        type(self).operations.append(tool_command.operation)
        observation = _successful_observation(tool_command)
        event = ToolEvent(
            command_id=tool_command.command_id,
            seq=0,
            event_type="started",
            phase=tool_command.operation,
            data={
                "appControlOperation": tool_command.operation,
                "appControlObservation": {"nodes": [{"title": "private"}]},
            },
        )
        return [
            {
                "schema": "app_control.service.event.v1",
                "requestId": request_id,
                "status": "event",
                "success": True,
                "event": event.to_dict(),
            },
            {
                "schema": "app_control.service.response.v1",
                "requestId": request_id,
                "status": "complete",
                "success": True,
                "observation": observation.to_dict(),
            },
        ]


class _FakeWeChatDesktopTool:
    operations: list[str] = []

    @classmethod
    def from_config(cls, app_control: object, config: dict[str, Any]) -> _FakeWeChatDesktopTool:
        return cls()

    def run_command(
        self,
        command: ToolCommand,
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        self.operations.append(command.operation)
        return _successful_observation(command)


class _FakeOpenContactFailingWeChatDesktopTool(_FakeWeChatDesktopTool):
    def run_command(
        self,
        command: ToolCommand,
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        if command.operation != "open_contact":
            return super().run_command(command, observer=observer)
        self.operations.append(command.operation)
        return ToolObservation(
            command_id=command.command_id,
            tool=command.tool,
            operation=command.operation,
            status="not_found",
            success=False,
            summary="contact not found",
            observation={},
            evidence={},
            timing={},
            failure_kind="contact_not_found",
            message="contact not found",
            recovery_hint="Open the target chat manually and retry.",
            retryable=True,
            error=None,
            metadata={},
        )


def test_manual_wechat_desktop_tool_smoke_drafts_without_submit(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(
        smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient
    )
    monkeypatch.setattr(smoke, "WeChatDesktopTool", _FakeWeChatDesktopTool)
    evidence_path = tmp_path / "evidence.json"

    exit_code = smoke.main(
        [
            "--message",
            "hello",
            "--token",
            "local-token",
            "--allow-focus-select",
            "--smoke-id",
            "smoke-test",
            "--evidence-output",
            str(evidence_path),
        ]
    )

    assert exit_code == 0
    assert _FakeUnixSocketServiceClient.operations == ["readiness"]
    assert _FakeUnixSocketServiceClient.socket_path == "/tmp/app-control.sock"
    assert _FakeUnixSocketServiceClient.token == "local-token"
    assert _FakeUnixSocketServiceClient.timeout == 30.0
    assert _FakeWeChatDesktopTool.operations == [
        "open_wechat",
        "open_contact",
        "draft_message",
        "observe_current_chat",
    ]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["kind"] == "wechat_desktop_tool_manual_smoke"
    assert evidence["submitRequested"] is False
    assert evidence["submitConfirmed"] is False
    assert evidence["submitAttempted"] is False
    assert evidence["submitted"] is False
    assert evidence["allowFocusSelect"] is True
    assert evidence["contactSelectionMode"] == "open_contact"
    assert [item["operation"] for item in evidence["observations"]] == [
        "readiness",
        *_FakeWeChatDesktopTool.operations,
    ]
    assert evidence["config"]["transport"] == "unix_socket"
    assert evidence["config"]["socketPath"] == "/tmp/app-control.sock"
    assert len(evidence["events"]) == 1
    assert evidence["events"][0]["data"] == {
        "appControlOperation": "readiness"
    }


def test_manual_wechat_desktop_tool_smoke_requires_explicit_submit_confirmation(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(
        smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient
    )
    monkeypatch.setattr(smoke, "WeChatDesktopTool", _FakeWeChatDesktopTool)
    evidence_path = tmp_path / "evidence.json"

    exit_code = smoke.main(
        [
            "--message",
            "hello",
            "--token",
            "local-token",
            "--allow-focus-select",
            "--allow-submit",
            "--smoke-id",
            "smoke-test",
            "--evidence-output",
            str(evidence_path),
        ]
    )

    assert exit_code == 2
    assert _FakeWeChatDesktopTool.operations == [
        "open_wechat",
        "open_contact",
        "draft_message",
        "observe_current_chat",
    ]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["submitRequested"] is True
    assert evidence["submitConfirmed"] is False
    assert evidence["submitAttempted"] is False
    assert evidence["submitted"] is False
    assert evidence["observations"][-1]["failure_kind"] == "submit_not_confirmed"


def test_manual_wechat_desktop_tool_smoke_submits_only_with_send_confirmation(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(
        smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient
    )
    monkeypatch.setattr(smoke, "WeChatDesktopTool", _FakeWeChatDesktopTool)
    evidence_path = tmp_path / "evidence.json"

    exit_code = smoke.main(
        [
            "--message",
            "hello",
            "--token",
            "local-token",
            "--allow-focus-select",
            "--allow-submit",
            "--confirm-submit",
            "SEND",
            "--smoke-id",
            "smoke-test",
            "--evidence-output",
            str(evidence_path),
        ]
    )

    assert exit_code == 0
    assert _FakeWeChatDesktopTool.operations == [
        "open_wechat",
        "open_contact",
        "draft_message",
        "observe_current_chat",
        "submit_draft",
    ]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["submitRequested"] is True
    assert evidence["submitConfirmed"] is True
    assert evidence["submitAttempted"] is True
    assert evidence["submitted"] is True


def test_manual_wechat_desktop_tool_smoke_does_not_report_submit_on_pre_submit_failure(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeOpenContactFailingWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(
        smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient
    )
    monkeypatch.setattr(smoke, "WeChatDesktopTool", _FakeOpenContactFailingWeChatDesktopTool)
    evidence_path = tmp_path / "evidence.json"

    exit_code = smoke.main(
        [
            "--message",
            "hello",
            "--token",
            "local-token",
            "--allow-focus-select",
            "--allow-submit",
            "--confirm-submit",
            "SEND",
            "--smoke-id",
            "smoke-test",
            "--evidence-output",
            str(evidence_path),
        ]
    )

    assert exit_code == 1
    assert _FakeOpenContactFailingWeChatDesktopTool.operations == [
        "open_wechat",
        "open_contact",
    ]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["submitRequested"] is True
    assert evidence["submitConfirmed"] is True
    assert evidence["submitAttempted"] is False
    assert evidence["submitted"] is False
    assert [item["operation"] for item in evidence["observations"]] == [
        "readiness",
        "open_wechat",
        "open_contact",
    ]
    assert evidence["observations"][-1]["failure_kind"] == "contact_not_found"


def test_manual_wechat_desktop_tool_smoke_requires_contact_selection_mode(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(
        smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient
    )
    monkeypatch.setattr(smoke, "WeChatDesktopTool", _FakeWeChatDesktopTool)
    evidence_path = tmp_path / "evidence.json"

    exit_code = smoke.main(
        [
            "--message",
            "hello",
            "--token",
            "local-token",
            "--smoke-id",
            "smoke-test",
            "--evidence-output",
            str(evidence_path),
        ]
    )

    assert exit_code == 2
    assert _FakeWeChatDesktopTool.operations == ["open_wechat"]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["allowFocusSelect"] is False
    assert evidence["contactSelectionMode"] == "blocked"
    assert evidence["submitAttempted"] is False
    assert evidence["submitted"] is False
    assert [item["operation"] for item in evidence["observations"]] == [
        "readiness",
        "open_wechat",
        "open_contact",
    ]
    assert evidence["observations"][-1]["failure_kind"] == (
        "contact_selection_not_authorized"
    )


def _successful_observation(command: ToolCommand) -> ToolObservation:
    return ToolObservation(
        command_id=command.command_id,
        tool=command.tool,
        operation=command.operation,
        status="ok",
        success=True,
        summary=f"{command.operation} ok",
        observation={"operation": command.operation},
        evidence={},
        timing={},
        metadata={},
    )
