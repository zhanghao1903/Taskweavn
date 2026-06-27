"""Bounded local Settings recovery actions."""

from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SETTINGS_RECOVERY_ACTION_SCHEMA_VERSION = "plato.settings_recovery_action.v1"
DEFAULT_HELPER_MANIFEST_PATH = Path(
    "~/Library/Application Support/PlatoDev/computer-use-helper.json"
)
DEFAULT_HELPER_BUNDLE_ID = "com.taskweavn.plato.computer-use-helper.dev"

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
    helper_manifest_path: Path = DEFAULT_HELPER_MANIFEST_PATH
    expected_helper_bundle_id: str = DEFAULT_HELPER_BUNDLE_ID
    kill_process: Callable[[int, int], None] = os.kill
    monotonic_clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    helper_restart_wait_seconds: float = 2.0

    def execute(self, action: str) -> dict[str, object]:
        if action == "restart_helper":
            return self._restart_helper()

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

    def _restart_helper(self) -> dict[str, object]:
        if self.platform_system() != "Darwin":
            raise SettingsRecoveryActionUnsupported(
                "settings recovery action requires macOS: restart_helper"
            )

        manifest_path = self.helper_manifest_path.expanduser()
        manifest = _read_helper_manifest(manifest_path)
        bundle_id = _string(manifest.get("bundleId")) or _string(
            manifest.get("bundle_id")
        )
        if bundle_id != self.expected_helper_bundle_id:
            raise SettingsRecoveryActionFailed(
                "refusing to restart helper from mismatched helper manifest"
            )

        pid = _int(manifest.get("pid"))
        if pid is None:
            raise SettingsRecoveryActionFailed(
                "helper manifest does not include a valid pid"
            )

        try:
            self.kill_process(pid, signal.SIGTERM)
        except ProcessLookupError:
            return self._helper_restart_result(
                manifest_path=manifest_path,
                pid=pid,
                bundle_id=bundle_id,
                reason="process_not_found",
                terminated=False,
                waited_for_exit=False,
            )
        except PermissionError as exc:
            raise SettingsRecoveryActionFailed(
                "permission denied while restarting helper"
            ) from exc
        except OSError as exc:
            raise SettingsRecoveryActionFailed("failed to restart helper") from exc

        waited_for_exit = self._wait_for_pid_exit(pid)
        return self._helper_restart_result(
            manifest_path=manifest_path,
            pid=pid,
            bundle_id=bundle_id,
            reason="sigterm_sent",
            terminated=True,
            waited_for_exit=waited_for_exit,
        )

    def _helper_restart_result(
        self,
        *,
        manifest_path: Path,
        pid: int,
        bundle_id: str,
        reason: str,
        terminated: bool,
        waited_for_exit: bool,
    ) -> dict[str, object]:
        return {
            "schemaVersion": SETTINGS_RECOVERY_ACTION_SCHEMA_VERSION,
            "action": "restart_helper",
            "status": "restarted",
            "summary": (
                "Restarted Plato Computer Use Helper. Rerun helper readiness "
                "preflight before publishing a computer-use task."
            ),
            "manifestPath": str(manifest_path),
            "bundleId": bundle_id,
            "pid": pid,
            "reason": reason,
            "terminated": terminated,
            "waitedForExit": waited_for_exit,
        }

    def _wait_for_pid_exit(self, pid: int, poll_interval_seconds: float = 0.1) -> bool:
        deadline = self.monotonic_clock() + max(0.0, self.helper_restart_wait_seconds)
        while True:
            try:
                self.kill_process(pid, 0)
            except ProcessLookupError:
                return True
            except PermissionError:
                return False
            if self.monotonic_clock() >= deadline:
                return False
            self.sleep(poll_interval_seconds)


def _read_helper_manifest(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SettingsRecoveryActionFailed("helper manifest is unavailable") from exc
    if not isinstance(raw, dict):
        raise SettingsRecoveryActionFailed("helper manifest must be a JSON object")
    return raw


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and value > 0 else None


def execute_settings_recovery_action(action: str) -> dict[str, object]:
    return SettingsRecoveryActionExecutor().execute(action)


__all__ = [
    "DEFAULT_HELPER_BUNDLE_ID",
    "DEFAULT_HELPER_MANIFEST_PATH",
    "MACOS_ACCESSIBILITY_SETTINGS_URL",
    "MACOS_AUTOMATION_SETTINGS_URL",
    "SETTINGS_RECOVERY_ACTION_SCHEMA_VERSION",
    "SettingsRecoveryActionExecutor",
    "SettingsRecoveryActionFailed",
    "SettingsRecoveryActionUnsupported",
    "execute_settings_recovery_action",
]
