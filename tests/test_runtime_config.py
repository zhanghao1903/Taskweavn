from __future__ import annotations

import pytest
from pydantic import ValidationError

from taskweavn.runtime_config import (
    RuntimeConfigActor,
    RuntimeConfigChange,
    RuntimeConfigKey,
    RuntimeConfigLayer,
    RuntimeConfigPatch,
    RuntimeConfigRegistry,
    RuntimeConfigRegistryError,
    RuntimeConfigRejection,
    RuntimeConfigResolverError,
    RuntimeConfigScope,
    RuntimeConfigSnapshotRecord,
    RuntimeConfigSource,
    build_default_runtime_config_registry,
    environment_runtime_config_layer,
    process_runtime_config_layer,
    resolve_default_runtime_config,
)
from taskweavn.server.runtime_config_consumers import (
    RuntimeConfigConsumerError,
    runtime_computer_use_settings_from_config,
    runtime_context_settings_from_config,
    runtime_execution_settings_from_config,
    runtime_read_only_inquiry_settings_from_config,
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


def test_runtime_execution_settings_are_extracted_from_effective_config() -> None:
    layer = process_runtime_config_layer(
        {
            "agent_loop.default_max_steps": 4,
            "execution_dispatcher.enabled": False,
            "execution_dispatcher.max_ticks_per_trigger": 2,
        }
    )
    config = resolve_default_runtime_config(
        scope=RuntimeConfigScope(level="workspace", workspace_id="w1"),
        layers=(layer,),
    )

    settings = runtime_execution_settings_from_config(config)

    assert settings.default_agent_max_steps == 4
    assert settings.execution_dispatcher_enabled is False
    assert settings.execution_dispatcher_max_ticks_per_trigger == 2
    assert settings.config_hash == config.config_hash


def test_runtime_context_settings_are_extracted_from_effective_config() -> None:
    layer = process_runtime_config_layer(
        {
            "context_manager.checkpoint_interval_steps": 3,
            "context_manager.max_prior_messages": 11,
            "context_manager.budget.max_events": 9,
            "context_manager.budget.max_tool_results": 8,
            "context_manager.budget.max_file_snippets": 7,
            "context_manager.budget.max_file_snippet_chars": 6000,
            "context_manager.budget.max_rendered_chars": 50000,
        }
    )
    config = resolve_default_runtime_config(
        scope=RuntimeConfigScope(level="workspace", workspace_id="w1"),
        layers=(layer,),
    )

    settings = runtime_context_settings_from_config(config)

    assert settings.checkpoint_interval_steps == 3
    assert settings.max_prior_messages == 11
    assert settings.budget.max_events == 9
    assert settings.budget.max_tool_results == 8
    assert settings.budget.max_file_snippets == 7
    assert settings.budget.max_file_snippet_chars == 6000
    assert settings.budget.max_rendered_chars == 50000
    assert settings.config_hash == config.config_hash


def test_runtime_tool_and_read_only_settings_are_extracted_from_effective_config() -> None:
    layer = process_runtime_config_layer(
        {
            "computer_use.enabled": True,
            "computer_use.backend": "macos",
            "computer_use.allowed_apps": ("WeChat", "TextEdit"),
            "read_only_inquiry.llm_enabled": False,
        }
    )
    config = resolve_default_runtime_config(
        scope=RuntimeConfigScope(level="workspace", workspace_id="w1"),
        layers=(layer,),
    )

    computer_use = runtime_computer_use_settings_from_config(config)
    inquiry = runtime_read_only_inquiry_settings_from_config(config)

    assert computer_use.enabled is True
    assert computer_use.backend == "macos"
    assert computer_use.allowed_apps == ("WeChat", "TextEdit")
    assert computer_use.config_hash == config.config_hash
    assert inquiry.llm_enabled is False
    assert inquiry.config_hash == config.config_hash


def test_runtime_execution_settings_reject_invalid_effective_values() -> None:
    config = resolve_default_runtime_config(
        scope=RuntimeConfigScope(level="process"),
    )
    values = dict(config.values)
    values["agent_loop.default_max_steps"] = values[
        "agent_loop.default_max_steps"
    ].model_copy(update={"value": "20"})
    bad_config = config.model_copy(update={"values": values})

    with pytest.raises(RuntimeConfigConsumerError, match="must be an int"):
        runtime_execution_settings_from_config(bad_config)


def test_runtime_context_settings_reject_invalid_effective_values() -> None:
    config = resolve_default_runtime_config(
        scope=RuntimeConfigScope(level="process"),
    )
    values = dict(config.values)
    values["context_manager.max_prior_messages"] = values[
        "context_manager.max_prior_messages"
    ].model_copy(update={"value": True})
    bad_config = config.model_copy(update={"values": values})

    with pytest.raises(RuntimeConfigConsumerError, match="must be an int"):
        runtime_context_settings_from_config(bad_config)


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


def test_runtime_config_patch_requires_explicit_scope_identifiers() -> None:
    actor = RuntimeConfigActor(actor_type="user", actor_id="user-1")

    with pytest.raises(ValidationError, match="workspace runtime config scope requires"):
        RuntimeConfigPatch(
            patch_id="patch-1",
            scope=RuntimeConfigScope(level="workspace"),
            actor=actor,
            values={"logging.level": "DEBUG"},
        )

    patch = RuntimeConfigPatch(
        patch_id="patch-2",
        idempotency_key="idem-2",
        scope=RuntimeConfigScope(
            level="session",
            workspace_id="workspace-1",
            session_id="session-1",
        ),
        actor=actor,
        reason="increase diagnostics",
        values={"logging.level": "DEBUG"},
        expected_base_config_hash="base-hash",
    )

    assert patch.scope.level == "session"
    assert patch.scope.workspace_id == "workspace-1"
    assert patch.scope.session_id == "session-1"
    assert patch.values == {"logging.level": "DEBUG"}


def test_runtime_config_change_validates_status_and_redaction() -> None:
    actor = RuntimeConfigActor(actor_type="system", actor_id="settings")
    scope = RuntimeConfigScope(level="workspace", workspace_id="workspace-1")

    with pytest.raises(ValidationError, match="accepted config change requires"):
        RuntimeConfigChange(
            change_id="change-1",
            patch_id="patch-1",
            scope=scope,
            actor=actor,
            status="accepted",
            requested_values={"logging.level": "DEBUG"},
            accepted_values={},
            base_config_hash="base-hash",
            resulting_config_hash="next-hash",
        )

    with pytest.raises(ValidationError, match="redacted keys"):
        RuntimeConfigChange(
            change_id="change-2",
            patch_id="patch-2",
            scope=scope,
            actor=actor,
            status="rejected",
            requested_values={"llm.default_model": "deepseek-v4-pro"},
            rejected_values={
                "llm.api_key": RuntimeConfigRejection(
                    code="secret_not_patchable",
                    message="Secrets are owned by the Settings secret boundary.",
                    details={"redacted": True},
                )
            },
            redacted_keys=("llm.api_key",),
            base_config_hash="base-hash",
        )

    change = RuntimeConfigChange(
        change_id="change-3",
        patch_id="patch-3",
        idempotency_key="idem-3",
        scope=scope,
        actor=actor,
        reason="debug one workspace",
        status="accepted",
        requested_values={
            "logging.level": "DEBUG",
            "llm.api_key": {"redacted": True},
        },
        accepted_values={"logging.level": "DEBUG"},
        rejected_values={
            "llm.api_key": RuntimeConfigRejection(
                code="secret_not_patchable",
                message="Secrets are owned by the Settings secret boundary.",
                details={"redacted": True},
            )
        },
        redacted_keys=("llm.api_key",),
        base_config_hash="base-hash",
        resulting_config_hash="next-hash",
        effective_status_by_key={"logging.level": "active"},
    )

    assert change.status == "accepted"
    assert change.redacted_keys == ("llm.api_key",)
    assert change.rejected_values["llm.api_key"].code == "secret_not_patchable"
    assert change.model_dump(mode="json", by_alias=True)["redactedKeys"] == [
        "llm.api_key"
    ]


def test_runtime_config_change_validates_no_op_hash() -> None:
    actor = RuntimeConfigActor(actor_type="test")
    scope = RuntimeConfigScope(level="workspace", workspace_id="workspace-1")

    with pytest.raises(ValidationError, match="no-op config change must preserve"):
        RuntimeConfigChange(
            change_id="change-1",
            patch_id="patch-1",
            scope=scope,
            actor=actor,
            status="no_op",
            requested_values={"logging.level": "INFO"},
            base_config_hash="base-hash",
            resulting_config_hash="different-hash",
        )

    change = RuntimeConfigChange(
        change_id="change-2",
        patch_id="patch-2",
        scope=scope,
        actor=actor,
        status="no_op",
        requested_values={"logging.level": "INFO"},
        base_config_hash="base-hash",
        resulting_config_hash="base-hash",
    )

    assert change.status == "no_op"
    assert change.resulting_config_hash == change.base_config_hash


def test_runtime_config_snapshot_record_matches_effective_config() -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="workspace-1")
    config = resolve_default_runtime_config(scope=scope)

    record = RuntimeConfigSnapshotRecord(
        snapshot_id="snapshot-1",
        config_hash=config.config_hash,
        scope=scope,
        effective_config=config,
        created_by_change_id="change-1",
    )

    assert record.config_hash == config.config_hash
    assert record.effective_config.config_hash == config.config_hash

    with pytest.raises(ValidationError, match="config_hash must match"):
        RuntimeConfigSnapshotRecord(
            snapshot_id="snapshot-2",
            config_hash="wrong-hash",
            scope=scope,
            effective_config=config,
        )

    with pytest.raises(ValidationError, match="scope must match"):
        RuntimeConfigSnapshotRecord(
            snapshot_id="snapshot-3",
            config_hash=config.config_hash,
            scope=RuntimeConfigScope(level="workspace", workspace_id="workspace-2"),
            effective_config=config,
        )


def test_runtime_config_resolver_rejects_unknown_keys() -> None:
    layer = process_runtime_config_layer({"wechat.enabled": True})

    with pytest.raises(RuntimeConfigRegistryError, match="unknown runtime config key"):
        resolve_default_runtime_config(scope=RuntimeConfigScope(), layers=(layer,))


def test_runtime_config_resolver_rejects_invalid_value_type() -> None:
    layer = process_runtime_config_layer({"agent_loop.default_max_steps": "20"})

    with pytest.raises(RuntimeConfigResolverError, match="must be int"):
        resolve_default_runtime_config(scope=RuntimeConfigScope(), layers=(layer,))
