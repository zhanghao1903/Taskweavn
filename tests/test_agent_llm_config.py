from __future__ import annotations

import pytest

from taskweavn.llm.agent_config import (
    parse_agent_llm_config,
    resolve_agent_llm_profile,
)


def test_agent_llm_config_resolves_bound_profile_with_inheritance() -> None:
    config = parse_agent_llm_config(
        {
            "agentLlm": {
                "schemaVersion": "plato.agent_llm_config.v1",
                "defaultProfile": "default",
                "profiles": {
                    "default": {
                        "provider": "deepseek",
                        "model": "deepseek-v4-pro",
                        "timeoutSeconds": 180,
                    },
                    "router": {
                        "inherits": "default",
                        "model": "deepseek-chat",
                        "timeoutSeconds": 30,
                        "temperature": 0,
                    },
                },
                "bindings": {
                    "runtime_input_router": "router",
                },
            }
        }
    )

    profile = resolve_agent_llm_profile(
        config=config,
        role="runtime_input_router",
        fallback_provider="openrouter",
        fallback_model="openrouter/fallback",
        api_key_configured=True,
    )

    assert profile.role == "runtime_input_router"
    assert profile.profile_name == "router"
    assert profile.provider == "deepseek"
    assert profile.model == "deepseek-chat"
    assert profile.timeout_seconds == 30
    assert profile.temperature == 0
    assert profile.api_key_configured is True


def test_agent_llm_config_uses_global_fallback_without_agent_block() -> None:
    profile = resolve_agent_llm_profile(
        config=parse_agent_llm_config({}),
        role="execution_agent",
        fallback_provider="openrouter",
        fallback_model="openrouter/model",
        api_key_configured=False,
    )

    assert profile.profile_name == "global"
    assert profile.provider == "openrouter"
    assert profile.model == "openrouter/model"
    assert profile.api_key_configured is False


def test_agent_llm_config_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="provider"):
        parse_agent_llm_config(
            {
                "agentLlm": {
                    "profiles": {
                        "default": {
                            "provider": "unknown",
                            "model": "model",
                        }
                    }
                }
            }
        )


def test_agent_llm_config_rejects_inheritance_cycle() -> None:
    config = parse_agent_llm_config(
        {
            "agentLlm": {
                "defaultProfile": "a",
                "profiles": {
                    "a": {"inherits": "b", "model": "a"},
                    "b": {"inherits": "a", "model": "b"},
                },
            }
        }
    )

    with pytest.raises(ValueError, match="cycle"):
        resolve_agent_llm_profile(
            config=config,
            role="execution_agent",
            fallback_provider="deepseek",
            fallback_model="deepseek-v4-pro",
            api_key_configured=True,
        )
