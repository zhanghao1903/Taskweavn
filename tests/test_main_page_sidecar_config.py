"""Tests for Main Page sidecar configuration and settings routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest

from taskweavn.server import (
    DEFAULT_PLATO_SIDECAR_PORT,
    MainPageSidecarConfig,
    WorkspaceRegistryEntry,
)
from tests.fixtures.main_page_sidecar_app import (
    _AgentLoopLLM,
    _build_stubbed_sidecar_app,
    _create_session,
    _request,
)
from tests.fixtures.sidecar_smoke import build_audit_sidecar_smoke_fixture


def test_main_page_sidecar_config_uses_stable_dev_port_by_default(
    tmp_path: Any,
) -> None:
    config = MainPageSidecarConfig(workspace_root=tmp_path)

    assert config.port == DEFAULT_PLATO_SIDECAR_PORT


def test_main_page_sidecar_exposes_effective_runtime_config(
    tmp_path: Any,
) -> None:
    app = _build_stubbed_sidecar_app(
        tmp_path,
        default_agent_max_steps=7,
        context_checkpoint_interval_steps=4,
        context_max_prior_messages=12,
        context_budget_max_events=11,
        enable_execution_dispatcher=False,
        execution_dispatcher_max_ticks_per_trigger=3,
        enable_read_only_inquiry_llm=False,
        enable_computer_use_tool=True,
        computer_use_backend_name="macos",
        computer_use_allowed_apps=("WeChat", "TextEdit"),
        logging_level="DEBUG",
    )
    try:
        response = _request(app, "GET", "/api/v1/runtime/config/effective")
    finally:
        app.close()

    assert response.status == 200
    assert response.json["ok"] is True
    values = response.json["data"]["values"]
    assert values["agent_loop.default_max_steps"]["value"] == 7
    assert values["agent_loop.default_max_steps"]["source"]["kind"] == "process_input"
    assert values["context_manager.checkpoint_interval_steps"]["value"] == 4
    assert values["context_manager.max_prior_messages"]["value"] == 12
    assert values["context_manager.budget.max_events"]["value"] == 11
    assert values["execution_dispatcher.enabled"]["value"] is False
    assert values["execution_dispatcher.max_ticks_per_trigger"]["value"] == 3
    assert values["read_only_inquiry.llm_enabled"]["value"] is False
    assert values["computer_use.enabled"]["value"] is True
    assert values["computer_use.backend"]["value"] == "macos"
    assert values["computer_use.allowed_apps"]["value"] == ["WeChat", "TextEdit"]
    assert values["logging.level"]["value"] == "DEBUG"


def test_main_page_sidecar_runtime_config_patch_route_persists_change(
    tmp_path: Any,
) -> None:
    app = _build_stubbed_sidecar_app(
        tmp_path,
        current_workspace_id="workspace-1",
    )
    try:
        patch = _request(
            app,
            "PATCH",
            "/api/v1/runtime/config",
            body={
                "idempotencyKey": "main-page-runtime-config-write",
                "scope": {
                    "level": "workspace",
                    "workspaceId": "workspace-1",
                },
                "values": {"logging.level": "DEBUG"},
            },
        )
        changes = _request(
            app,
            "GET",
            "/api/v1/runtime/config/changes?workspaceId=workspace-1",
        )
    finally:
        app.close()

    assert patch.status == 200
    assert patch.json["ok"] is True
    assert patch.json["data"]["change"]["status"] == "accepted"
    assert patch.json["data"]["snapshotRef"]["configHash"] == (
        patch.json["data"]["change"]["resultingConfigHash"]
    )
    assert changes.status == 200
    assert changes.json["ok"] is True
    assert changes.json["data"]["totalCount"] == 1
    assert changes.json["data"]["changes"][0]["idempotencyKey"] == (
        "main-page-runtime-config-write"
    )


def test_main_page_sidecar_uses_guarded_llm_inquiry_provider_by_default(
    tmp_path: Any,
) -> None:
    llm = _AgentLoopLLM("{}")
    app = _build_stubbed_sidecar_app(tmp_path, llm=llm)
    try:
        session_id = _create_session(app)
        llm.final_answer = json.dumps(
            {
                "status": "answered",
                "body": "The LLM provider rendered this read-only answer.",
                "confidence": "high",
                "citedRefIds": [f"session:{session_id}:status"],
            }
        )

        response = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/runtime-input/route",
            body={
                "commandId": "route-llm-inquiry",
                "sessionId": session_id,
                "content": "What is this session doing?",
                "mode": "ask",
                "selection": {"scopeKind": "session"},
            },
        )
    finally:
        app.close()

    assert response.status == 200
    assert response.json["ok"] is True
    assert response.json["data"]["outcome"]["status"] == "answered"
    assert response.json["data"]["outcome"]["userMessage"] == (
        "The LLM provider rendered this read-only answer."
    )
    assert response.json["data"]["inquiryResult"]["answer"]["body"] == (
        "The LLM provider rendered this read-only answer."
    )
    assert llm.calls[-1]["tools"] is None
    assert llm.calls[-1]["metadata"]["feature"] == "read_only_inquiry"


def test_main_page_sidecar_can_disable_guarded_llm_inquiry_provider(
    tmp_path: Any,
) -> None:
    llm = _AgentLoopLLM("{}")
    app = _build_stubbed_sidecar_app(
        tmp_path,
        llm=llm,
        enable_read_only_inquiry_llm=False,
    )
    try:
        session_id = _create_session(app)
        response = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/runtime-input/route",
            body={
                "commandId": "route-deterministic-inquiry",
                "sessionId": session_id,
                "content": "What is this session doing?",
                "mode": "ask",
                "selection": {"scopeKind": "session"},
            },
        )
    finally:
        app.close()

    assert response.status == 200
    assert response.json["ok"] is True
    assert response.json["data"]["outcome"]["status"] == "answered"
    assert response.json["data"]["inquiryResult"]["answer"]["body"] == (
        "Session 'Demo session' is new."
    )
    assert app.runtime_config.values["read_only_inquiry.llm_enabled"].value is False
    assert llm.calls == []


def test_main_page_sidecar_app_exposes_settings_readiness_without_secret(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "litellm")
    monkeypatch.setenv("LLM_API_KEY", "sk-sidecar-readiness-secret")
    monkeypatch.setenv("LLM_MODEL", "deepseek-v4-pro")

    app = _build_stubbed_sidecar_app(tmp_path)
    try:
        response = _request(app, "GET", "/api/v1/settings/readiness")
    finally:
        app.close()

    profile_ids = {profile["id"] for profile in response.json["data"]["logging"]["profiles"]}
    assert response.status == 200
    assert response.json["ok"] is True
    assert response.json["data"]["schemaVersion"] == "plato.settings_readiness.v1"
    assert response.json["data"]["status"] == "ready"
    assert response.json["data"]["llm"]["apiKeyConfigured"] is True
    assert response.json["data"]["diagnostics"]["bundleExportAvailable"] is True
    assert response.json["data"]["diagnostics"]["httpExportRouteAvailable"] is True
    assert "normal" in profile_ids
    assert "sk-sidecar-readiness-secret" not in response.text


def test_main_page_sidecar_app_saves_settings_config_and_refreshes_readiness(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_API_KEY",
        "DEEPSEEK_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    secret = "sk-sidecar-settings-secret"

    app = _build_stubbed_sidecar_app(tmp_path)
    try:
        initial = _request(app, "GET", "/api/v1/settings/readiness")
        saved = _request(
            app,
            "PATCH",
            "/api/v1/settings/config",
            body={
                "llm": {
                    "provider": "deepseek",
                    "model": "deepseek-v4-pro",
                    "apiKey": secret,
                },
                "logging": {"selectedProfile": "normal"},
            },
        )
        config = _request(app, "GET", "/api/v1/settings/config")
        readiness = _request(app, "GET", "/api/v1/settings/readiness")
    finally:
        app.close()

    assert initial.status == 200
    assert initial.json["data"]["status"] == "needs_configuration"
    assert saved.status == 200
    assert saved.json["data"]["schemaVersion"] == "plato.settings_config_update.v1"
    assert saved.json["data"]["config"]["llm"]["apiKeyConfigured"] is True
    assert saved.json["data"]["config"]["llm"]["apiKeySource"] == "stored"
    assert saved.json["data"]["readiness"]["status"] == "ready"
    assert config.json["data"]["schemaVersion"] == "plato.settings_config.v1"
    assert config.json["data"]["llm"]["model"] == "deepseek-v4-pro"
    assert config.json["data"]["logging"]["selectedProfile"] == "normal"
    assert readiness.json["data"]["status"] == "ready"
    assert readiness.json["data"]["firstRun"]["ready"] is True
    combined_text = saved.text + config.text + readiness.text
    assert secret not in combined_text
    assert secret not in (
        tmp_path / ".plato" / "settings" / "config.json"
    ).read_text(encoding="utf-8")


def test_main_page_sidecar_app_saves_settings_config_to_global_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_API_KEY",
        "DEEPSEEK_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    workspace_root = tmp_path / "workspace"
    global_settings_root = tmp_path / "plato-user-data"
    secret = "sk-global-settings-secret"

    app = _build_stubbed_sidecar_app(
        workspace_root,
        global_settings_root=global_settings_root,
    )
    try:
        saved = _request(
            app,
            "PATCH",
            "/api/v1/settings/config",
            body={
                "llm": {
                    "provider": "deepseek",
                    "model": "deepseek-v4-pro",
                    "apiKey": secret,
                }
            },
        )
        readiness = _request(app, "GET", "/api/v1/settings/readiness")
    finally:
        app.close()

    global_config = global_settings_root / "settings" / "config.json"
    global_secret = global_settings_root / "settings" / "secrets.json"
    workspace_settings_dir = workspace_root / ".plato" / "settings"
    assert saved.status == 200
    assert saved.json["data"]["config"]["llm"]["apiKeySource"] == "stored"
    assert readiness.json["data"]["status"] == "ready"
    assert global_config.is_file()
    assert global_secret.is_file()
    assert secret not in global_config.read_text(encoding="utf-8")
    assert secret in global_secret.read_text(encoding="utf-8")
    assert not workspace_settings_dir.exists()


def test_audit_sidecar_smoke_fixture_can_force_first_run_unconfigured(
    tmp_path: Any,
) -> None:
    fixture = build_audit_sidecar_smoke_fixture(
        tmp_path,
        settings_readiness_env={},
    )
    try:
        response = fixture.request("GET", "/api/v1/settings/readiness")
    finally:
        fixture.close()

    assert response.status == 200
    assert response.json["ok"] is True
    assert response.json["data"]["status"] == "needs_configuration"
    assert response.json["data"]["firstRun"]["ready"] is False
    assert response.json["data"]["llm"]["provider"] == "deepseek"
    assert response.json["data"]["llm"]["missingEnvVars"] == [
        "DEEPSEEK_API_KEY",
        "LLM_API_KEY",
    ]
    assert response.json["data"]["blockingIssues"][0]["code"] == "llm.missing_api_key"


def test_audit_sidecar_smoke_fixture_can_force_first_run_configured(
    tmp_path: Any,
) -> None:
    fixture = build_audit_sidecar_smoke_fixture(
        tmp_path,
        settings_readiness_env={
            "LLM_PROVIDER": "deepseek",
            "LLM_MODEL": "deepseek-v4-pro",
            "DEEPSEEK_API_KEY": "test-sidecar-readiness-key",
        },
    )
    try:
        response = fixture.request("GET", "/api/v1/settings/readiness")
    finally:
        fixture.close()

    assert response.status == 200
    assert response.json["ok"] is True
    assert response.json["data"]["status"] == "ready"
    assert response.json["data"]["firstRun"]["ready"] is True
    assert response.json["data"]["llm"]["provider"] == "deepseek"
    assert response.json["data"]["llm"]["missingEnvVars"] == []
    assert "test-sidecar-readiness-key" not in response.text


def test_audit_sidecar_smoke_fixture_uses_workspace_registry_id(
    tmp_path: Any,
) -> None:
    fixture = build_audit_sidecar_smoke_fixture(
        tmp_path,
        workspace_registry=(
            WorkspaceRegistryEntry(
                workspace_id="workspace-smoke",
                root_path=tmp_path,
                label="Smoke workspace",
                is_current=True,
            ),
        ),
    )
    try:
        diff = fixture.request(
            "GET",
            (
                f"/api/v1/workspaces/{quote(fixture.workspace_id, safe='')}"
                f"/inspection/diff?path={quote(fixture.inspection_file_path, safe='')}"
            ),
        )
        stale_current = fixture.request(
            "GET",
            (
                "/api/v1/workspaces/current/inspection/diff?"
                f"path={quote(fixture.inspection_file_path, safe='')}"
            ),
        )
    finally:
        fixture.close()

    assert fixture.workspace_id == "workspace-smoke"
    assert diff.status == 200
    assert "Workspace inspection seeded change." in diff.text
    assert stale_current.status == 404
