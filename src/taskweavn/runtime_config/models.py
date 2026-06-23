"""Typed contracts for Plato runtime configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

RuntimeConfigScopeLevel = Literal[
    "global",
    "workspace",
    "session",
    "task",
    "agent_run",
    "process",
]

RuntimeConfigSourceKind = Literal[
    "built_in_default",
    "environment",
    "cli",
    "settings_store",
    "workspace_file",
    "session_override",
    "task_override",
    "runtime_patch",
    "process_input",
]

RuntimeConfigMutability = Literal[
    "live",
    "next_context_build",
    "next_llm_call",
    "next_action",
    "next_agent_run",
    "next_task",
    "next_session",
    "startup_only",
    "migration_only",
]

RuntimeConfigEffectiveStatus = Literal[
    "active",
    "pending_next_context_build",
    "pending_next_llm_call",
    "pending_next_action",
    "pending_next_agent_run",
    "pending_next_task",
    "pending_next_session",
    "pending_restart",
]

RuntimeConfigValueType = Literal[
    "bool",
    "int",
    "float",
    "string",
    "string_list",
    "object",
]


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class RuntimeConfigModel(BaseModel):
    """Base model for immutable runtime configuration contracts."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        validate_assignment=True,
    )


class RuntimeConfigScope(RuntimeConfigModel):
    """Scope for resolving or explaining runtime configuration."""

    level: RuntimeConfigScopeLevel = "process"
    workspace_id: str | None = None
    session_id: str | None = None
    task_id: str | None = None
    agent_run_id: str | None = None


class RuntimeConfigKey(RuntimeConfigModel):
    """Registry metadata for a supported runtime configuration key."""

    key: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    value_type: RuntimeConfigValueType
    default_value: Any
    scope_levels: tuple[RuntimeConfigScopeLevel, ...]
    mutability: RuntimeConfigMutability
    description: str = Field(min_length=1)
    source_hints: tuple[RuntimeConfigSourceKind, ...] = ("built_in_default",)
    user_visible: bool = True
    secret: bool = False
    restart_required: bool = False

    @field_validator("domain")
    @classmethod
    def _domain_matches_key(cls, value: str, info: ValidationInfo) -> str:
        key = info.data.get("key")
        if isinstance(key, str) and "." in key and key.split(".", 1)[0] != value:
            raise ValueError("domain must match key prefix")
        return value

    @field_validator("scope_levels", "source_hints")
    @classmethod
    def _not_empty(cls, value: tuple[Any, ...]) -> tuple[Any, ...]:
        if not value:
            raise ValueError("tuple must not be empty")
        return value


class RuntimeConfigSource(RuntimeConfigModel):
    """Source layer for an effective runtime configuration value."""

    source_id: str = Field(min_length=1)
    kind: RuntimeConfigSourceKind
    scope: RuntimeConfigScope = Field(default_factory=RuntimeConfigScope)
    priority: int = 0


class RuntimeConfigLayer(RuntimeConfigModel):
    """Concrete values from one source layer."""

    source: RuntimeConfigSource
    values: dict[str, Any] = Field(default_factory=dict)


class EffectiveRuntimeConfigValue(RuntimeConfigModel):
    """Resolved value plus source and lifecycle explanation."""

    key: str = Field(min_length=1)
    value: Any
    source: RuntimeConfigSource
    mutability: RuntimeConfigMutability
    effective_status: RuntimeConfigEffectiveStatus
    redacted: bool = False


class EffectiveRuntimeConfig(RuntimeConfigModel):
    """Immutable runtime configuration snapshot."""

    config_id: str = Field(min_length=1)
    scope: RuntimeConfigScope
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    schema_version: str = "plato.runtime_config.v1"
    values: dict[str, EffectiveRuntimeConfigValue]
    source_layers: tuple[RuntimeConfigSource, ...]
    config_hash: str = Field(min_length=1)


__all__ = [
    "EffectiveRuntimeConfig",
    "EffectiveRuntimeConfigValue",
    "RuntimeConfigEffectiveStatus",
    "RuntimeConfigKey",
    "RuntimeConfigLayer",
    "RuntimeConfigModel",
    "RuntimeConfigMutability",
    "RuntimeConfigScope",
    "RuntimeConfigScopeLevel",
    "RuntimeConfigSource",
    "RuntimeConfigSourceKind",
    "RuntimeConfigValueType",
    "to_camel",
]
