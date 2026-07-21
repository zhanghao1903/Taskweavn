from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app_control_protocol import ToolCommand, ToolEvent, ToolObservation

import scripts.manual_wechat_desktop_tool_smoke as smoke
from taskweavn.integrations.app_control.service_manifest import (
    AppControlServiceManifest,
)


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


def test_smoke_evidence_redacts_nested_message_collections() -> None:
    redacted = smoke._redact_evidence(
        {
            "messages": [{"text": "private chat message"}],
            "messageHash": "safe-hash",
        }
    )

    assert redacted == {
        "messages": {"redacted": True, "count": 1},
        "messageHash": "safe-hash",
    }


class _FakeOpenContactFailingWeChatDesktopTool(_FakeWeChatDesktopTool):
    def run_command(
        self,
        command: ToolCommand,
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        if command.operation != "send_message":
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


class _FakeSendUnverifiedWeChatDesktopTool(_FakeWeChatDesktopTool):
    def run_command(
        self,
        command: ToolCommand,
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        if command.operation != "send_message":
            return super().run_command(command, observer=observer)
        self.operations.append(command.operation)
        return ToolObservation(
            command_id=command.command_id,
            tool=command.tool,
            operation=command.operation,
            status="unknown",
            success=False,
            summary="Submitted message was not visible after send.",
            observation={
                "submitted": True,
                "verified": False,
                "verificationRequested": True,
            },
            evidence={},
            timing={},
            failure_kind="send_unverified",
            message="Submitted message was not visible after send.",
            recovery_hint="Check WeChat manually before retrying.",
            retryable=False,
            error=None,
            metadata={},
        )


def test_manual_wechat_desktop_tool_smoke_default_config_allows_coordinate_click(
    tmp_path: Path,
) -> None:
    args = smoke._parse_args(
        [
            "--config",
            str(tmp_path / "missing-app-control.toml"),
            "--message",
            "hello",
        ]
    )

    config = smoke._tool_config(args)

    assert isinstance(config, dict)
    assert config["computer_use"]["allow_coordinate_click"] is True


def test_manual_wechat_desktop_tool_smoke_drafts_without_submit(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient)
    monkeypatch.setattr(smoke, "PackageWeChatDesktopTool", _FakeWeChatDesktopTool)
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
    assert evidence["events"][0]["data"] == {"appControlOperation": "readiness"}


def test_manual_wechat_desktop_tool_smoke_readiness_only_never_operates_wechat(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient)
    monkeypatch.setattr(smoke, "PackageWeChatDesktopTool", _FakeWeChatDesktopTool)
    evidence_path = tmp_path / "readiness.json"

    exit_code = smoke.main(
        [
            "--message",
            "readiness only",
            "--token",
            "local-token",
            "--readiness-only",
            "--evidence-output",
            str(evidence_path),
        ]
    )

    assert exit_code == 0
    assert _FakeUnixSocketServiceClient.operations == ["readiness"]
    assert _FakeWeChatDesktopTool.operations == []
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["readinessOnly"] is True
    assert [item["operation"] for item in evidence["observations"]] == ["readiness"]
    assert evidence["submitted"] is False


def test_manual_wechat_desktop_tool_smoke_reads_helper_manifest(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient)
    monkeypatch.setattr(smoke, "PackageWeChatDesktopTool", _FakeWeChatDesktopTool)
    token_path = tmp_path / "service.token"
    token_path.write_text("manifest-token\n", encoding="utf-8")
    manifest_path = tmp_path / "service.json"
    AppControlServiceManifest(
        endpoint=tmp_path / "service.sock",
        token_path=token_path,
        pid=123,
        bundle_id="com.taskweavn.plato.computer-use-helper.dev",
        service_version="0.3.0",
    ).write(manifest_path)
    evidence_path = tmp_path / "evidence.json"

    exit_code = smoke.main(
        [
            "--manifest-path",
            str(manifest_path),
            "--message",
            "hello",
            "--allow-focus-select",
            "--smoke-id",
            "manifest-smoke",
            "--evidence-output",
            str(evidence_path),
        ]
    )

    assert exit_code == 0
    assert _FakeUnixSocketServiceClient.socket_path == str(tmp_path / "service.sock")
    assert _FakeUnixSocketServiceClient.token == "manifest-token"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["config"]["manifestPath"] == str(manifest_path)


def test_manual_wechat_desktop_tool_smoke_rejects_manifest_transport_overrides(
    tmp_path: Path,
    capsys: Any,
) -> None:
    exit_code = smoke.main(
        [
            "--manifest-path",
            str(tmp_path / "service.json"),
            "--socket-path",
            str(tmp_path / "service.sock"),
            "--message",
            "hello",
        ]
    )

    assert exit_code == 2
    assert "mutually exclusive" in capsys.readouterr().err


def test_manual_wechat_desktop_tool_smoke_requires_explicit_submit_confirmation(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient)
    monkeypatch.setattr(smoke, "PackageWeChatDesktopTool", _FakeWeChatDesktopTool)
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
    assert _FakeWeChatDesktopTool.operations == []
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
    monkeypatch.setattr(smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient)
    monkeypatch.setattr(smoke, "PackageWeChatDesktopTool", _FakeWeChatDesktopTool)
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
            "--effect-db",
            str(tmp_path / "tool-effects.sqlite"),
            "--session-id",
            "session-1",
            "--task-id",
            "task-1",
            "--smoke-id",
            "smoke-test",
            "--evidence-output",
            str(evidence_path),
        ]
    )

    assert exit_code == 0
    assert _FakeWeChatDesktopTool.operations == ["send_message"]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["submitRequested"] is True
    assert evidence["submitConfirmed"] is True
    assert evidence["submitAttempted"] is True
    assert evidence["submitted"] is True
    assert evidence["replayed"] is False
    assert evidence["config"]["sessionId"] == "session-1"
    assert evidence["config"]["taskId"] == "task-1"


def test_manual_wechat_desktop_tool_smoke_does_not_report_submit_on_pre_submit_failure(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeOpenContactFailingWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient)
    monkeypatch.setattr(
        smoke,
        "PackageWeChatDesktopTool",
        _FakeOpenContactFailingWeChatDesktopTool,
    )
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
            "--effect-db",
            str(tmp_path / "tool-effects.sqlite"),
            "--session-id",
            "session-1",
            "--task-id",
            "task-failure",
            "--smoke-id",
            "smoke-test",
            "--evidence-output",
            str(evidence_path),
        ]
    )

    assert exit_code == 1
    assert _FakeOpenContactFailingWeChatDesktopTool.operations == ["send_message"]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["submitRequested"] is True
    assert evidence["submitConfirmed"] is True
    assert evidence["submitAttempted"] is False
    assert evidence["submitted"] is False
    assert [item["operation"] for item in evidence["observations"]] == [
        "readiness",
        "send_message",
    ]
    assert evidence["observations"][-1]["metadata"]["failure_kind"] == ("contact_not_found")


def test_manual_wechat_desktop_tool_smoke_preserves_unverified_submit_attempt(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeSendUnverifiedWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient)
    monkeypatch.setattr(
        smoke,
        "PackageWeChatDesktopTool",
        _FakeSendUnverifiedWeChatDesktopTool,
    )
    evidence_path = tmp_path / "unknown.json"

    exit_code = smoke.main(
        _managed_submit_args(
            tmp_path,
            db_path=tmp_path / "tool-effects.sqlite",
            evidence_name=evidence_path.name,
        )
    )

    assert exit_code == 1
    assert _FakeSendUnverifiedWeChatDesktopTool.operations == ["send_message"]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["submitAttempted"] is True
    assert evidence["submitted"] is True
    assert evidence["replayed"] is False
    assert evidence["observations"][-1]["status"] == "unknown"
    assert evidence["observations"][-1]["metadata"]["send_boundary"]["state"] == ("unknown")


def test_manual_wechat_desktop_tool_smoke_replay_only_does_not_call_package_again(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient)
    monkeypatch.setattr(smoke, "PackageWeChatDesktopTool", _FakeWeChatDesktopTool)
    db_path = tmp_path / "tool-effects.sqlite"

    first_exit = smoke.main(
        _managed_submit_args(
            tmp_path,
            db_path=db_path,
            evidence_name="first.json",
        )
    )
    replay_exit = smoke.main(
        [
            *_managed_submit_args(
                tmp_path,
                db_path=db_path,
                evidence_name="replay.json",
            ),
            "--replay-only",
        ]
    )

    assert first_exit == 0
    assert replay_exit == 0
    assert _FakeWeChatDesktopTool.operations == ["send_message"]
    replay = json.loads((tmp_path / "replay.json").read_text(encoding="utf-8"))
    assert replay["replayed"] is True
    assert replay["submitAttempted"] is False
    assert replay["submitted"] is False
    assert replay["observations"][-1]["metadata"]["send_boundary"]["replayed"] is True


def test_manual_wechat_desktop_tool_smoke_replay_only_requires_existing_record(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient)
    monkeypatch.setattr(smoke, "PackageWeChatDesktopTool", _FakeWeChatDesktopTool)

    exit_code = smoke.main(
        [
            *_managed_submit_args(
                tmp_path,
                db_path=tmp_path / "missing.sqlite",
                evidence_name="missing.json",
            ),
            "--replay-only",
        ]
    )

    assert exit_code == 2
    assert _FakeWeChatDesktopTool.operations == []
    evidence = json.loads((tmp_path / "missing.json").read_text(encoding="utf-8"))
    assert evidence["submitAttempted"] is False
    assert evidence["submitted"] is False
    assert evidence["observations"][-1]["failure_kind"] == ("managed_send_precondition_failed")


def test_manual_wechat_desktop_tool_smoke_requires_contact_selection_mode(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _FakeWeChatDesktopTool.operations = []
    _FakeUnixSocketServiceClient.operations = []
    monkeypatch.setattr(smoke, "UnixSocketServiceClient", _FakeUnixSocketServiceClient)
    monkeypatch.setattr(smoke, "PackageWeChatDesktopTool", _FakeWeChatDesktopTool)
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
    assert evidence["observations"][-1]["failure_kind"] == ("contact_selection_not_authorized")


def _successful_observation(command: ToolCommand) -> ToolObservation:
    return ToolObservation(
        command_id=command.command_id,
        tool=command.tool,
        operation=command.operation,
        status="ok",
        success=True,
        summary=f"{command.operation} ok",
        observation={
            "operation": command.operation,
            "sendAttempted": command.operation == "send_message",
        },
        evidence={},
        timing={},
        metadata={},
    )


def _managed_submit_args(
    tmp_path: Path,
    *,
    db_path: Path,
    evidence_name: str,
) -> list[str]:
    return [
        "--message",
        "hello",
        "--token",
        "local-token",
        "--allow-focus-select",
        "--allow-submit",
        "--confirm-submit",
        "SEND",
        "--effect-db",
        str(db_path),
        "--session-id",
        "session-1",
        "--task-id",
        "task-1",
        "--smoke-id",
        evidence_name.removesuffix(".json"),
        "--evidence-output",
        str(tmp_path / evidence_name),
    ]
