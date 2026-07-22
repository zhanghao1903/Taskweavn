from __future__ import annotations

import json
import signal
import subprocess
from typing import Any

import pytest

from taskweavn.server.settings_recovery_actions import (
    MACOS_ACCESSIBILITY_SETTINGS_URL,
    SettingsRecoveryActionExecutor,
    SettingsRecoveryActionFailed,
    SettingsRecoveryActionUnsupported,
)


def test_settings_recovery_action_opens_macos_accessibility_pane() -> None:
    calls: list[list[str]] = []

    def runner(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        assert kwargs["check"] is True
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["timeout"] == 5
        return subprocess.CompletedProcess(args=args, returncode=0)

    result = SettingsRecoveryActionExecutor(
        runner=runner,
        platform_system=lambda: "Darwin",
    ).execute("open_macos_privacy_accessibility")

    assert calls == [["/usr/bin/open", MACOS_ACCESSIBILITY_SETTINGS_URL]]
    assert result["schemaVersion"] == "plato.settings_recovery_action.v1"
    assert result["action"] == "open_macos_privacy_accessibility"
    assert result["status"] == "opened"


def test_settings_recovery_action_rejects_non_allowlisted_actions() -> None:
    with pytest.raises(SettingsRecoveryActionUnsupported):
        SettingsRecoveryActionExecutor(
            runner=_never_called,
            platform_system=lambda: "Darwin",
        ).execute("erase_disk")


def test_settings_recovery_action_restarts_matching_helper_manifest(tmp_path) -> None:
    manifest_path = tmp_path / "computer-use-helper.json"
    manifest_path.write_text(
        json.dumps(
            {
                "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
                "endpoint": "http://127.0.0.1:50814",
                "pid": 12345,
            }
        ),
        encoding="utf-8",
    )
    calls: list[tuple[int, int]] = []

    def kill_process(pid: int, sig: int) -> None:
        calls.append((pid, sig))
        if sig == 0:
            raise ProcessLookupError

    result = SettingsRecoveryActionExecutor(
        runner=_never_called,
        platform_system=lambda: "Darwin",
        helper_manifest_path=manifest_path,
        kill_process=kill_process,
        sleep=lambda _seconds: None,
    ).execute("restart_helper")

    assert calls == [(12345, signal.SIGTERM), (12345, 0)]
    assert result["schemaVersion"] == "plato.settings_recovery_action.v1"
    assert result["action"] == "restart_helper"
    assert result["status"] == "restarted"
    assert result["bundleId"] == "com.taskweavn.plato.computer-use-helper.dev"
    assert result["pid"] == 12345
    assert result["reason"] == "sigterm_sent"
    assert result["terminated"] is True
    assert result["waitedForExit"] is True


def test_settings_recovery_action_restart_is_idempotent_for_stale_pid(
    tmp_path,
) -> None:
    manifest_path = tmp_path / "computer-use-helper.json"
    manifest_path.write_text(
        json.dumps(
            {
                "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
                "endpoint": "http://127.0.0.1:50814",
                "pid": 12345,
            }
        ),
        encoding="utf-8",
    )

    def kill_process(pid: int, sig: int) -> None:
        assert (pid, sig) == (12345, signal.SIGTERM)
        raise ProcessLookupError

    result = SettingsRecoveryActionExecutor(
        runner=_never_called,
        platform_system=lambda: "Darwin",
        helper_manifest_path=manifest_path,
        kill_process=kill_process,
    ).execute("restart_helper")

    assert result["status"] == "restarted"
    assert result["reason"] == "process_not_found"
    assert result["terminated"] is False
    assert result["waitedForExit"] is False


def test_settings_recovery_action_restart_rejects_mismatched_bundle(
    tmp_path,
) -> None:
    manifest_path = tmp_path / "computer-use-helper.json"
    manifest_path.write_text(
        json.dumps(
            {
                "bundleId": "com.example.OtherApp",
                "endpoint": "http://127.0.0.1:50814",
                "pid": 12345,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SettingsRecoveryActionFailed):
        SettingsRecoveryActionExecutor(
            runner=_never_called,
            platform_system=lambda: "Darwin",
            helper_manifest_path=manifest_path,
            kill_process=_kill_never_called,
        ).execute("restart_helper")


def test_settings_recovery_action_rejects_non_macos_platforms() -> None:
    with pytest.raises(SettingsRecoveryActionUnsupported):
        SettingsRecoveryActionExecutor(
            runner=_never_called,
            platform_system=lambda: "Linux",
        ).execute("open_macos_privacy_accessibility")


def test_settings_recovery_action_reports_open_failures() -> None:
    def runner(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=1, cmd=args)

    with pytest.raises(SettingsRecoveryActionFailed):
        SettingsRecoveryActionExecutor(
            runner=runner,
            platform_system=lambda: "Darwin",
        ).execute("open_macos_privacy_accessibility")


def _never_called(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
    raise AssertionError("runner should not be called")


def _kill_never_called(*args: object, **kwargs: object) -> None:
    raise AssertionError("kill_process should not be called")
