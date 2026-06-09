"""LLM provider configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass

from taskweavn.llm.contracts import (
    LLMProvider,
    ProviderRoutingConfig,
    RetryPolicy,
    ThinkingConfig,
)
from taskweavn.llm.providers.deepseek import DeepSeekProvider
from taskweavn.llm.providers.litellm import LiteLLMProvider
from taskweavn.llm.providers.openrouter import OpenRouterProvider


@dataclass(frozen=True)
class LLMClientConfig:
    """Resolved configuration for ``LLMClient.from_env``."""

    model: str
    api_key: str | None
    provider: LLMProvider
    thinking: ThinkingConfig | None = None
    provider_routing: ProviderRoutingConfig | None = None
    request_timeout_seconds: float | None = None


DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS = 180.0
DEFAULT_LLM_PROVIDER = "deepseek"


def load_client_config_from_env(default_model: str) -> LLMClientConfig:
    """Resolve provider config from environment variables."""
    provider_name = os.environ.get("LLM_PROVIDER", DEFAULT_LLM_PROVIDER).strip().lower()
    model = os.environ.get("LLM_MODEL", default_model)
    thinking = _thinking_from_env()
    routing = _openrouter_routing_from_env() if provider_name == "openrouter" else None
    request_timeout_seconds = _request_timeout_from_env()
    provider: LLMProvider

    if provider_name == "deepseek":
        api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
        if not api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY or LLM_API_KEY is required for LLM_PROVIDER=deepseek."
            )
        provider = DeepSeekProvider(
            api_key=api_key,
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
    elif provider_name == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY or LLM_API_KEY is required for LLM_PROVIDER=openrouter."
            )
        provider = OpenRouterProvider(api_key=api_key, provider_routing=routing)
    elif provider_name == "litellm":
        api_key = os.environ.get("LLM_API_KEY")
        if not api_key:
            raise RuntimeError(
                "LLM_API_KEY is not set; export it before using LLMClient.from_env()."
            )
        provider = LiteLLMProvider(api_key=api_key)
    else:
        raise RuntimeError(
            "LLM_PROVIDER must be one of: litellm, deepseek, openrouter; "
            f"got {provider_name!r}."
        )

    return LLMClientConfig(
        model=model,
        api_key=api_key,
        provider=provider,
        thinking=thinking,
        provider_routing=routing,
        request_timeout_seconds=request_timeout_seconds,
    )


def build_provider(
    *,
    provider_name: str,
    api_key: str | None,
    retry_policy: RetryPolicy | None = None,
    provider_routing: ProviderRoutingConfig | None = None,
) -> LiteLLMProvider | DeepSeekProvider | OpenRouterProvider:
    """Build a provider explicitly, mostly for tests and advanced config."""
    normalized = provider_name.strip().lower()
    if normalized == "litellm":
        return LiteLLMProvider(api_key=api_key, retry_policy=retry_policy)
    if normalized == "deepseek":
        if api_key is None:
            raise RuntimeError("api_key is required for deepseek provider")
        return DeepSeekProvider(api_key=api_key, retry_policy=retry_policy)
    if normalized == "openrouter":
        return OpenRouterProvider(
            api_key=api_key,
            retry_policy=retry_policy,
            provider_routing=provider_routing,
        )
    raise RuntimeError(f"unknown LLM provider: {provider_name!r}")


def _thinking_from_env() -> ThinkingConfig | None:
    raw = os.environ.get("LLM_THINKING_ENABLED")
    if raw is None:
        return None
    return ThinkingConfig(
        enabled=_parse_bool(raw),
        effort=os.environ.get("LLM_THINKING_EFFORT", "high"),
    )


def _request_timeout_from_env() -> float | None:
    raw = os.environ.get("LLM_REQUEST_TIMEOUT_SECONDS")
    if raw is None:
        return DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS

    normalized = raw.strip().lower()
    if normalized in {"none", "off", "disabled"}:
        return None
    try:
        timeout = float(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid LLM_REQUEST_TIMEOUT_SECONDS: {raw!r}") from exc
    if timeout <= 0:
        raise ValueError("LLM_REQUEST_TIMEOUT_SECONDS must be positive or 'none'")
    return timeout


def _openrouter_routing_from_env() -> ProviderRoutingConfig | None:
    order = _split_csv(os.environ.get("OPENROUTER_PROVIDER_ORDER"))
    only = _split_csv(os.environ.get("OPENROUTER_PROVIDER_ONLY"))
    ignore = _split_csv(os.environ.get("OPENROUTER_PROVIDER_IGNORE"))
    allow_fallbacks = _parse_bool(os.environ.get("OPENROUTER_ALLOW_FALLBACKS", "false"))
    require_parameters = _parse_bool(
        os.environ.get("OPENROUTER_REQUIRE_PARAMETERS", "true")
    )
    data_collection = os.environ.get("OPENROUTER_DATA_COLLECTION")
    if (
        not order
        and not only
        and not ignore
        and data_collection is None
        and "OPENROUTER_ALLOW_FALLBACKS" not in os.environ
        and "OPENROUTER_REQUIRE_PARAMETERS" not in os.environ
    ):
        return None
    return ProviderRoutingConfig(
        order=tuple(order),
        only=tuple(only),
        ignore=tuple(ignore),
        allow_fallbacks=allow_fallbacks,
        require_parameters=require_parameters,
        data_collection=data_collection,
        zdr=_parse_optional_bool(os.environ.get("OPENROUTER_ZDR")),
    )


def _split_csv(raw: str | None) -> list[str]:
    if raw is None:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _parse_optional_bool(raw: str | None) -> bool | None:
    return None if raw is None else _parse_bool(raw)


def _parse_bool(raw: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {raw!r}")


__all__ = [
    "DEFAULT_LLM_PROVIDER",
    "DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS",
    "LLMClientConfig",
    "build_provider",
    "load_client_config_from_env",
]
