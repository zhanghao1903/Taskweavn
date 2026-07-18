"""Tests for the Plato adapter over the published app-control package suite."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app_control_protocol import ToolCommand, ToolEvent, ToolObservation

from taskweavn.integrations.app_control import (
    AppControlClientFactoryConfig,
    build_app_control_config,
)
from taskweavn.observability import (
    build_disabled_logging_config,
    build_session_logging_config,
    get_logging_manager,
)
from taskweavn.tools import MacOSComputerUseBackend
from taskweavn.types import ComputerUseAction


@dataclass
class FakeProtocolClient:
    next_observation: ToolObservation = field(
        default_factory=lambda: ToolObservation(
            command_id="cmd_default",
            tool="macos.computer_use",
            operation="observe",
            status="ok",
            success=True,
            summary="Observed frontmost app.",
            observation={
                "textExtract": "Frontmost app: TextEdit.",
                "snapshotId": "frontmost:TextEdit:Untitled",
                "frontmostApp": "TextEdit",
            },
            metadata={"frontmost_app": "TextEdit"},
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
                    data={"accessibilityTree": "raw tree should stay out of logs"},
                )
            )
        return self.next_observation


def test_build_app_control_config_maps_runtime_settings() -> None:
    config = build_app_control_config(
        AppControlClientFactoryConfig(
            backend="helper",
            allowed_apps=("WeChat",),
            allowed_app_bundle_ids={"WeChat": "com.tencent.xinWeChat"},
            helper_bundle_id="com.taskweavn.plato.computer-use-helper",
            helper_endpoint="/tmp/plato-helper.sock",
            helper_token="token-1",
            helper_auto_launch=True,
        )
    )

    assert config.computer_use.backend == "helper"
    assert config.computer_use.allowed_apps == ("WeChat",)
    assert config.computer_use.allowed_app_bundle_ids == {
        "WeChat": "com.tencent.xinWeChat"
    }
    assert config.helper.bundle_id == "com.taskweavn.plato.computer-use-helper"
    assert config.helper.endpoint == "/tmp/plato-helper.sock"
    assert config.helper.token == "token-1"
    assert config.helper.auto_launch is True


def test_macos_backend_reports_package_missing_as_not_available() -> None:
    backend = MacOSComputerUseBackend(client=None)
    backend._client = None  # force deterministic package-missing behavior
    backend._import_error = "ModuleNotFoundError: test"

    observation = backend.execute(
        ComputerUseAction(operation="observe", instruction="Inspect app.")
    )

    assert observation.success is False
    assert observation.status == "not_available"
    assert observation.operation == "observe"
    assert "package is not available" in observation.summary


def test_macos_backend_maps_ready_readiness_to_ok_observation() -> None:
    client = FakeProtocolClient(
        ToolObservation(
            command_id="cmd_ready",
            tool="macos.computer_use",
            operation="readiness",
            status="ok",
            success=True,
            summary="ready",
            observation={
                "status": "ready",
                "permissions": {"accessibility": True},
                "enabledOperations": ["observe", "open_app"],
            },
        )
    )
    backend = MacOSComputerUseBackend(client=client)

    observation = backend.execute(
        ComputerUseAction(operation="readiness", instruction="Check readiness.")
    )

    assert observation.success is True
    assert observation.status == "ok"
    assert observation.operation == "readiness"
    assert observation.metadata["observation"]["status"] == "ready"
    assert observation.metadata["protocol"]["tool"] == "macos.computer_use"
    diagnostics = observation.metadata["diagnostics"]
    assert diagnostics["checkedByProcessPath"]
    assert diagnostics["adapterProcessExecutable"]
    assert diagnostics["adapterArgv0"]
    assert diagnostics["packageClientClass"].endswith(".FakeProtocolClient")
    assert client.commands[0].operation == "readiness"


def test_macos_backend_maps_permission_missing_to_needs_user() -> None:
    client = FakeProtocolClient(
        ToolObservation(
            command_id="cmd_ready",
            tool="macos.computer_use",
            operation="readiness",
            status="permission_missing",
            success=False,
            summary="Accessibility permission is missing.",
            failure_kind="missing_accessibility",
            message="Accessibility permission is missing.",
            recovery_hint="Grant Accessibility to the helper app.",
            retryable=True,
        )
    )
    backend = MacOSComputerUseBackend(client=client)

    observation = backend.readiness()

    assert observation.success is False
    assert observation.status == "needs_user"
    assert observation.metadata["failure_kind"] == "missing_accessibility"
    assert observation.metadata["recovery_hint"] == "Grant Accessibility to the helper app."
    assert observation.metadata["retryable"] is True


def test_macos_backend_maps_observe_result_metadata() -> None:
    client = FakeProtocolClient()
    backend = MacOSComputerUseBackend(client=client)
    action = ComputerUseAction(
        operation="observe",
        instruction="Inspect TextEdit.",
        target="TextEdit",
    )

    observation = backend.execute(action)

    command = client.commands[0]
    assert command.operation == "observe"
    assert command.input == {"targetApp": "TextEdit"}
    assert observation.action_id == action.event_id
    assert observation.success is True
    assert observation.status == "ok"
    assert observation.text_extract == "Frontmost app: TextEdit."
    assert observation.metadata["snapshot_id"] == "frontmost:TextEdit:Untitled"
    assert observation.metadata["package_metadata"]["frontmost_app"] == "TextEdit"
    assert observation.metadata["tool_events"][0]["phase"] == "observe.test"
    assert observation.metadata["tool_events"][0]["dataKeys"] == ["accessibilityTree"]


def test_macos_backend_builds_protocol_commands_for_core_operations() -> None:
    client = FakeProtocolClient()
    backend = MacOSComputerUseBackend(client=client)

    backend.execute(
        ComputerUseAction(
            operation="open_app",
            instruction="Open TextEdit.",
            target="TextEdit",
            timeout_seconds=7,
            metadata={"bundle_id": "com.apple.TextEdit"},
        )
    )
    backend.execute(
        ComputerUseAction(
            operation="focus_app",
            instruction="Focus WeChat.",
            target="WeChat",
            timeout_seconds=7,
            metadata={"bundle_id": "com.tencent.xinWeChat"},
        )
    )
    backend.execute(
        ComputerUseAction(
            operation="accessibility_query",
            instruction="Query focused WeChat window.",
            target="WeChat",
            timeout_seconds=6,
            metadata={
                "bundle_id": "com.tencent.xinWeChat",
                "root": {"kind": "focusedWindow"},
                "query": {"scope": "children", "limit": 5},
                "include_raw": False,
            },
        )
    )
    backend.execute(
        ComputerUseAction(
            operation="type_text",
            instruction="Type text.",
            text="hello",
            metadata={"target_app": "TextEdit"},
            timeout_seconds=3,
        )
    )
    backend.execute(
        ComputerUseAction(
            operation="click",
            instruction="Click OK.",
            target="OK",
            x=1,
            y=2,
            metadata={
                "target_app": "TextEdit",
                "snapshot_id": "snap-1",
                "selector": {"role": "button", "name": "OK"},
            },
            timeout_seconds=4,
        )
    )
    backend.execute(
        ComputerUseAction(
            operation="press_key",
            instruction="Open search.",
            keys=("command", "f"),
            metadata={"target_app": "TextEdit"},
            timeout_seconds=4,
        )
    )
    backend.execute(
        ComputerUseAction(
            operation="wait",
            instruction="Wait briefly.",
            timeout_seconds=2,
        )
    )

    command_facts = [
        (command.operation, command.input, command.timeout_ms)
        for command in client.commands
    ]
    assert command_facts == [
        (
            "open_app",
            {"app": "TextEdit", "bundleId": "com.apple.TextEdit"},
            7000,
        ),
        (
            "focus_app",
            {"app": "WeChat", "bundleId": "com.tencent.xinWeChat"},
            7000,
        ),
        (
            "accessibility_query",
            {
                "targetApp": "WeChat",
                "bundleId": "com.tencent.xinWeChat",
                "root": {"kind": "focusedWindow"},
                "query": {"scope": "children", "limit": 5},
                "includeRaw": False,
            },
            6000,
        ),
        ("type_text", {"text": "hello", "targetApp": "TextEdit"}, 3000),
        (
            "click",
            {
                "target": "OK",
                "targetApp": "TextEdit",
                "selector": {"role": "button", "name": "OK"},
                "coordinates": [1, 2],
                "snapshotId": "snap-1",
            },
            4000,
        ),
        ("hotkey", {"keys": ["command", "f"], "targetApp": "TextEdit"}, 4000),
        ("wait", {"seconds": 2}, 2000),
    ]


def test_macos_backend_preserves_structured_failure_metadata() -> None:
    client = FakeProtocolClient(
        ToolObservation(
            command_id="cmd_click",
            tool="macos.computer_use",
            operation="click",
            status="timeout",
            success=False,
            summary="Timed out while clicking semantic target.",
            failure_kind="click_timeout",
            message="Timed out while clicking semantic target.",
            recovery_hint="Observe the target app before retrying.",
            retryable=True,
            evidence={
                "phase": "click",
                "lookupAttempted": True,
                "targetResolved": True,
                "clickAttempted": True,
                "postClickObserved": False,
            },
        )
    )
    backend = MacOSComputerUseBackend(client=client)

    observation = backend.execute(
        ComputerUseAction(
            operation="click",
            instruction="Click Send after product confirmation.",
            target="发送",
            metadata={
                "target_app": "WeChat",
                "confirmed_by_user": True,
                "aliases": ["发送", "Send"],
            },
        )
    )

    assert observation.status == "failed"
    assert observation.metadata["failure_kind"] == "click_timeout"
    assert observation.metadata["message"] == "Timed out while clicking semantic target."
    assert observation.metadata["recovery_hint"] == "Observe the target app before retrying."
    assert observation.metadata["retryable"] is True
    assert observation.metadata["evidence"]["clickAttempted"] is True
    command = client.commands[0]
    assert command.operation == "click"
    assert command.input["target"] == "发送"
    assert command.input["targetApp"] == "WeChat"
    assert command.metadata["confirmed_by_user"] is True
    assert command.metadata["aliases"] == ["发送", "Send"]


def test_macos_backend_emits_computer_use_api_logs_without_raw_text(
    tmp_path: Path,
) -> None:
    session_id = "session-computer-use-log"
    log_root = tmp_path / "logs"
    manager = get_logging_manager()
    manager.apply_config(build_session_logging_config(log_root, level="DEBUG"))
    try:
        client = FakeProtocolClient(
            ToolObservation(
                command_id="cmd_type",
                tool="macos.computer_use",
                operation="type_text",
                status="ok",
                success=True,
                summary="Typed text.",
                observation={},
            )
        )
        backend = MacOSComputerUseBackend(client=client)

        backend.execute(
            ComputerUseAction(
                operation="type_text",
                instruction="Type text.",
                text="secret message",
                metadata={
                    "sessionId": session_id,
                    "taskId": "task-1",
                    "executionId": "exec-1",
                    "target_app": "TextEdit",
                },
            )
        )

        runtime_log = log_root / "sessions" / session_id / "runtime.jsonl"
        rows = [
            json.loads(line)
            for line in runtime_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        row = next(item for item in rows if item["event"] == "computer_use_api")
        assert row["context"]["task_id"] == "task-1"
        data = row["data"]
        assert data["schema"] == "plato.runtime_observability.v1"
        assert data["operation"] == "type_text"
        assert data["messageHash"].startswith("sha256:")
        assert data["messageChars"] == 14
        assert data["metadata"]["packageEventCount"] == 1
        assert data["metadata"]["packageEvents"][0]["dataKeys"] == ["accessibilityTree"]
        assert "secret message" not in runtime_log.read_text(encoding="utf-8")
        assert "raw tree should stay out of logs" not in runtime_log.read_text(
            encoding="utf-8"
        )
    finally:
        manager.apply_config(build_disabled_logging_config(tmp_path / "disabled-logs"))
