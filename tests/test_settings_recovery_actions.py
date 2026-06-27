from __future__ import annotations

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
