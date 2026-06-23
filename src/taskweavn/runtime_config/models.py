"""Typed contracts for Plato runtime configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

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

RuntimeConfigActorType = Literal["user", "system", "test", "migration"]
RuntimeConfigChangeStatus = Literal["accepted", "rejected", "no_op"]
RuntimeConfigRejectionCode = Literal[
    "unknown_key",
    "unsupported_scope",
    "invalid_value",
    "secret_not_patchable",
    "startup_only_not_patchable",
    "stale_base_config",
    "higher_priority_source_active",
    "policy_denied",
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


class RuntimeConfigActor(RuntimeConfigModel):
    """Actor metadata for a requested runtime config change."""

    actor_type: RuntimeConfigActorType
    actor_id: str | None = Field(default=None, min_length=1)
    display_name: str | None = Field(default=None, min_length=1)


class RuntimeConfigPatch(RuntimeConfigModel):
    """Sparse requested runtime config mutation before validation/persistence."""

    patch_id: str = Field(min_length=1)
    idempotency_key: str | None = Field(default=None, min_length=1)
    scope: RuntimeConfigScope
    actor: RuntimeConfigActor
    reason: str | None = Field(default=None, min_length=1)
    values: dict[str, Any] = Field(min_length=1)
    expected_base_config_hash: str | None = Field(default=None, min_length=1)
    dry_run: bool = False
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _scope_has_required_ids(self) -> RuntimeConfigPatch:
        _validate_scope_identifiers(self.scope)
        return self


class RuntimeConfigRejection(RuntimeConfigModel):
    """Per-key rejection detail for a runtime config patch."""

    code: RuntimeConfigRejectionCode
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class RuntimeConfigChange(RuntimeConfigModel):
    """Durable runtime config change ledger entry."""

    change_id: str = Field(min_length=1)
    patch_id: str = Field(min_length=1)
    idempotency_key: str | None = Field(default=None, min_length=1)
    scope: RuntimeConfigScope
    actor: RuntimeConfigActor
    reason: str | None = Field(default=None, min_length=1)
    status: RuntimeConfigChangeStatus
    requested_values: dict[str, Any] = Field(default_factory=dict)
    accepted_values: dict[str, Any] = Field(default_factory=dict)
    rejected_values: dict[str, RuntimeConfigRejection] = Field(default_factory=dict)
    redacted_keys: tuple[str, ...] = ()
    base_config_hash: str = Field(min_length=1)
    resulting_config_hash: str | None = Field(default=None, min_length=1)
    effective_status_by_key: dict[str, RuntimeConfigEffectiveStatus] = Field(
        default_factory=dict
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _change_is_consistent(self) -> RuntimeConfigChange:
        _validate_scope_identifiers(self.scope)
        accepted_keys = set(self.accepted_values)
        rejected_keys = set(self.rejected_values)
        overlap_keys = accepted_keys & rejected_keys
        if overlap_keys:
            raise ValueError("config keys cannot be both accepted and rejected")
        missing_redacted_keys = set(self.redacted_keys) - set(self.requested_values)
        if missing_redacted_keys:
            raise ValueError("redacted keys must be present in requested values")
        if self.status == "rejected":
            if self.accepted_values:
                raise ValueError("rejected config change cannot include accepted values")
            if self.resulting_config_hash is not None:
                raise ValueError("rejected config change cannot include resulting hash")
        if self.status == "accepted":
            if not self.accepted_values:
                raise ValueError("accepted config change requires accepted values")
            if self.resulting_config_hash is None:
                raise ValueError("accepted config change requires resulting hash")
        if self.status == "no_op":
            if self.accepted_values or self.rejected_values:
                raise ValueError("no-op config change cannot accept or reject values")
            if self.resulting_config_hash != self.base_config_hash:
                raise ValueError("no-op config change must preserve config hash")
        missing_status_keys = accepted_keys - set(self.effective_status_by_key)
        if missing_status_keys:
            raise ValueError("accepted config values require effective status entries")
        return self


class RuntimeConfigSnapshotRecord(RuntimeConfigModel):
    """Durable effective runtime config snapshot record."""

    snapshot_id: str = Field(min_length=1)
    config_hash: str = Field(min_length=1)
    scope: RuntimeConfigScope
    effective_config: EffectiveRuntimeConfig
    created_by_change_id: str | None = Field(default=None, min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _snapshot_matches_effective_config(self) -> RuntimeConfigSnapshotRecord:
        _validate_scope_identifiers(self.scope)
        if self.config_hash != self.effective_config.config_hash:
            raise ValueError("snapshot config_hash must match effective config hash")
        if self.scope != self.effective_config.scope:
            raise ValueError("snapshot scope must match effective config scope")
        return self


def _validate_scope_identifiers(scope: RuntimeConfigScope) -> None:
    required_by_level: dict[RuntimeConfigScopeLevel, tuple[str, ...]] = {
        "global": (),
        "process": (),
        "workspace": ("workspace_id",),
        "session": ("workspace_id", "session_id"),
        "task": ("workspace_id", "session_id", "task_id"),
        "agent_run": ("workspace_id", "session_id", "task_id", "agent_run_id"),
    }
    missing = [
        field_name
        for field_name in required_by_level[scope.level]
        if getattr(scope, field_name) is None
    ]
    if missing:
        raise ValueError(
            f"{scope.level} runtime config scope requires: {', '.join(missing)}"
        )


__all__ = [
    "EffectiveRuntimeConfig",
    "EffectiveRuntimeConfigValue",
    "RuntimeConfigActor",
    "RuntimeConfigActorType",
    "RuntimeConfigChange",
    "RuntimeConfigChangeStatus",
    "RuntimeConfigEffectiveStatus",
    "RuntimeConfigKey",
    "RuntimeConfigLayer",
    "RuntimeConfigModel",
    "RuntimeConfigMutability",
    "RuntimeConfigPatch",
    "RuntimeConfigRejection",
    "RuntimeConfigRejectionCode",
    "RuntimeConfigScope",
    "RuntimeConfigScopeLevel",
    "RuntimeConfigSnapshotRecord",
    "RuntimeConfigSource",
    "RuntimeConfigSourceKind",
    "RuntimeConfigValueType",
    "to_camel",
]
