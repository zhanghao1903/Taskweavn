"""Same-process control surface for configurable logging."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from taskweavn.observability.levels import LogLevel, normalize_level
from taskweavn.observability.manager import LoggingManager, get_logging_manager
from taskweavn.observability.models import (
    EffectiveLogRule,
    LogArchiveManifest,
    LogCategory,
    LogContext,
)

LoggingControlOperation = Literal["apply_profile", "set_level", "close_session"]


class LoggingProfileInfo(BaseModel):
    """User-facing summary of one named logging profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str


class LoggingControlResult(BaseModel):
    """Typed response returned by the logging control service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: LoggingControlOperation
    config_hash: str
    session_id: str | None = None
    category: LogCategory | None = None
    level: LogLevel | None = None
    profile: str | None = None
    duration_seconds: float | None = None
    manifest: LogArchiveManifest | None = None


class LoggingControlService:
    """Hot-update API for in-process UI/server control planes.

    CLI archive inspection reads files from disk, but cannot modify another
    already-running process. This service is the reusable same-process entry:
    a future web UI, daemon, or debug endpoint can call it to change the
    active :class:`LoggingManager` without restarting the agent.
    """

    def __init__(self, manager: LoggingManager | None = None) -> None:
        self._manager = manager or get_logging_manager()

    def list_profiles(self) -> tuple[LoggingProfileInfo, ...]:
        """List profiles from the active config."""
        return tuple(
            LoggingProfileInfo(name=name, description=profile.description)
            for name, profile in sorted(self._manager.config.profiles.items())
        )

    def get_effective_rule(
        self,
        *,
        category: LogCategory,
        session_id: str | None = None,
    ) -> EffectiveLogRule:
        """Resolve one category rule for the optional session scope."""
        return self._manager.get_effective_rule(
            category,
            LogContext(session_id=session_id),
        )

    def apply_profile(
        self,
        *,
        session_id: str,
        profile_name: str,
        write_manifest: bool = True,
    ) -> LoggingControlResult:
        """Apply a named profile to one session and optionally refresh manifest."""
        self._manager.apply_profile(session_id, profile_name)
        manifest = (
            self._manager.write_session_manifest(session_id)
            if write_manifest
            else None
        )
        self._manager.emit(
            "config",
            "INFO",
            "profile_applied",
            context=LogContext(session_id=session_id),
            data={
                "profile": profile_name,
                "config_hash": self._manager.config_hash(),
            },
        )
        return LoggingControlResult(
            operation="apply_profile",
            session_id=session_id,
            profile=profile_name,
            config_hash=self._manager.config_hash(),
            manifest=manifest,
        )

    def set_level(
        self,
        *,
        category: LogCategory,
        level: LogLevel | str | int,
        session_id: str | None = None,
        duration_seconds: float | None = None,
        write_manifest: bool = True,
    ) -> LoggingControlResult:
        """Set a global or session-scoped category level."""
        normalized = normalize_level(level)
        self._manager.set_level(
            session_id=session_id,
            category=category,
            level=normalized,
            duration_seconds=duration_seconds,
        )
        manifest = (
            self._manager.write_session_manifest(session_id)
            if write_manifest and session_id is not None
            else None
        )
        self._manager.emit(
            "config",
            "INFO",
            "level_set",
            context=LogContext(session_id=session_id),
            data={
                "category": category,
                "level": normalized,
                "duration_seconds": duration_seconds,
                "config_hash": self._manager.config_hash(),
            },
        )
        return LoggingControlResult(
            operation="set_level",
            session_id=session_id,
            category=category,
            level=normalized,
            duration_seconds=duration_seconds,
            config_hash=self._manager.config_hash(),
            manifest=manifest,
        )

    def close_session_archive(self, *, session_id: str) -> LoggingControlResult:
        """Close one session archive manifest."""
        manifest = self._manager.close_session_archive(session_id)
        self._manager.emit(
            "config",
            "INFO",
            "session_archive_closed",
            context=LogContext(session_id=session_id),
            data={"config_hash": self._manager.config_hash()},
        )
        return LoggingControlResult(
            operation="close_session",
            session_id=session_id,
            config_hash=self._manager.config_hash(),
            manifest=manifest,
        )


__all__ = [
    "LoggingControlOperation",
    "LoggingControlResult",
    "LoggingControlService",
    "LoggingProfileInfo",
]
