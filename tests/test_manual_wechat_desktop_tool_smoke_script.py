from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app_control_protocol import ToolCommand, ToolObservation

import scripts.manual_wechat_desktop_tool_smoke as smoke


class _FakeComputerUseClient:
    @classmethod
    def from_config(cls, config: dict[str, Any]) -> object:
        return {"config": config}


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


class _FakeFocusFailingWeChatDesktopTool(_FakeWeChatDesktopTool):
    def run_command(
        self,
        command: ToolCommand,
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        if command.operation != "focus_contact":
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
    monkeypatch.setattr(smoke, "ComputerUseClient", _FakeComputerUseClient)
    monkeypatch.setattr(smoke, "WeChatDesktopTool", _FakeWeChatDesktopTool)
    evidence_path = tmp_path / "evidence.json"

    exit_code = smoke.main(
        [
            "--message",
            "hello",
            "--smoke-id",
            "smoke-test",
            "--evidence-output",
            str(evidence_path),
        ]
    )

    assert exit_code == 0
    assert _FakeWeChatDesktopTool.operations == [
        "open_wechat",
        "focus_contact",
        "draft_message",
        "observe_current_chat",
    ]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["kind"] == "wechat_desktop_tool_manual_smoke"
    assert evidence["submitRequested"] is False
    assert evidence["submitConfirmed"] is False
    assert evidence["submitAttempted"] is False
    assert evidence["submitted"] is False
    assert [item["operation"] for item in evidence["observations"]] == (
        _FakeWeChatDesktopTool.operations
    )


def test_manual_wechat_desktop_tool_smoke_requires_explicit_submit_confirmation(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeWeChatDesktopTool.operations = []
    monkeypatch.setattr(smoke, "ComputerUseClient", _FakeComputerUseClient)
    monkeypatch.setattr(smoke, "WeChatDesktopTool", _FakeWeChatDesktopTool)
    evidence_path = tmp_path / "evidence.json"

    exit_code = smoke.main(
        [
            "--message",
            "hello",
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
        "focus_contact",
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
    monkeypatch.setattr(smoke, "ComputerUseClient", _FakeComputerUseClient)
    monkeypatch.setattr(smoke, "WeChatDesktopTool", _FakeWeChatDesktopTool)
    evidence_path = tmp_path / "evidence.json"

    exit_code = smoke.main(
        [
            "--message",
            "hello",
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
        "focus_contact",
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
    _FakeFocusFailingWeChatDesktopTool.operations = []
    monkeypatch.setattr(smoke, "ComputerUseClient", _FakeComputerUseClient)
    monkeypatch.setattr(smoke, "WeChatDesktopTool", _FakeFocusFailingWeChatDesktopTool)
    evidence_path = tmp_path / "evidence.json"

    exit_code = smoke.main(
        [
            "--message",
            "hello",
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
    assert _FakeFocusFailingWeChatDesktopTool.operations == [
        "open_wechat",
        "focus_contact",
    ]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["submitRequested"] is True
    assert evidence["submitConfirmed"] is True
    assert evidence["submitAttempted"] is False
    assert evidence["submitted"] is False
    assert [item["operation"] for item in evidence["observations"]] == [
        "open_wechat",
        "focus_contact",
    ]
    assert evidence["observations"][-1]["failure_kind"] == "contact_not_found"
