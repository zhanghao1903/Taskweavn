from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from taskweavn.llm.agent_config import ResolvedAgentLlmProfile
from taskweavn.llm.agent_resolver import AgentConfiguredLLM, SettingsBackedAgentLlmResolver
from taskweavn.llm.contracts import ChatResponse, ProviderRoutingConfig, ThinkingConfig


def test_settings_backed_agent_llm_resolver_uses_role_profile_and_provider_secret() -> None:
    store = _SettingsStore(
        config={
            "llm": {
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
            },
            "agentLlm": {
                "profiles": {
                    "default": {
                        "provider": "deepseek",
                        "model": "deepseek-v4-pro",
                    },
                    "router": {
                        "provider": "openrouter",
                        "model": "openrouter/router-model",
                        "timeoutSeconds": 25,
                    },
                },
                "bindings": {
                    "runtime_input_router": "router",
                },
            },
        },
        secrets={"openrouter": "sk-openrouter"},
    )
    resolver = SettingsBackedAgentLlmResolver(
        settings_store=store,
        base_env={"DEEPSEEK_API_KEY": "sk-deepseek-env"},
        workspace_id="workspace-1",
    )

    profile = resolver.profile_for("runtime_input_router")

    assert profile.profile_name == "router"
    assert profile.provider == "openrouter"
    assert profile.model == "openrouter/router-model"
    assert profile.timeout_seconds == 25
    assert profile.api_key_configured is True


def test_agent_configured_llm_applies_profile_defaults_and_safe_metadata() -> None:
    inner = _StubLLM()
    llm = AgentConfiguredLLM(
        inner=inner,
        profile=ResolvedAgentLlmProfile(
            role="runtime_input_router",
            profile_name="router",
            provider="deepseek",
            model="deepseek-chat",
            timeout_seconds=30,
            temperature=0,
            thinking=ThinkingConfig(enabled=True, effort="high"),
            provider_routing=ProviderRoutingConfig(only=("deepinfra/turbo",)),
        ),
    )

    response = llm.chat(
        messages=[{"role": "user", "content": "route this"}],
        tools=None,
        metadata={"agent_kind": "router"},
    )

    assert response.content == "ok"
    assert inner.calls[0]["timeout_seconds"] == 30
    assert inner.calls[0]["temperature"] == 0
    assert inner.calls[0]["thinking"].enabled is True
    assert inner.calls[0]["provider_routing"].only == ("deepinfra/turbo",)
    assert inner.calls[0]["metadata"] == {
        "agent_kind": "router",
        "agent_llm_role": "runtime_input_router",
        "agent_llm_profile": "router",
    }


@dataclass
class _SettingsStore:
    config: dict[str, Any]
    secrets: dict[str, str] = field(default_factory=dict)

    def read_config(self) -> dict[str, Any]:
        return self.config

    def effective_env(self, base_env: Mapping[str, str]) -> dict[str, str]:
        env = dict(base_env)
        llm = self.config.get("llm")
        if isinstance(llm, dict):
            provider = llm.get("provider")
            model = llm.get("model")
            if isinstance(provider, str):
                env["LLM_PROVIDER"] = provider
            if isinstance(model, str):
                env["LLM_MODEL"] = model
        return env

    def read_llm_provider_secret(self, provider: str) -> str | None:
        return self.secrets.get(provider)


@dataclass
class _StubLLM:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "metadata": metadata,
                **kwargs,
            }
        )
        return ChatResponse(
            content="ok",
            tool_calls=[],
            raw_assistant_message={"role": "assistant", "content": "ok"},
        )
