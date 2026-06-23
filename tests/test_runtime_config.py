from __future__ import annotations

import pytest

from taskweavn.runtime_config import (
    RuntimeConfigKey,
    RuntimeConfigLayer,
    RuntimeConfigRegistry,
    RuntimeConfigRegistryError,
    RuntimeConfigResolverError,
    RuntimeConfigScope,
    RuntimeConfigSource,
    build_default_runtime_config_registry,
    environment_runtime_config_layer,
    process_runtime_config_layer,
    resolve_default_runtime_config,
)


def test_default_runtime_config_registry_contains_first_batch_keys() -> None:
    registry = build_default_runtime_config_registry()

    expected_keys = {
        "agent_loop.default_max_steps",
        "context_manager.checkpoint_interval_steps",
        "context_manager.max_prior_messages",
        "context_manager.budget.max_events",
        "context_manager.budget.max_tool_results",
        "context_manager.budget.max_file_snippets",
        "context_manager.budget.max_file_snippet_chars",
        "context_manager.budget.max_rendered_chars",
        "execution_dispatcher.enabled",
        "execution_dispatcher.max_ticks_per_trigger",
        "task_api.enabled",
        "task_api.require_valid_session",
        "computer_use.enabled",
        "computer_use.backend",
        "computer_use.allowed_apps",
        "computer_use.allow_coordinate_click",
        "computer_use.screen_recording_required",
        "computer_use.max_text_chars",
        "safety.high_risk_confirmation",
        "llm.default_provider",
        "llm.default_model",
        "llm.request_timeout_seconds",
        "logging.profile",
        "logging.level",
        "web.search_enabled",
        "web.fetch_limits",
        "read_only_inquiry.llm_enabled",
        "debug.main_page_trace_enabled",
        "debug.main_page_trace_sink",
    }

    registered = {key.key for key in registry.all()}
    assert expected_keys <= registered

    for key in registry.all():
        assert key.description
        assert key.scope_levels
        assert key.source_hints
        assert key.domain == key.key.split(".", 1)[0]


def test_runtime_config_registry_rejects_duplicate_keys() -> None:
    key = RuntimeConfigKey(
        key="agent_loop.default_max_steps",
        domain="agent_loop",
        value_type="int",
        default_value=20,
        scope_levels=("workspace",),
        mutability="next_agent_run",
        description="Maximum steps.",
    )
    registry = RuntimeConfigRegistry()
    registry.register(key)

    with pytest.raises(RuntimeConfigRegistryError, match="duplicate"):
        registry.register(key)


def test_runtime_config_resolver_uses_built_in_defaults() -> None:
    config = resolve_default_runtime_config(scope=RuntimeConfigScope(level="workspace"))

    max_steps = config.values["agent_loop.default_max_steps"]
    checkpoint = config.values["context_manager.checkpoint_interval_steps"]

    assert max_steps.value == 20
    assert max_steps.source.kind == "built_in_default"
    assert max_steps.mutability == "next_agent_run"
    assert max_steps.effective_status == "active"
    assert checkpoint.value == 5
    assert config.values["llm.default_provider"].value == "deepseek"
    assert config.values["llm.default_model"].value == "deepseek-v4-pro"
    assert config.values["llm.request_timeout_seconds"].value == 180.0
    assert config.values["context_manager.budget.max_file_snippet_chars"].value == 8000
    assert config.values["context_manager.budget.max_rendered_chars"].value == 60000
    assert config.values["computer_use.max_text_chars"].value == 4000
    assert config.values["debug.main_page_trace_enabled"].value is True
    assert config.config_id.startswith("runtime_config:")
    assert len(config.config_hash) == 64


def test_environment_runtime_config_layer_overrides_defaults() -> None:
    layer = environment_runtime_config_layer(
        {
            "LLM_PROVIDER": "deepseek",
            "LLM_MODEL": "deepseek-v4-pro",
            "LLM_REQUEST_TIMEOUT_SECONDS": "45",
            "PLATO_COMPUTER_USE_BACKEND": "macos",
            "PLATO_COMPUTER_USE_ALLOWED_APPS": "WeChat, TextEdit",
            "PLATO_COMPUTER_USE_ALLOW_COORDINATE_CLICK": "1",
            "PLATO_COMPUTER_USE_SCREEN_RECORDING_REQUIRED": "true",
            "PLATO_COMPUTER_USE_MAX_TEXT_CHARS": "1024",
            "PLATO_ENABLE_READ_ONLY_INQUIRY_LLM": "0",
            "PLATO_WEB_SEARCH_ENABLED": "1",
            "PLATO_WEB_FETCH_MAX_URLS": "5",
            "PLATO_WEB_FETCH_MAX_CHARS_PER_URL": "1234",
            "PLATO_WEB_FETCH_MAX_TOTAL_CHARS": "5678",
            "PLATO_MAIN_PAGE_TRACE": "0",
            "PLATO_MAIN_PAGE_TRACE_PRINT": "1",
            "PLATO_MAIN_PAGE_TRACE_FILE": "/tmp/plato-trace.jsonl",
        }
    )
    config = resolve_default_runtime_config(
        scope=RuntimeConfigScope(level="process"),
        layers=(layer,),
    )

    assert config.values["llm.default_provider"].value == "deepseek"
    assert config.values["llm.default_model"].value == "deepseek-v4-pro"
    assert config.values["llm.request_timeout_seconds"].value == 45.0
    assert config.values["computer_use.backend"].value == "macos"
    assert config.values["computer_use.enabled"].value is True
    assert config.values["computer_use.allowed_apps"].value == ("WeChat", "TextEdit")
    assert config.values["computer_use.allow_coordinate_click"].value is True
    assert config.values["computer_use.screen_recording_required"].value is True
    assert config.values["computer_use.max_text_chars"].value == 1024
    assert config.values["read_only_inquiry.llm_enabled"].value is False
    assert config.values["web.search_enabled"].value is True
    assert config.values["web.fetch_limits"].value == {
        "maxUrls": 5,
        "maxCharsPerUrl": 1234,
        "maxTotalChars": 5678,
    }
    assert config.values["debug.main_page_trace_enabled"].value is False
    assert config.values["debug.main_page_trace_sink"].value == {
        "print": True,
        "file": "/tmp/plato-trace.jsonl",
    }
    assert config.values["computer_use.backend"].source.kind == "environment"


def test_process_runtime_config_layer_has_priority_over_environment() -> None:
    env_layer = environment_runtime_config_layer(
        {
            "PLATO_COMPUTER_USE_BACKEND": "macos",
            "PLATO_COMPUTER_USE_ALLOWED_APPS": "WeChat",
        }
    )
    process_layer = process_runtime_config_layer(
        {
            "computer_use.backend": "disabled",
            "computer_use.enabled": False,
            "computer_use.allowed_apps": (),
            "agent_loop.default_max_steps": 8,
        }
    )

    config = resolve_default_runtime_config(
        scope=RuntimeConfigScope(level="process"),
        layers=(process_layer, env_layer),
    )

    assert config.values["computer_use.backend"].value == "disabled"
    assert config.values["computer_use.backend"].source.kind == "process_input"
    assert config.values["computer_use.allowed_apps"].value == ()
    assert config.values["agent_loop.default_max_steps"].value == 8


def test_runtime_patch_non_live_values_are_marked_pending() -> None:
    patch_layer = RuntimeConfigLayer(
        source=RuntimeConfigSource(
            source_id="runtime_patch:test",
            kind="runtime_patch",
            scope=RuntimeConfigScope(level="session", session_id="s1"),
            priority=80,
        ),
        values={"agent_loop.default_max_steps": 12},
    )

    config = resolve_default_runtime_config(
        scope=RuntimeConfigScope(level="session", session_id="s1"),
        layers=(patch_layer,),
    )

    value = config.values["agent_loop.default_max_steps"]
    assert value.value == 12
    assert value.effective_status == "pending_next_agent_run"


def test_runtime_config_resolver_rejects_unknown_keys() -> None:
    layer = process_runtime_config_layer({"wechat.enabled": True})

    with pytest.raises(RuntimeConfigRegistryError, match="unknown runtime config key"):
        resolve_default_runtime_config(scope=RuntimeConfigScope(), layers=(layer,))


def test_runtime_config_resolver_rejects_invalid_value_type() -> None:
    layer = process_runtime_config_layer({"agent_loop.default_max_steps": "20"})

    with pytest.raises(RuntimeConfigResolverError, match="must be int"):
        resolve_default_runtime_config(scope=RuntimeConfigScope(), layers=(layer,))
