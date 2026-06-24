"""Effective runtime configuration resolution."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from taskweavn.runtime_config.defaults import build_default_runtime_config_registry
from taskweavn.runtime_config.models import (
    EffectiveRuntimeConfig,
    EffectiveRuntimeConfigValue,
    RuntimeConfigEffectiveStatus,
    RuntimeConfigKey,
    RuntimeConfigLayer,
    RuntimeConfigMutability,
    RuntimeConfigScope,
    RuntimeConfigSource,
)
from taskweavn.runtime_config.registry import RuntimeConfigRegistry


class RuntimeConfigResolverError(ValueError):
    """Raised when effective runtime configuration cannot be resolved."""


def resolve_default_runtime_config(
    *,
    scope: RuntimeConfigScope | None = None,
    layers: tuple[RuntimeConfigLayer, ...] = (),
    registry: RuntimeConfigRegistry | None = None,
) -> EffectiveRuntimeConfig:
    resolver = RuntimeConfigResolver(registry or build_default_runtime_config_registry())
    return resolver.resolve(scope=scope or RuntimeConfigScope(), layers=layers)


@dataclass(frozen=True)
class RuntimeConfigResolver:
    """Resolve immutable effective runtime configuration snapshots."""

    registry: RuntimeConfigRegistry

    def resolve(
        self,
        *,
        scope: RuntimeConfigScope,
        layers: tuple[RuntimeConfigLayer, ...] = (),
    ) -> EffectiveRuntimeConfig:
        values: dict[str, EffectiveRuntimeConfigValue] = {}
        default_source = RuntimeConfigSource(
            source_id="built_in_defaults",
            kind="built_in_default",
            scope=RuntimeConfigScope(level="global"),
            priority=0,
        )
        for key in self.registry.all():
            values[key.key] = EffectiveRuntimeConfigValue(
                key=key.key,
                value=_normalize_value(key, key.default_value),
                source=default_source,
                mutability=key.mutability,
                effective_status=_effective_status(key.mutability, default_source),
                redacted=key.secret,
            )
        normalized_layers = tuple(sorted(layers, key=lambda layer: layer.source.priority))
        for layer in normalized_layers:
            self._apply_layer(values, layer)
        source_layers = tuple(_unique_sources(default_source, *(layer.source for layer in layers)))
        config_hash = _config_hash(values)
        return EffectiveRuntimeConfig(
            config_id=f"runtime_config:{config_hash[:16]}",
            scope=scope,
            values=values,
            source_layers=source_layers,
            config_hash=config_hash,
        )

    def explain(
        self,
        *,
        key: str,
        scope: RuntimeConfigScope,
        layers: tuple[RuntimeConfigLayer, ...] = (),
    ) -> EffectiveRuntimeConfigValue:
        config = self.resolve(scope=scope, layers=layers)
        try:
            return config.values[key]
        except KeyError as exc:
            raise RuntimeConfigResolverError(f"unknown runtime config key: {key}") from exc

    def _apply_layer(
        self,
        values: dict[str, EffectiveRuntimeConfigValue],
        layer: RuntimeConfigLayer,
    ) -> None:
        for key_name, raw_value in layer.values.items():
            key = self.registry.get(key_name)
            values[key_name] = EffectiveRuntimeConfigValue(
                key=key_name,
                value=_normalize_value(key, raw_value),
                source=layer.source,
                mutability=key.mutability,
                effective_status=_effective_status(key.mutability, layer.source),
                redacted=key.secret,
            )


def environment_runtime_config_layer(
    env: Mapping[str, str] | None = None,
    *,
    priority: int = 90,
) -> RuntimeConfigLayer:
    """Build a runtime config layer from current environment variables."""

    source_env = os.environ if env is None else env
    values: dict[str, Any] = {}
    if provider := _non_empty(source_env.get("LLM_PROVIDER")):
        values["llm.default_provider"] = provider
    if model := _non_empty(source_env.get("LLM_MODEL")):
        values["llm.default_model"] = model
    if timeout := _positive_float(source_env.get("LLM_REQUEST_TIMEOUT_SECONDS")):
        values["llm.request_timeout_seconds"] = timeout
    if backend := _non_empty(source_env.get("PLATO_COMPUTER_USE_BACKEND")):
        normalized_backend = backend.strip().lower()
        values["computer_use.backend"] = normalized_backend
        values["computer_use.enabled"] = normalized_backend != "disabled"
    if allowed := _csv(source_env.get("PLATO_COMPUTER_USE_ALLOWED_APPS")):
        values["computer_use.allowed_apps"] = allowed
    coordinate_click = _optional_bool(source_env.get("PLATO_COMPUTER_USE_ALLOW_COORDINATE_CLICK"))
    if coordinate_click is not None:
        values["computer_use.allow_coordinate_click"] = coordinate_click
    screen_recording_required = _optional_bool(
        source_env.get("PLATO_COMPUTER_USE_SCREEN_RECORDING_REQUIRED")
    )
    if screen_recording_required is not None:
        values["computer_use.screen_recording_required"] = screen_recording_required
    max_text_chars = _positive_int(source_env.get("PLATO_COMPUTER_USE_MAX_TEXT_CHARS"))
    if max_text_chars is not None:
        values["computer_use.max_text_chars"] = max_text_chars
    read_only_inquiry = _optional_bool(source_env.get("PLATO_ENABLE_READ_ONLY_INQUIRY_LLM"))
    if read_only_inquiry is not None:
        values["read_only_inquiry.llm_enabled"] = read_only_inquiry
    web_search = _optional_bool(source_env.get("PLATO_WEB_SEARCH_ENABLED"))
    if web_search is not None:
        values["web.search_enabled"] = web_search
    web_fetch_limits = _web_fetch_limits(source_env)
    if web_fetch_limits:
        values["web.fetch_limits"] = web_fetch_limits
    trace_enabled = _optional_bool(source_env.get("PLATO_MAIN_PAGE_TRACE"))
    if trace_enabled is not None:
        values["debug.main_page_trace_enabled"] = trace_enabled
    trace_print = _optional_bool(source_env.get("PLATO_MAIN_PAGE_TRACE_PRINT"))
    trace_file = _non_empty(source_env.get("PLATO_MAIN_PAGE_TRACE_FILE"))
    if trace_print is not None or trace_file is not None:
        values["debug.main_page_trace_sink"] = {
            "print": bool(trace_print) if trace_print is not None else False,
            "file": trace_file,
        }
    return RuntimeConfigLayer(
        source=RuntimeConfigSource(
            source_id="environment",
            kind="environment",
            scope=RuntimeConfigScope(level="process"),
            priority=priority,
        ),
        values=values,
    )


def process_runtime_config_layer(
    values: Mapping[str, Any],
    *,
    source_id: str = "process_input",
    priority: int = 100,
) -> RuntimeConfigLayer:
    """Build a high-priority layer from already parsed process inputs."""

    return RuntimeConfigLayer(
        source=RuntimeConfigSource(
            source_id=source_id,
            kind="process_input",
            scope=RuntimeConfigScope(level="process"),
            priority=priority,
        ),
        values=dict(values),
    )


def _normalize_value(key: RuntimeConfigKey, value: Any) -> Any:
    if value is None:
        return None
    if key.value_type == "bool":
        if not isinstance(value, bool):
            raise RuntimeConfigResolverError(f"{key.key} must be bool")
        return value
    if key.value_type == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise RuntimeConfigResolverError(f"{key.key} must be int")
        return value
    if key.value_type == "float":
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise RuntimeConfigResolverError(f"{key.key} must be float")
        return float(value)
    if key.value_type == "string":
        if not isinstance(value, str):
            raise RuntimeConfigResolverError(f"{key.key} must be string")
        return value
    if key.value_type == "string_list":
        if not isinstance(value, (tuple, list)):
            raise RuntimeConfigResolverError(f"{key.key} must be string list")
        if not all(isinstance(item, str) for item in value):
            raise RuntimeConfigResolverError(f"{key.key} must contain only strings")
        return tuple(value)
    if key.value_type == "object":
        if not isinstance(value, Mapping):
            raise RuntimeConfigResolverError(f"{key.key} must be object")
        return dict(value)
    raise RuntimeConfigResolverError(f"{key.key} has unsupported value type {key.value_type}")


def _effective_status(
    mutability: RuntimeConfigMutability,
    source: RuntimeConfigSource,
) -> RuntimeConfigEffectiveStatus:
    if source.kind != "runtime_patch":
        return "active"
    if mutability == "live":
        return "active"
    if mutability == "next_context_build":
        return "pending_next_context_build"
    if mutability == "next_llm_call":
        return "pending_next_llm_call"
    if mutability == "next_action":
        return "pending_next_action"
    if mutability == "next_agent_run":
        return "pending_next_agent_run"
    if mutability == "next_task":
        return "pending_next_task"
    if mutability == "next_session":
        return "pending_next_session"
    return "pending_restart"


def _config_hash(values: Mapping[str, EffectiveRuntimeConfigValue]) -> str:
    payload = {
        key: {
            "value": value.value,
            "source": value.source.source_id,
            "kind": value.source.kind,
            "mutability": value.mutability,
            "effectiveStatus": value.effective_status,
            "redacted": value.redacted,
        }
        for key, value in sorted(values.items())
    }
    encoded = json.dumps(payload, sort_keys=True, default=list, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _unique_sources(*sources: RuntimeConfigSource) -> tuple[RuntimeConfigSource, ...]:
    seen: set[str] = set()
    result: list[RuntimeConfigSource] = []
    for source in sorted(sources, key=lambda item: item.priority):
        if source.source_id in seen:
            continue
        seen.add(source.source_id)
        result.append(source)
    return tuple(result)


def _non_empty(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _positive_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    parsed = float(value)
    if parsed <= 0:
        raise RuntimeConfigResolverError("timeout value must be positive")
    return parsed


def _positive_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeConfigResolverError(f"invalid integer environment value: {value!r}") from exc
    if parsed <= 0:
        raise RuntimeConfigResolverError("integer environment value must be positive")
    return parsed


def _web_fetch_limits(source_env: Mapping[str, str]) -> dict[str, int]:
    env_to_key = {
        "PLATO_WEB_FETCH_MAX_URLS": "maxUrls",
        "PLATO_WEB_FETCH_MAX_CHARS_PER_URL": "maxCharsPerUrl",
        "PLATO_WEB_FETCH_MAX_TOTAL_CHARS": "maxTotalChars",
    }
    values: dict[str, int] = {}
    for env_key, config_key in env_to_key.items():
        parsed = _positive_int(source_env.get(env_key))
        if parsed is not None:
            values[config_key] = parsed
    return values


def _csv(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeConfigResolverError(f"invalid boolean environment value: {value!r}")


__all__ = [
    "RuntimeConfigResolver",
    "RuntimeConfigResolverError",
    "environment_runtime_config_layer",
    "process_runtime_config_layer",
    "resolve_default_runtime_config",
]
