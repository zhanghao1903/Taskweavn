"""Tests for Settings readiness projection of computer-use backends."""

from __future__ import annotations

from typing import Any

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
                        "apiVersion": "plato.computer_use_helper.v1",
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
        "apiVersion": "plato.computer_use_helper.v1",
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
                    "diagnostics": {
                        "bundle_id": "com.taskweavn.plato.computer-use-helper.dev",
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
    assert computer_use["helper"] == {
        "bundleId": "com.taskweavn.plato.computer-use-helper.dev",
        "path": "/Applications/Plato Computer Use Helper Dev.app",
    }
    assert report["warnings"] == [
        {
            "code": "computer_use.not_ready",
            "severity": "warning",
            "message": "Accessibility permission is missing.",
            "recoveryActions": ["open_settings", "export_diagnostics"],
            "envVars": (),
        }
    ]
    assert "secret" not in computer_use["diagnostics"]
    assert "must-not-leak" not in str(computer_use)
