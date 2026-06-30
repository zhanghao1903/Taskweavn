"""Tests for Settings readiness projection of computer-use backends."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from taskweavn.server.computer_use_settings_readiness import (
    ComputerUseSettingsReadinessGateway,
    build_computer_use_settings_readiness,
)
from taskweavn.tools import ScriptedComputerUseBackend
from taskweavn.types import ComputerUseObservation


class _ReadinessSource:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def get_readiness(self) -> dict[str, Any]:
        return dict(self.payload)


def test_computer_use_readiness_is_disabled_without_warning() -> None:
    report = ComputerUseSettingsReadinessGateway(
        inner=_ReadinessSource(
            {
                "schemaVersion": "plato.settings_readiness.v1",
                "status": "ready",
                "warnings": [],
            }
        ),
        enabled=False,
        backend_name="disabled",
    ).get_readiness()

    assert report["status"] == "ready"
    assert report["warnings"] == []
    assert report["computerUse"] == {
        "enabled": False,
        "backend": "disabled",
        "allowedApps": [],
        "ready": False,
        "configured": False,
        "status": "disabled",
        "summary": "Computer-use is disabled.",
        "recoveryActions": [],
    }


def test_computer_use_readiness_reports_ready_backend() -> None:
    backend = ScriptedComputerUseBackend(
        (
            ComputerUseObservation(
                operation="readiness",
                status="ok",
                summary="Helper is ready.",
                metadata={
                    "provider": "helper",
                    "helper_status": "ready",
                    "helper": {
                        "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
                        "version": "0.1.0",
                        "apiVersion": "app_control.helper.v1",
                        "path": "/Applications/Plato Computer Use Helper Dev.app",
                        "signingMode": "development-app",
                        "tokenRef": "must-not-leak",
                    },
                },
            ),
        )
    )

    readiness = build_computer_use_settings_readiness(
        enabled=True,
        backend_name="helper",
        allowed_apps=("WeChat",),
        backend=backend,
    )

    assert readiness["ready"] is True
    assert readiness["configured"] is True
    assert readiness["status"] == "ready"
    assert readiness["backend"] == "helper"
    assert readiness["allowedApps"] == ["WeChat"]
    assert readiness["recoveryActions"] == []
    assert readiness["helper"] == {
        "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
        "version": "0.1.0",
        "apiVersion": "app_control.helper.v1",
        "path": "/Applications/Plato Computer Use Helper Dev.app",
        "signingMode": "development-app",
    }
    assert "must-not-leak" not in str(readiness)
    assert backend.actions[0].operation == "readiness"


def test_computer_use_readiness_degrades_when_enabled_backend_is_not_ready() -> None:
    backend = ScriptedComputerUseBackend(
        (
            ComputerUseObservation(
                operation="readiness",
                success=False,
                status="not_available",
                summary="Accessibility permission is missing.",
                metadata={
                    "provider": "helper",
                    "helper_status": "missing_accessibility",
                    "failure_kind": "missing_accessibility",
                    "setup_hint": "Enable Accessibility for Plato Computer Use Helper.",
                    "readiness": {
                        "status": "missing_accessibility",
                        "accessibility_trusted": False,
                    },
                    "recovery_actions": [
                        "open_macos_privacy_accessibility",
                        "restart_helper",
                        "rerun_readiness_check",
                    ],
                    "diagnostics": {
                        "bundle_id": "com.taskweavn.plato.computer-use-helper.dev",
                        "runtimeIdentity": {
                            "mode": "helper_owned_executable",
                            "effectiveExecutable": (
                                "/Applications/Plato Computer Use Helper Dev.app/"
                                "Contents/MacOS/PlatoComputerUseHelper"
                            ),
                            "token": "must-not-leak",
                        },
                        "helperSignature": {
                            "checked": True,
                            "status": "ok",
                            "appPath": "/Applications/Plato Computer Use Helper Dev.app",
                            "expectedBundleId": (
                                "com.taskweavn.plato.computer-use-helper.dev"
                            ),
                            "identifier": (
                                "com.taskweavn.plato.computer-use-helper.dev"
                            ),
                            "identifierMatchesExpected": True,
                            "infoPlistBound": True,
                            "sealedResources": True,
                            "signature": "adhoc",
                            "teamIdentifier": "not set",
                            "tokenRef": "must-not-leak",
                        },
                        "token": "must-not-leak",
                    },
                    "helper": {
                        "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
                        "path": "/Applications/Plato Computer Use Helper Dev.app",
                        "tokenRef": "must-not-leak",
                    },
                    "secret": "must-not-leak",
                },
            ),
        )
    )

    report = ComputerUseSettingsReadinessGateway(
        inner=_ReadinessSource(
            {
                "schemaVersion": "plato.settings_readiness.v1",
                "status": "ready",
                "warnings": [],
            }
        ),
        enabled=True,
        backend_name="helper",
        allowed_apps=("WeChat",),
        backend=backend,
    ).get_readiness()

    computer_use = report["computerUse"]
    assert report["status"] == "degraded"
    assert computer_use["ready"] is False
    assert computer_use["status"] == "missing_accessibility"
    assert computer_use["helperStatus"] == "missing_accessibility"
    assert computer_use["failureKind"] == "missing_accessibility"
    assert computer_use["setupHint"] == (
        "Enable Accessibility for Plato Computer Use Helper."
    )
    assert computer_use["recoveryActions"] == [
        "open_macos_privacy_accessibility",
        "restart_helper",
        "rerun_readiness_check",
    ]
    assert computer_use["helper"] == {
        "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
        "path": "/Applications/Plato Computer Use Helper Dev.app",
    }
    assert computer_use["permissionSubject"] == {
        "helperBundleId": "com.taskweavn.plato.computer-use-helper.dev",
        "helperAppPath": "/Applications/Plato Computer Use Helper Dev.app",
        "runtimeMode": "helper_owned_executable",
        "effectiveExecutable": (
            "/Applications/Plato Computer Use Helper Dev.app/"
            "Contents/MacOS/PlatoComputerUseHelper"
        ),
        "accessibilityTrusted": False,
        "packageReadinessStatus": "missing_accessibility",
        "helperStatus": "missing_accessibility",
        "signature": {
            "checked": True,
            "status": "ok",
            "appPath": "/Applications/Plato Computer Use Helper Dev.app",
            "expectedBundleId": "com.taskweavn.plato.computer-use-helper.dev",
            "identifier": "com.taskweavn.plato.computer-use-helper.dev",
            "identifierMatchesExpected": True,
            "infoPlistBound": True,
            "sealedResources": True,
            "signature": "adhoc",
            "teamIdentifier": "not set",
        },
        "recoveryActions": [
            "open_macos_privacy_accessibility",
            "restart_helper",
            "rerun_readiness_check",
        ],
        "operatorInstruction": (
            "Grant or refresh macOS Accessibility and Automation permissions "
            "for /Applications/Plato Computer Use Helper Dev.app, restart the "
            "helper, then recheck local computer-use readiness before "
            "publishing a computer-use task."
        ),
    }
    assert report["warnings"] == [
        {
            "code": "computer_use.not_ready",
            "severity": "warning",
            "message": "Accessibility permission is missing.",
            "recoveryActions": [
                "open_macos_privacy_accessibility",
                "restart_helper",
                "rerun_readiness_check",
            ],
            "envVars": (),
        }
    ]
    assert "secret" not in computer_use["diagnostics"]
    assert "must-not-leak" not in str(computer_use)


def test_computer_use_readiness_computes_helper_signature_when_metadata_omits_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "taskweavn.server.computer_use_settings_readiness.sys.platform",
        "darwin",
    )
    monkeypatch.setattr(
        "taskweavn.server.computer_use_settings_readiness.shutil.which",
        lambda name: "/usr/bin/codesign",
    )

    def fake_run(
        args: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        assert args == [
            "/usr/bin/codesign",
            "-dv",
            "--verbose=4",
            "/Applications/Plato Computer Use Helper Dev.app",
        ]
        assert check is False
        assert capture_output is True
        assert text is True
        assert timeout == 10
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="",
            stderr=(
                "Identifier=com.taskweavn.plato.computer-use-helper.dev\n"
                "Info.plist entries=13\n"
                "Sealed Resources version=2 rules=13 files=3\n"
                "Signature=adhoc\n"
                "TeamIdentifier=not set\n"
            ),
        )

    monkeypatch.setattr(
        "taskweavn.server.computer_use_settings_readiness.subprocess.run",
        fake_run,
    )
    backend = ScriptedComputerUseBackend(
        (
            ComputerUseObservation(
                operation="readiness",
                success=False,
                status="not_available",
                summary="Accessibility permission is missing.",
                metadata={
                    "helper_status": "missing_accessibility",
                    "readiness": {
                        "status": "missing_accessibility",
                        "accessibility_trusted": False,
                    },
                    "diagnostics": {
                        "runtimeIdentity": {
                            "mode": "helper_owned_executable",
                            "effectiveExecutable": (
                                "/Applications/Plato Computer Use Helper Dev.app/"
                                "Contents/MacOS/PlatoComputerUseHelper"
                            ),
                        },
                    },
                    "helper": {
                        "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
                        "path": "/Applications/Plato Computer Use Helper Dev.app",
                    },
                },
            ),
        )
    )

    readiness = build_computer_use_settings_readiness(
        enabled=True,
        backend_name="helper",
        backend=backend,
    )

    assert readiness["permissionSubject"]["signature"] == {
        "checked": True,
        "appPath": "/Applications/Plato Computer Use Helper Dev.app",
        "expectedBundleId": "com.taskweavn.plato.computer-use-helper.dev",
        "status": "ok",
        "identifier": "com.taskweavn.plato.computer-use-helper.dev",
        "identifierMatchesExpected": True,
        "infoPlistBound": True,
        "sealedResources": True,
        "signature": "adhoc",
        "teamIdentifier": "not set",
    }
