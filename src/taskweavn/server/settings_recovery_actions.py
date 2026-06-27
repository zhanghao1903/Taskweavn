"""Bounded local Settings recovery actions."""

from __future__ import annotations

import platform
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

SETTINGS_RECOVERY_ACTION_SCHEMA_VERSION = "plato.settings_recovery_action.v1"

MACOS_ACCESSIBILITY_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
)
MACOS_AUTOMATION_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation"
)

_MACOS_SETTINGS_ACTION_URLS = {
    "open_macos_privacy_accessibility": MACOS_ACCESSIBILITY_SETTINGS_URL,
    "open_macos_privacy_automation": MACOS_AUTOMATION_SETTINGS_URL,
}


class SettingsRecoveryActionError(Exception):
    """Base class for local Settings recovery action failures."""


class SettingsRecoveryActionUnsupported(SettingsRecoveryActionError):
    """Raised when a requested recovery action is not executable by this API."""


class SettingsRecoveryActionFailed(SettingsRecoveryActionError):
    """Raised when a bounded recovery action fails at the OS boundary."""


@dataclass(frozen=True)
class SettingsRecoveryActionExecutor:
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
    platform_system: Callable[[], str] = platform.system

    def execute(self, action: str) -> dict[str, object]:
        url = _MACOS_SETTINGS_ACTION_URLS.get(action)
        if url is None:
            raise SettingsRecoveryActionUnsupported(
                f"settings recovery action is not executable: {action}"
            )

        if self.platform_system() != "Darwin":
            raise SettingsRecoveryActionUnsupported(
                f"settings recovery action requires macOS: {action}"
            )

        try:
            result = self.runner(
                ["/usr/bin/open", url],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise SettingsRecoveryActionFailed(
                f"failed to open macOS settings for action: {action}"
            ) from exc

        return {
            "schemaVersion": SETTINGS_RECOVERY_ACTION_SCHEMA_VERSION,
            "action": action,
            "status": "opened",
            "summary": "Opened macOS System Settings.",
            "url": url,
            "returnCode": result.returncode,
        }


def execute_settings_recovery_action(action: str) -> dict[str, object]:
    return SettingsRecoveryActionExecutor().execute(action)


__all__ = [
    "MACOS_ACCESSIBILITY_SETTINGS_URL",
    "MACOS_AUTOMATION_SETTINGS_URL",
    "SETTINGS_RECOVERY_ACTION_SCHEMA_VERSION",
    "SettingsRecoveryActionExecutor",
    "SettingsRecoveryActionFailed",
    "SettingsRecoveryActionUnsupported",
    "execute_settings_recovery_action",
]
