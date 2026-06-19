"""Backend-only Agent-level LLM profile configuration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from taskweavn.llm.contracts import ProviderRoutingConfig, ThinkingConfig

AgentLlmRole = Literal[
    "runtime_input_router",
    "execution_agent",
    "collaborator",
    "read_only_inquiry",
    "audit_agent",
    "summary_agent",
]

AGENT_LLM_CONFIG_SCHEMA_VERSION = "plato.agent_llm_config.v1"
SUPPORTED_AGENT_LLM_PROVIDERS = ("deepseek", "litellm", "openrouter")
_MAX_INHERITANCE_DEPTH = 8


class AgentLlmProfileInput(BaseModel):
    """Raw profile shape as stored in settings/config.json."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    inherits: str | None = Field(default=None, min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    timeout_seconds: float | None = Field(default=None, alias="timeoutSeconds")
    temperature: float | None = None
    thinking: ThinkingConfig | None = None
    provider_routing: ProviderRoutingConfig | None = Field(
        default=None,
        alias="providerRouting",
    )

    @field_validator("provider")
    @classmethod
    def _normalize_provider(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_AGENT_LLM_PROVIDERS:
            raise ValueError(
                "provider must be one of: "
                + ", ".join(SUPPORTED_AGENT_LLM_PROVIDERS)
            )
        return normalized

    @field_validator("timeout_seconds")
    @classmethod
    def _validate_timeout(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("timeoutSeconds must be positive")
        return value

    @field_validator("temperature")
    @classmethod
    def _validate_temperature(cls, value: float | None) -> float | None:
        if value is not None and (value < 0 or value > 2):
            raise ValueError("temperature must be between 0 and 2")
        return value


class ResolvedAgentLlmProfile(BaseModel):
    """Fully-resolved role profile after inheritance and global fallback."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str
    profile_name: str
    provider: str
    model: str
    timeout_seconds: float | None = None
    temperature: float | None = None
    thinking: ThinkingConfig | None = None
    provider_routing: ProviderRoutingConfig | None = None
    api_key_configured: bool = False


class AgentLlmConfig(BaseModel):
    """Parsed backend-only Agent LLM configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: Literal["plato.agent_llm_config.v1"] = Field(
        default="plato.agent_llm_config.v1",
        alias="schemaVersion",
    )
    default_profile: str = Field(default="default", alias="defaultProfile", min_length=1)
    profiles: dict[str, AgentLlmProfileInput] = Field(default_factory=dict)
    bindings: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_bindings(self) -> AgentLlmConfig:
        if self.profiles and self.default_profile not in self.profiles:
            raise ValueError("defaultProfile must reference an existing profile")
        for role, profile_name in self.bindings.items():
            if not isinstance(role, str) or not role.strip():
                raise ValueError("binding role must not be empty")
            if profile_name not in self.profiles:
                raise ValueError(f"binding {role!r} references unknown profile")
        return self


def parse_agent_llm_config(config: Mapping[str, Any]) -> AgentLlmConfig | None:
    """Parse the optional top-level ``agentLlm`` config block."""

    raw_config = config.get("agentLlm")
    if not isinstance(raw_config, Mapping):
        return None
    return AgentLlmConfig.model_validate(raw_config)


def resolve_agent_llm_profile(
    *,
    config: AgentLlmConfig | None,
    role: AgentLlmRole,
    fallback_provider: str,
    fallback_model: str,
    api_key_configured: bool,
) -> ResolvedAgentLlmProfile:
    """Resolve one role to a concrete provider/model profile."""

    if config is None or not config.profiles:
        return ResolvedAgentLlmProfile(
            role=role,
            profile_name="global",
            provider=_normalize_provider_or_default(fallback_provider),
            model=fallback_model,
            api_key_configured=api_key_configured,
        )

    profile_name = config.bindings.get(role, config.default_profile)
    merged = _merge_profile(
        profile_name,
        config.profiles,
        seen=(),
    )
    provider = merged.provider or _normalize_provider_or_default(fallback_provider)
    model = merged.model or fallback_model
    return ResolvedAgentLlmProfile(
        role=role,
        profile_name=profile_name,
        provider=provider,
        model=model,
        timeout_seconds=merged.timeout_seconds,
        temperature=merged.temperature,
        thinking=merged.thinking,
        provider_routing=merged.provider_routing,
        api_key_configured=api_key_configured,
    )


def _merge_profile(
    profile_name: str,
    profiles: Mapping[str, AgentLlmProfileInput],
    *,
    seen: tuple[str, ...],
) -> AgentLlmProfileInput:
    if profile_name in seen:
        chain = " -> ".join((*seen, profile_name))
        raise ValueError(f"agentLlm profile inheritance cycle: {chain}")
    if len(seen) >= _MAX_INHERITANCE_DEPTH:
        raise ValueError("agentLlm profile inheritance is too deep")
    profile = profiles.get(profile_name)
    if profile is None:
        raise ValueError(f"unknown agentLlm profile: {profile_name}")
    if profile.inherits is None:
        return profile
    parent = _merge_profile(profile.inherits, profiles, seen=(*seen, profile_name))
    return AgentLlmProfileInput(
        provider=profile.provider if profile.provider is not None else parent.provider,
        model=profile.model if profile.model is not None else parent.model,
        timeoutSeconds=(
            profile.timeout_seconds
            if profile.timeout_seconds is not None
            else parent.timeout_seconds
        ),
        temperature=(
            profile.temperature
            if profile.temperature is not None
            else parent.temperature
        ),
        thinking=profile.thinking if profile.thinking is not None else parent.thinking,
        providerRouting=(
            profile.provider_routing
            if profile.provider_routing is not None
            else parent.provider_routing
        ),
    )


def _normalize_provider_or_default(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized in SUPPORTED_AGENT_LLM_PROVIDERS:
        return normalized
    return "deepseek"


__all__ = [
    "AGENT_LLM_CONFIG_SCHEMA_VERSION",
    "AgentLlmConfig",
    "AgentLlmProfileInput",
    "AgentLlmRole",
    "ResolvedAgentLlmProfile",
    "parse_agent_llm_config",
    "resolve_agent_llm_profile",
]
