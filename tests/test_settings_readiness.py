"""Tests for Product 1.0 Settings / first-run readiness."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from taskweavn.server.settings_readiness import (
    DefaultSettingsReadinessGateway,
    build_settings_readiness_report,
)

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def test_missing_default_litellm_key_returns_first_run_blocker(tmp_path: Path) -> None:
    report = build_settings_readiness_report(
        workspace_root=tmp_path,
        env={},
        now=NOW,
    ).to_contract_dict()

    assert report["schemaVersion"] == "plato.settings_readiness.v1"
    assert report["status"] == "needs_configuration"
    assert report["generatedAt"] == "2026-06-05T12:00:00Z"
    assert report["firstRun"] == {
        "ready": False,
        "blockingIssueCodes": ["llm.missing_api_key"],
        "recommendedActions": ["open_settings"],
    }
    assert report["llm"]["provider"] == "litellm"
    assert report["llm"]["providerSource"] == "default"
    assert report["llm"]["configured"] is False
    assert report["llm"]["apiKeyConfigured"] is False
    assert report["llm"]["missingEnvVars"] == ["LLM_API_KEY"]
    assert report["blockingIssues"][0]["recoveryActions"] == ["open_settings"]


def test_configured_litellm_readiness_does_not_expose_secret(tmp_path: Path) -> None:
    report = build_settings_readiness_report(
        workspace_root=tmp_path,
        env={
            "LLM_API_KEY": "sk-super-secret",
            "LLM_MODEL": "anthropic/test-model",
            "LLM_REQUEST_TIMEOUT_SECONDS": "none",
            "LLM_THINKING_ENABLED": "yes",
            "LLM_THINKING_EFFORT": "low",
        },
        now=NOW,
    ).to_contract_dict()

    serialized = json.dumps(report)
    assert report["status"] == "ready"
    assert report["firstRun"]["ready"] is True
    assert report["firstRun"]["recommendedActions"] == ["none"]
    assert report["llm"]["configured"] is True
    assert report["llm"]["apiKeyConfigured"] is True
    assert report["llm"]["missingEnvVars"] == []
    assert report["llm"]["requestTimeoutSeconds"] is None
    assert report["llm"]["requestTimeoutConfigured"] is True
    assert report["llm"]["thinking"] == {
        "configured": True,
        "enabled": True,
        "effort": "low",
    }
    assert "sk-super-secret" not in serialized


def test_invalid_llm_environment_maps_to_blocking_issues(tmp_path: Path) -> None:
    report = build_settings_readiness_report(
        workspace_root=tmp_path,
        env={
            "LLM_PROVIDER": "unsupported-provider",
            "LLM_API_KEY": "sk-test",
            "LLM_MODEL": "",
            "LLM_REQUEST_TIMEOUT_SECONDS": "0",
        },
        now=NOW,
    ).to_contract_dict()

    issue_codes = {issue["code"] for issue in report["blockingIssues"]}
    assert report["status"] == "needs_configuration"
    assert report["llm"]["provider"] == "unsupported-provider"
    assert report["llm"]["configured"] is False
    assert report["llm"]["requestTimeoutValid"] is False
    assert issue_codes == {
        "llm.invalid_provider",
        "llm.invalid_model",
        "llm.invalid_timeout",
    }


def test_logging_profiles_and_diagnostics_are_discoverable(tmp_path: Path) -> None:
    report = build_settings_readiness_report(
        workspace_root=tmp_path,
        env={"LLM_API_KEY": "sk-test"},
        selected_logging_profile="debug-llm",
        now=NOW,
    ).to_contract_dict()

    profile_ids = {profile["id"] for profile in report["logging"]["profiles"]}
    assert report["status"] == "ready"
    assert report["logging"]["enabled"] is True
    assert report["logging"]["selectedProfile"] == "debug-llm"
    assert report["logging"]["selectedProfileKnown"] is True
    assert report["logging"]["defaultProfile"] == "normal"
    assert {"normal", "debug-llm", "full-debug"}.issubset(profile_ids)
    assert report["diagnostics"]["bundleExportAvailable"] is True
    assert report["diagnostics"]["httpExportRouteAvailable"] is True


def test_gateway_uses_injected_env_and_serializes_contract_shape(tmp_path: Path) -> None:
    gateway = DefaultSettingsReadinessGateway(
        workspace_root=tmp_path,
        env={"LLM_API_KEY": "sk-gateway-secret"},
    )

    report = gateway.get_readiness()

    assert report["status"] == "ready"
    assert report["llm"]["apiKeyConfigured"] is True
    assert "sk-gateway-secret" not in json.dumps(report)
