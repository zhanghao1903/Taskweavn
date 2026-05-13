"""Pydantic models for configurable structured logging."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from taskweavn.observability.levels import LogLevel, normalize_level

LogCategory = Literal[
    "action",
    "observation",
    "llm",
    "task",
    "tool",
    "bus",
    "agent",
    "session",
    "runtime",
    "sandbox",
    "audit",
    "risk",
    "gate",
    "wait",
    "config",
]

PayloadMode = Literal["summary", "full", "off"]
SinkFormat = Literal["jsonl", "pretty"]
SinkType = Literal["file", "console", "null"]

LOG_CATEGORIES: tuple[LogCategory, ...] = (
    "action",
    "observation",
    "llm",
    "task",
    "tool",
    "bus",
    "agent",
    "session",
    "runtime",
    "sandbox",
    "audit",
    "risk",
    "gate",
    "wait",
    "config",
)


class LogContext(BaseModel):
    """Stable, filterable context shared by all structured log events."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    trace_id: str | None = None
    action_id: str | None = None
    observation_id: str | None = None
    message_id: str | None = None
    tool_name: str | None = None
    model: str | None = None
    provider: str | None = None
    provider_request_id: str | None = None
    workspace_root: str | None = None


class RotationConfig(BaseModel):
    """Size-based rotation config for file sinks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_bytes: int | None = 10 * 1024 * 1024
    backup_count: int = 5

    @model_validator(mode="after")
    def _validate_rotation(self) -> RotationConfig:
        if self.max_bytes is not None and self.max_bytes <= 0:
            raise ValueError("max_bytes must be positive or None")
        if self.backup_count < 0:
            raise ValueError("backup_count must be non-negative")
        return self


class LogSinkConfig(BaseModel):
    """Configuration for one output sink."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    type: SinkType
    path_template: str | None = None
    format: SinkFormat = "jsonl"
    rotation: RotationConfig | None = None

    @model_validator(mode="after")
    def _validate_path(self) -> LogSinkConfig:
        if self.type == "file" and not self.path_template:
            raise ValueError("file sink requires path_template")
        return self


class LogRule(BaseModel):
    """Effective logging behavior for a category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: LogCategory
    level: LogLevel = "INFO"
    sinks: tuple[str, ...] = ("session_file",)
    payload_mode: PayloadMode = "summary"
    redact: bool = True

    @field_validator("level", mode="before")
    @classmethod
    def _normalize_level(cls, value: object) -> object:
        if isinstance(value, (str, int)):
            return normalize_level(value)
        return value


class LogScope(BaseModel):
    """Scope used by overrides and future object-level matching."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    tool_name: str | None = None
    model: str | None = None
    provider: str | None = None

    def matches(self, context: LogContext | None) -> bool:
        """Return True when all non-null scope fields match the context."""
        if context is None:
            return not any(self.model_dump(exclude_none=True).values())
        for key, expected in self.model_dump(exclude_none=True).items():
            if getattr(context, key) != expected:
                return False
        return True


class LogOverride(BaseModel):
    """A scoped override over a category rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: LogScope
    category: LogCategory
    level: LogLevel | None = None
    sinks: tuple[str, ...] | None = None
    payload_mode: PayloadMode | None = None
    expires_at: datetime | None = None

    @field_validator("level", mode="before")
    @classmethod
    def _normalize_level(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, (str, int)):
            return normalize_level(value)
        return value


class LoggingConfigPatch(BaseModel):
    """Small patch language for profiles/session overrides."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    default_level: LogLevel | None = None
    rules: dict[LogCategory, LogRule] = Field(default_factory=dict)
    overrides: tuple[LogOverride, ...] = ()

    @field_validator("default_level", mode="before")
    @classmethod
    def _normalize_default_level(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, (str, int)):
            return normalize_level(value)
        return value


class LoggingProfile(BaseModel):
    """Named user-friendly logging config patch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str
    patch: LoggingConfigPatch = Field(default_factory=LoggingConfigPatch)


class LoggingConfig(BaseModel):
    """Top-level structured logging config."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1"] = "1"
    enabled: bool = True
    default_level: LogLevel = "INFO"
    archive_root: str
    sinks: dict[str, LogSinkConfig]
    rules: dict[LogCategory, LogRule]
    profiles: dict[str, LoggingProfile] = Field(default_factory=dict)
    session_overrides: dict[str, LoggingConfigPatch] = Field(default_factory=dict)
    overrides: tuple[LogOverride, ...] = ()

    @field_validator("default_level", mode="before")
    @classmethod
    def _normalize_default_level(cls, value: object) -> object:
        if isinstance(value, (str, int)):
            return normalize_level(value)
        return value

    @model_validator(mode="after")
    def _validate_references(self) -> LoggingConfig:
        known_sinks = set(self.sinks)
        for rule in self.rules.values():
            unknown = [sink for sink in rule.sinks if sink not in known_sinks]
            if unknown:
                raise ValueError(
                    f"rule {rule.category!r} references unknown sinks: {unknown}"
                )
        return self


class EffectiveLogRule(BaseModel):
    """Resolved category rule after global/session/override application."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: LogCategory
    level: LogLevel
    sinks: tuple[str, ...]
    payload_mode: PayloadMode
    redact: bool


class LogEvent(BaseModel):
    """One structured log event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ts: datetime
    level: LogLevel
    category: LogCategory
    event: str
    message: str
    context: LogContext = Field(default_factory=LogContext)
    data: dict[str, Any] = Field(default_factory=dict)
    schema_version: Literal["1"] = "1"

    @field_validator("level", mode="before")
    @classmethod
    def _normalize_level(cls, value: object) -> object:
        if isinstance(value, (str, int)):
            return normalize_level(value)
        return value


class LogArchiveManifest(BaseModel):
    """Manifest written under one session log archive directory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1"] = "1"
    session_id: str
    created_at: datetime
    closed_at: datetime | None = None
    config_hash: str
    active_config_path: str | None = None
    archive_root: str
    files: dict[str, str] = Field(default_factory=dict)
    templates: dict[str, str] = Field(default_factory=dict)
    rotation: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "EffectiveLogRule",
    "LOG_CATEGORIES",
    "LogArchiveManifest",
    "LogCategory",
    "LogContext",
    "LogEvent",
    "LogOverride",
    "LogRule",
    "LogScope",
    "LogSinkConfig",
    "LoggingConfig",
    "LoggingConfigPatch",
    "LoggingProfile",
    "PayloadMode",
    "RotationConfig",
    "SinkFormat",
    "SinkType",
]
