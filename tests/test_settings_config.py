"""Tests for Product 1.0 Settings config read/write gateway."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from taskweavn.server.settings_config import (
    DefaultSettingsConfigGateway,
    FileSettingsConfigStore,
    SettingsConfigValidationError,
)


def test_settings_config_summary_returns_safe_defaults(tmp_path: Path) -> None:
    gateway = DefaultSettingsConfigGateway(workspace_root=tmp_path, env={})

    summary = gateway.get_config()

    assert summary["schemaVersion"] == "plato.settings_config.v1"
    assert summary["llm"]["provider"] == "litellm"
    assert summary["llm"]["providerSource"] == "default"
    assert summary["llm"]["modelSource"] == "default"
    assert summary["llm"]["apiKeyConfigured"] is False
    assert summary["llm"]["apiKeySource"] == "none"
    assert summary["llm"]["apiKeyEnvVar"] == "LLM_API_KEY"
    assert {"litellm", "deepseek", "openrouter"} == {
        option["id"] for option in summary["llm"]["providerOptions"]
    }
    assert summary["logging"]["selectedProfileKnown"] is True
    assert "sk-" not in json.dumps(summary)


def test_settings_config_update_persists_write_only_secret_and_refreshes_readiness(
    tmp_path: Path,
) -> None:
    secret = "sk-settings-config-secret"
    gateway = DefaultSettingsConfigGateway(workspace_root=tmp_path, env={})

    result = gateway.update_config(
        {
            "llm": {
                "provider": "openrouter",
                "model": "openrouter/test-model",
                "apiKey": secret,
            },
            "logging": {"selectedProfile": "normal"},
        }
    )

    serialized = json.dumps(result)
    store = FileSettingsConfigStore(tmp_path)
    assert result["schemaVersion"] == "plato.settings_config_update.v1"
    assert result["config"]["llm"]["provider"] == "openrouter"
    assert result["config"]["llm"]["providerSource"] == "stored"
    assert result["config"]["llm"]["apiKeyConfigured"] is True
    assert result["config"]["llm"]["apiKeySource"] == "stored"
    assert result["config"]["llm"]["apiKeyEnvVar"] == "OPENROUTER_API_KEY"
    assert result["config"]["logging"]["selectedProfile"] == "normal"
    assert result["readiness"]["status"] == "ready"
    assert result["readiness"]["llm"]["provider"] == "openrouter"
    assert result["readiness"]["llm"]["apiKeyConfigured"] is True
    assert secret not in serialized
    assert secret not in store.config_path.read_text(encoding="utf-8")
    assert secret in store.secrets_path.read_text(encoding="utf-8")


def test_settings_config_blank_api_key_keeps_existing_secret(tmp_path: Path) -> None:
    gateway = DefaultSettingsConfigGateway(workspace_root=tmp_path, env={})
    gateway.update_config(
        {
            "llm": {
                "provider": "litellm",
                "model": "anthropic/initial",
                "apiKey": "sk-existing-secret",
            }
        }
    )

    result = gateway.update_config(
        {
            "llm": {
                "provider": "litellm",
                "model": "anthropic/updated",
                "apiKey": "",
            }
        }
    )

    assert result["config"]["llm"]["model"] == "anthropic/updated"
    assert result["config"]["llm"]["apiKeyConfigured"] is True
    assert result["readiness"]["status"] == "ready"
    assert "sk-existing-secret" not in json.dumps(result)


def test_settings_config_rejects_missing_api_key_without_leaking_input(
    tmp_path: Path,
) -> None:
    gateway = DefaultSettingsConfigGateway(workspace_root=tmp_path, env={})

    with pytest.raises(SettingsConfigValidationError) as exc_info:
        gateway.update_config(
            {
                "llm": {
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "apiKey": "",
                }
            }
        )

    api_error = exc_info.value.to_api_error().model_dump(mode="json")
    serialized = json.dumps(api_error)
    assert api_error["code"] == "bad_request"
    assert api_error["details"]["productCategory"] == "llm_auth_or_config"
    assert api_error["details"]["recoveryActions"] == [
        "open_settings",
        "export_diagnostics",
    ]
    assert api_error["details"]["fieldErrors"] == [
        {
            "path": "llm.apiKey",
            "message": "an API key is required for the selected provider",
            "envVars": ["DEEPSEEK_API_KEY", "LLM_API_KEY"],
        }
    ]
    assert "apiKey" in serialized
    assert "deepseek-chat" not in serialized


def test_settings_config_rejects_unsupported_provider_without_secret_echo(
    tmp_path: Path,
) -> None:
    gateway = DefaultSettingsConfigGateway(workspace_root=tmp_path, env={})

    with pytest.raises(SettingsConfigValidationError) as exc_info:
        gateway.update_config(
            {
                "llm": {
                    "provider": "unsupported",
                    "model": "test-model",
                    "apiKey": "sk-do-not-echo",
                }
            }
        )

    api_error = exc_info.value.to_api_error().model_dump(mode="json")
    assert api_error["details"]["fieldErrors"][0] == {
        "path": "llm.provider",
        "message": "unsupported provider",
        "allowedValues": ["litellm", "deepseek", "openrouter"],
    }
    assert "sk-do-not-echo" not in json.dumps(api_error)


def test_settings_config_rejects_unknown_logging_profile(tmp_path: Path) -> None:
    gateway = DefaultSettingsConfigGateway(
        workspace_root=tmp_path,
        env={"LLM_API_KEY": "sk-env-secret"},
    )

    with pytest.raises(SettingsConfigValidationError) as exc_info:
        gateway.update_config({"logging": {"selectedProfile": "missing-profile"}})

    field_error = exc_info.value.to_api_error().details["fieldErrors"][0]
    assert field_error["path"] == "logging.selectedProfile"
    assert field_error["message"] == "unknown logging profile"
    assert "normal" in field_error["allowedValues"]
