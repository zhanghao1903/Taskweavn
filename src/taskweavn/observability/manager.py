"""Runtime manager for configurable structured logging."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from taskweavn.observability.context import merge_log_context
from taskweavn.observability.levels import LogLevel, level_enabled, normalize_level
from taskweavn.observability.models import (
    LOG_CATEGORIES,
    EffectiveLogRule,
    LogArchiveManifest,
    LogCategory,
    LogContext,
    LogEvent,
    LoggingConfig,
    LoggingConfigPatch,
    LoggingProfile,
    LogOverride,
    LogRule,
    LogScope,
    LogSinkConfig,
    RotationConfig,
)
from taskweavn.observability.redaction import redact_payload
from taskweavn.observability.sinks import LogSink, build_sink

LogData = Mapping[str, Any] | Callable[[], Mapping[str, Any]]


@dataclass(frozen=True)
class LoggingSnapshot:
    """Immutable runtime logging config snapshot."""

    config: LoggingConfig
    sinks: Mapping[str, LogSink]
    created_at: datetime


class LoggingManager:
    """Coordinates config resolution, hot updates, and sink dispatch."""

    def __init__(self, config: LoggingConfig | None = None) -> None:
        self._lock = threading.RLock()
        self._snapshot = self._build_snapshot(
            config or build_disabled_logging_config(Path("./logs"))
        )

    @property
    def config(self) -> LoggingConfig:
        """Return the active immutable logging config."""
        with self._lock:
            return self._snapshot.config

    def apply_config(self, config: LoggingConfig) -> None:
        """Atomically replace the active logging config."""
        new_snapshot = self._build_snapshot(config)
        with self._lock:
            old_snapshot = self._snapshot
            self._snapshot = new_snapshot
        for sink in old_snapshot.sinks.values():
            sink.close()
        self.emit(
            "config",
            "INFO",
            "updated",
            message="logging config updated",
            data={"configured_sinks": sorted(config.sinks)},
        )

    def get_effective_rule(
        self,
        category: LogCategory,
        context: LogContext | None = None,
    ) -> EffectiveLogRule:
        """Resolve the effective rule for a category/context pair."""
        return _resolve_effective_rule(
            self._snapshot.config,
            category,
            context,
            now=datetime.now(tz=UTC),
        )

    def is_enabled(
        self,
        category: LogCategory,
        level: LogLevel | str | int,
        context: LogContext | None = None,
    ) -> bool:
        """Return whether an event should be emitted."""
        config = self._snapshot.config
        if not config.enabled:
            return False
        rule = self.get_effective_rule(category, context)
        if rule.payload_mode == "off":
            return False
        return level_enabled(normalize_level(level), rule.level)

    def emit(
        self,
        category: LogCategory,
        level: LogLevel | str | int,
        event: str,
        *,
        message: str | None = None,
        context: LogContext | None = None,
        data: LogData | None = None,
    ) -> None:
        """Emit one structured log event if enabled."""
        normalized_level = normalize_level(level)
        resolved_context = merge_log_context(context)
        rule = self.get_effective_rule(category, resolved_context)
        if (
            not self._snapshot.config.enabled
            or rule.payload_mode == "off"
            or not level_enabled(normalized_level, rule.level)
        ):
            return

        payload: Mapping[str, Any]
        if data is None:
            payload = {}
        elif callable(data):
            payload = data()
        else:
            payload = data
        if rule.redact:
            payload = redact_payload(payload)

        log_event = LogEvent(
            ts=datetime.now(tz=UTC),
            level=normalized_level,
            category=category,
            event=event,
            message=message or event,
            context=resolved_context,
            data=dict(payload),
        )

        snapshot = self._snapshot
        for sink_name in rule.sinks:
            sink = snapshot.sinks.get(sink_name)
            if sink is not None:
                sink.emit(log_event)

    def apply_profile(self, session_id: str, profile_name: str) -> None:
        """Apply a named profile as a session override."""
        config = self._snapshot.config
        profile = config.profiles.get(profile_name)
        if profile is None:
            raise KeyError(f"unknown logging profile {profile_name!r}")
        self.update_session_config(session_id, profile.patch)

    def update_session_config(self, session_id: str, patch: LoggingConfigPatch) -> None:
        """Replace a session-level logging patch."""
        config = self._snapshot.config
        session_overrides = dict(config.session_overrides)
        session_overrides[session_id] = patch
        self.apply_config(config.model_copy(update={"session_overrides": session_overrides}))

    def set_level(
        self,
        *,
        session_id: str | None,
        category: LogCategory,
        level: LogLevel | str | int,
        duration_seconds: float | None = None,
    ) -> None:
        """Set a category level globally or for one session."""
        if duration_seconds is not None and duration_seconds < 0:
            raise ValueError("duration_seconds must be >= 0 or None")
        normalized = normalize_level(level)
        expires_at = (
            datetime.now(tz=UTC) + timedelta(seconds=duration_seconds)
            if duration_seconds is not None
            else None
        )
        override = LogOverride(
            scope=LogScope(session_id=session_id),
            category=category,
            level=normalized,
            expires_at=expires_at,
        )
        config = self._snapshot.config
        self.apply_config(config.model_copy(update={"overrides": (*config.overrides, override)}))

    def config_hash(self) -> str:
        """Return a stable short hash of the active config."""
        return _config_hash(self._snapshot.config)

    def session_archive_dir(self, session_id: str) -> Path:
        """Return the archive directory for a session."""
        return Path(self._snapshot.config.archive_root) / "sessions" / session_id

    def write_session_manifest(
        self,
        session_id: str,
        *,
        active_config_path: Path | str | None = None,
        closed_at: datetime | None = None,
    ) -> LogArchiveManifest:
        """Write and return ``manifest.json`` for a session archive.

        The manifest is a stable lookup table for UI, testers, and archive
        scripts. It lists configured file sinks even before the first log line
        is written, so callers can discover where each category will land.
        """
        with self._lock:
            snapshot = self._snapshot
        session_dir = Path(snapshot.config.archive_root) / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = session_dir / "manifest.json"

        existing = _read_manifest(manifest_path)
        created_at = existing.created_at if existing is not None else datetime.now(tz=UTC)
        files, templates = _session_archive_files(snapshot.config, session_id)
        manifest = LogArchiveManifest(
            session_id=session_id,
            created_at=created_at,
            closed_at=closed_at if closed_at is not None else (
                existing.closed_at if existing is not None else None
            ),
            config_hash=_config_hash(snapshot.config),
            active_config_path=str(active_config_path) if active_config_path is not None else (
                existing.active_config_path if existing is not None else None
            ),
            archive_root=str(Path(snapshot.config.archive_root)),
            files=files,
            templates=templates,
            rotation=_rotation_summary(snapshot.config),
        )
        manifest_path.write_text(
            manifest.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8",
        )
        return manifest

    def close_session_archive(self, session_id: str) -> LogArchiveManifest:
        """Mark a session archive manifest closed."""
        return self.write_session_manifest(session_id, closed_at=datetime.now(tz=UTC))

    def close(self) -> None:
        """Close all active sinks."""
        with self._lock:
            snapshot = self._snapshot
        for sink in snapshot.sinks.values():
            sink.close()

    def _build_snapshot(self, config: LoggingConfig) -> LoggingSnapshot:
        archive_root = Path(config.archive_root)
        sinks = {
            name: build_sink(sink_config, archive_root=archive_root)
            for name, sink_config in config.sinks.items()
        }
        return LoggingSnapshot(
            config=config,
            sinks=sinks,
            created_at=datetime.now(tz=UTC),
        )


def _apply_patch_rule(
    rule: EffectiveLogRule,
    patch_rule: LogRule | None,
) -> EffectiveLogRule:
    if patch_rule is None:
        return rule
    return EffectiveLogRule(
        category=rule.category,
        level=patch_rule.level,
        sinks=patch_rule.sinks,
        payload_mode=patch_rule.payload_mode,
        redact=patch_rule.redact,
    )


def _apply_config_patch_rule(
    rule: EffectiveLogRule,
    patch: LoggingConfigPatch,
) -> EffectiveLogRule:
    patch_rule = patch.rules.get(rule.category)
    if patch_rule is not None:
        return _apply_patch_rule(rule, patch_rule)
    if patch.default_level is None:
        return rule
    return EffectiveLogRule(
        category=rule.category,
        level=patch.default_level,
        sinks=rule.sinks,
        payload_mode=rule.payload_mode,
        redact=rule.redact,
    )


def _apply_override(rule: EffectiveLogRule, override: LogOverride) -> EffectiveLogRule:
    return EffectiveLogRule(
        category=rule.category,
        level=override.level or rule.level,
        sinks=override.sinks or rule.sinks,
        payload_mode=override.payload_mode or rule.payload_mode,
        redact=rule.redact,
    )


def _resolve_effective_rule(
    config: LoggingConfig,
    category: LogCategory,
    context: LogContext | None,
    *,
    now: datetime,
) -> EffectiveLogRule:
    base = config.rules.get(
        category,
        LogRule(
            category=category,
            level=config.default_level,
            sinks=(),
            payload_mode="summary",
        ),
    )
    rule = EffectiveLogRule(
        category=category,
        level=base.level,
        sinks=base.sinks,
        payload_mode=base.payload_mode,
        redact=base.redact,
    )

    if context is not None and context.session_id is not None:
        patch = config.session_overrides.get(context.session_id)
        if patch is not None:
            rule = _apply_config_patch_rule(rule, patch)

    for override in config.overrides:
        if override.category != category:
            continue
        if override.expires_at is not None and override.expires_at <= now:
            continue
        if not override.scope.matches(context):
            continue
        rule = _apply_override(rule, override)

    return rule


def build_session_logging_config(
    log_dir: Path | str,
    *,
    level: str | int = logging.INFO,
) -> LoggingConfig:
    """Build the default session-archive structured logging config."""
    directory = Path(log_dir)
    normalized = normalize_level(level)
    sinks = {
        "session_file": LogSinkConfig(
            name="session_file",
            type="file",
            path_template="{archive_root}/sessions/{session_id}/{category}.jsonl",
            format="jsonl",
            rotation=RotationConfig(),
        ),
        "global_config_file": LogSinkConfig(
            name="global_config_file",
            type="file",
            path_template="{archive_root}/global/{category}.jsonl",
            format="jsonl",
            rotation=RotationConfig(),
        ),
    }
    rules = {
        category: LogRule(
            category=category,
            level=normalized,
            sinks=("session_file",),
            payload_mode="summary",
        )
        for category in LOG_CATEGORIES
    }
    rules["config"] = LogRule(
        category="config",
        level="INFO",
        sinks=("session_file", "global_config_file"),
        payload_mode="summary",
    )
    return LoggingConfig(
        archive_root=str(directory),
        sinks=sinks,
        rules=rules,
        profiles=_default_profiles(),
    )


def build_legacy_logging_config(
    log_dir: Path | str,
    *,
    level: str | int = logging.INFO,
) -> LoggingConfig:
    """Build a config that preserves the old per-channel file layout."""
    directory = Path(log_dir)
    sinks: dict[str, LogSinkConfig] = {}
    rules: dict[LogCategory, LogRule] = {}
    for category in ("tool", "action", "observation", "llm", "config"):
        sink_name = f"{category}_file"
        suffix = ".log" if category != "config" else ".log"
        sinks[sink_name] = LogSinkConfig(
            name=sink_name,
            type="file",
            path_template=f"{{archive_root}}/{category}{suffix}",
            format="jsonl",
            rotation=None,
        )
        rules[category] = LogRule(
            category=category,
            level=normalize_level(level),
            sinks=(sink_name,),
            payload_mode="full",
        )
    sinks["session_file"] = LogSinkConfig(
        name="session_file",
        type="file",
        path_template="{archive_root}/{category}.log",
        format="jsonl",
        rotation=None,
    )

    return LoggingConfig(
        archive_root=str(directory),
        sinks=sinks,
        rules=rules,
        profiles=_default_profiles(),
    )


def build_disabled_logging_config(log_dir: Path | str) -> LoggingConfig:
    """Build a silent config for process startup before logging is configured."""
    return LoggingConfig(
        enabled=False,
        archive_root=str(Path(log_dir)),
        sinks={},
        rules={},
        profiles=_default_profiles(),
    )


def _default_profiles() -> dict[str, LoggingProfile]:
    full_debug_rules = {
        category: LogRule(
            category=category,
            level="DEBUG",
            sinks=("session_file",),
            payload_mode="full",
        )
        for category in LOG_CATEGORIES
    }
    return {
        "normal": LoggingProfile(name="normal", description="Record normal summaries."),
        "quiet": LoggingProfile(
            name="quiet",
            description="Only warning and above.",
            patch=LoggingConfigPatch(default_level="WARNING"),
        ),
        "debug-llm": LoggingProfile(
            name="debug-llm",
            description="Enable full LLM debug payloads.",
            patch=LoggingConfigPatch(
                rules={
                    "llm": LogRule(
                        category="llm",
                        level="DEBUG",
                        sinks=("session_file",),
                        payload_mode="full",
                    )
                }
            ),
        ),
        "debug-tools": LoggingProfile(
            name="debug-tools",
            description="Enable debug payloads for tool/runtime/sandbox categories.",
            patch=LoggingConfigPatch(
                rules={
                    "tool": LogRule(
                        category="tool",
                        level="DEBUG",
                        sinks=("session_file",),
                        payload_mode="full",
                    ),
                    "runtime": LogRule(
                        category="runtime",
                        level="DEBUG",
                        sinks=("session_file",),
                        payload_mode="full",
                    ),
                    "sandbox": LogRule(
                        category="sandbox",
                        level="DEBUG",
                        sinks=("session_file",),
                        payload_mode="full",
                    ),
                }
            ),
        ),
        "debug-bus": LoggingProfile(
            name="debug-bus",
            description="Enable debug payloads for bus/task/agent/gate/wait categories.",
            patch=LoggingConfigPatch(
                rules={
                    "bus": LogRule(
                        category="bus",
                        level="DEBUG",
                        sinks=("session_file",),
                        payload_mode="full",
                    ),
                    "task": LogRule(
                        category="task",
                        level="DEBUG",
                        sinks=("session_file",),
                        payload_mode="full",
                    ),
                    "agent": LogRule(
                        category="agent",
                        level="DEBUG",
                        sinks=("session_file",),
                        payload_mode="full",
                    ),
                    "gate": LogRule(
                        category="gate",
                        level="DEBUG",
                        sinks=("session_file",),
                        payload_mode="full",
                    ),
                    "wait": LogRule(
                        category="wait",
                        level="DEBUG",
                        sinks=("session_file",),
                        payload_mode="full",
                    ),
                }
            ),
        ),
        "full-debug": LoggingProfile(
            name="full-debug",
            description="Enable full debug payloads for all categories.",
            patch=LoggingConfigPatch(rules=full_debug_rules),
        ),
    }


def _config_hash(config: LoggingConfig) -> str:
    payload = json.dumps(
        config.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _read_manifest(path: Path) -> LogArchiveManifest | None:
    if not path.exists():
        return None
    return LogArchiveManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _session_archive_files(
    config: LoggingConfig,
    session_id: str,
) -> tuple[dict[str, str], dict[str, str]]:
    files: dict[str, str] = {}
    templates: dict[str, str] = {}
    archive_root = Path(config.archive_root)
    session_dir = archive_root / "sessions" / session_id
    context = LogContext(session_id=session_id)
    now = datetime.now(tz=UTC)
    for category in LOG_CATEGORIES:
        rule = _resolve_effective_rule(config, category, context, now=now)
        for sink_name in rule.sinks:
            sink = config.sinks.get(sink_name)
            if sink is None or sink.type != "file" or sink.path_template is None:
                continue
            display_template = _display_template(
                sink.path_template,
                archive_root,
                category,
                context,
                session_dir,
            )
            if "{" in display_template or "}" in display_template:
                key = _archive_key(category, sink_name, templates)
                templates[key] = display_template
                continue
            path = _render_path(sink.path_template, archive_root, category, context)
            key = _archive_key(category, sink_name, files)
            files[key] = _display_path(path, session_dir, archive_root)
    return files, templates


def _rotation_summary(config: LoggingConfig) -> dict[str, Any]:
    rotations = [
        sink.rotation
        for sink in config.sinks.values()
        if sink.type == "file" and sink.rotation is not None
    ]
    if not rotations:
        return {"enabled": False}
    return {
        "enabled": True,
        "max_bytes": max(
            (rotation.max_bytes or 0) for rotation in rotations
        ) or None,
        "backup_count": max(rotation.backup_count for rotation in rotations),
    }


def _render_path(
    template: str,
    archive_root: Path,
    category: LogCategory,
    context: LogContext,
) -> Path:
    values = {
        "archive_root": str(archive_root),
        "category": category,
        "session_id": context.session_id or "_unknown",
        "task_id": context.task_id or "_unknown",
        "agent_id": context.agent_id or "_unknown",
        "date": datetime.now(tz=UTC).date().isoformat(),
    }
    return Path(template.format_map(_DefaultMapping(values)))


def _display_path(path: Path, session_dir: Path, archive_root: Path) -> str:
    for base in (session_dir, archive_root):
        try:
            return str(path.relative_to(base))
        except ValueError:
            continue
    return str(path)


def _display_template(
    template: str,
    archive_root: Path,
    category: LogCategory,
    context: LogContext,
    session_dir: Path,
) -> str:
    values = {
        "archive_root": str(archive_root),
        "category": category,
        "session_id": context.session_id or "{session_id}",
        "task_id": context.task_id or "{task_id}",
        "agent_id": context.agent_id or "{agent_id}",
        "date": "{date}",
    }
    rendered = Path(template.format_map(_DefaultMapping(values)))
    return _display_path(rendered, session_dir, archive_root)


def _archive_key(
    category: LogCategory,
    sink_name: str,
    existing: dict[str, str],
) -> str:
    return category if category not in existing else f"{category}.{sink_name}"


class _DefaultMapping(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "_unknown"


_GLOBAL_MANAGER = LoggingManager()


def get_logging_manager() -> LoggingManager:
    """Return the process-wide logging manager."""
    return _GLOBAL_MANAGER


__all__ = [
    "LogData",
    "LoggingManager",
    "LoggingSnapshot",
    "build_disabled_logging_config",
    "build_legacy_logging_config",
    "build_session_logging_config",
    "get_logging_manager",
]
