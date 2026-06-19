"""Resolve backend-only Agent LLM roles to lazy configured clients."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from taskweavn.llm.agent_config import (
    AgentLlmConfig,
    AgentLlmRole,
    ResolvedAgentLlmProfile,
    parse_agent_llm_config,
    resolve_agent_llm_profile,
)
from taskweavn.llm.client import LazyLLMClient
from taskweavn.usage import UsageRecordingLLM
from taskweavn.usage.recording import TaskPlanResolver, TokenUsageEventSink


class AgentLlmSettingsStore(Protocol):
    def read_config(self) -> dict[str, Any]: ...

    def effective_env(self, base_env: Mapping[str, str]) -> dict[str, str]: ...

    def read_llm_provider_secret(self, provider: str) -> str | None: ...


@dataclass(frozen=True)
class SettingsBackedAgentLlmResolver:
    """Role-aware LLM resolver backed by existing Plato Settings files."""

    settings_store: AgentLlmSettingsStore
    base_env: Mapping[str, str]
    workspace_id: str
    usage_sink: TokenUsageEventSink | None = None
    task_plan_resolver: TaskPlanResolver | None = None
    fallback_default_model: str = "deepseek-v4-pro"

    def profile_for(self, role: AgentLlmRole) -> ResolvedAgentLlmProfile:
        fallback_env = self.settings_store.effective_env(self.base_env)
        config = self._agent_config()
        fallback_provider = fallback_env.get("LLM_PROVIDER", "deepseek")
        fallback_model = fallback_env.get("LLM_MODEL", self.fallback_default_model)
        profile = resolve_agent_llm_profile(
            config=config,
            role=role,
            fallback_provider=fallback_provider,
            fallback_model=fallback_model,
            api_key_configured=False,
        )
        api_key = self._api_key_for(profile.provider, fallback_env=fallback_env)
        return profile.model_copy(update={"api_key_configured": api_key is not None})

    def client_for(self, role: AgentLlmRole) -> Any:
        profile = self.profile_for(role)
        env = self._env_for_profile(profile)
        inner = LazyLLMClient(
            default_model=profile.model or self.fallback_default_model,
            env_provider=lambda: env,
        )
        configured = AgentConfiguredLLM(inner=inner, profile=profile)
        if self.usage_sink is None:
            return configured
        return UsageRecordingLLM(
            configured,
            workspace_id=self.workspace_id,
            sink=self.usage_sink,
            task_plan_resolver=self.task_plan_resolver,
        )

    def _agent_config(self) -> AgentLlmConfig | None:
        try:
            return parse_agent_llm_config(self.settings_store.read_config())
        except Exception:
            return None

    def _env_for_profile(self, profile: ResolvedAgentLlmProfile) -> dict[str, str]:
        env = self.settings_store.effective_env(self.base_env)
        env["LLM_PROVIDER"] = profile.provider
        env["LLM_MODEL"] = profile.model
        if profile.timeout_seconds is not None:
            env["LLM_REQUEST_TIMEOUT_SECONDS"] = str(profile.timeout_seconds)
        api_key = self._api_key_for(profile.provider, fallback_env=env)
        if api_key is not None:
            env[_preferred_api_key_env_var(profile.provider)] = api_key
        return env

    def _api_key_for(
        self,
        provider: str,
        *,
        fallback_env: Mapping[str, str],
    ) -> str | None:
        secret = self.settings_store.read_llm_provider_secret(provider)
        if secret is not None:
            return secret
        for env_var in _required_api_key_env_vars(provider):
            value = fallback_env.get(env_var, "").strip()
            if value:
                return value
        return None


@dataclass(frozen=True)
class AgentConfiguredLLM:
    """Apply resolved role profile defaults to an underlying LLM client."""

    inner: Any
    profile: ResolvedAgentLlmProfile

    @property
    def model(self) -> str:
        return self.profile.model

    @property
    def request_timeout_seconds(self) -> float | None:
        return self.profile.timeout_seconds

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        request_kwargs = dict(kwargs)
        if self.profile.timeout_seconds is not None:
            request_kwargs.setdefault("timeout_seconds", self.profile.timeout_seconds)
        if self.profile.temperature is not None:
            request_kwargs.setdefault("temperature", self.profile.temperature)
        if self.profile.thinking is not None:
            request_kwargs.setdefault("thinking", self.profile.thinking)
        if self.profile.provider_routing is not None:
            request_kwargs.setdefault("provider_routing", self.profile.provider_routing)
        enriched_metadata = dict(metadata or {})
        enriched_metadata.setdefault("agent_llm_role", self.profile.role)
        enriched_metadata.setdefault("agent_llm_profile", self.profile.profile_name)
        return self.inner.chat(
            messages=messages,
            tools=tools,
            metadata=enriched_metadata,
            **request_kwargs,
        )

    def complete(self, *args: Any, **kwargs: Any) -> Any:
        return self.inner.complete(*args, **kwargs)

    def count_tokens(self, *args: Any, **kwargs: Any) -> Any:
        return self.inner.count_tokens(*args, **kwargs)


def _required_api_key_env_vars(provider: str) -> tuple[str, ...]:
    normalized = provider.strip().lower()
    if normalized == "deepseek":
        return ("DEEPSEEK_API_KEY", "LLM_API_KEY")
    if normalized == "openrouter":
        return ("OPENROUTER_API_KEY", "LLM_API_KEY")
    if normalized == "litellm":
        return ("LLM_API_KEY",)
    return ("LLM_API_KEY",)


def _preferred_api_key_env_var(provider: str) -> str:
    return _required_api_key_env_vars(provider)[0]


__all__ = [
    "AgentConfiguredLLM",
    "AgentLlmSettingsStore",
    "SettingsBackedAgentLlmResolver",
]
