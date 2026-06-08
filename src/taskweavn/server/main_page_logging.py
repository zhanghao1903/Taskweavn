"""Session logging setup for the Plato Main Page sidecar."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from taskweavn.core import Session
from taskweavn.observability import (
    LogArchiveManifest,
    LogRule,
    build_disabled_logging_config,
    build_session_logging_config,
    get_logging_manager,
)
from taskweavn.observability.models import LOG_CATEGORIES


def configure_sidecar_logging(
    *,
    workspace_root: Path,
    enable_session_logging: bool,
    logging_level: str,
    logging_profile: str | None,
) -> Callable[[Session], None]:
    """Enable debug-phase session archives under each workspace session dir."""

    manager = get_logging_manager()
    if not enable_session_logging:
        manager.apply_config(build_disabled_logging_config(workspace_root / ".logs"))
        return lambda session: None

    base = build_session_logging_config(workspace_root, level=logging_level)
    sinks = dict(base.sinks)
    session_sink = sinks["session_file"]
    sinks["session_file"] = session_sink.model_copy(
        update={
            "path_template": (
                "{archive_root}/.taskweavn/sessions/{session_id}/logs/"
                "{category}.jsonl"
            )
        }
    )
    global_config_sink = sinks["global_config_file"]
    sinks["global_config_file"] = global_config_sink.model_copy(
        update={
            "path_template": (
                "{archive_root}/.code-agent/logs/global/{category}.jsonl"
            )
        }
    )
    rules = dict(base.rules)
    rules["config"] = LogRule(
        category="config",
        level="INFO",
        sinks=("global_config_file",),
        payload_mode="summary",
    )
    manager.apply_config(base.model_copy(update={"sinks": sinks, "rules": rules}))

    def initialize(session: Session) -> None:
        if logging_profile is not None:
            manager.apply_profile(session.id, logging_profile)
        write_sidecar_session_log_manifest(session)

    return initialize


def write_sidecar_session_log_manifest(session: Session) -> LogArchiveManifest:
    """Write the manifest where Audit Page already looks for session logs."""

    manager = get_logging_manager()
    log_dir = session.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = log_dir / "manifest.json"
    existing = None
    if manifest_path.exists():
        with contextlib.suppress(Exception):
            existing = LogArchiveManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
    manifest = LogArchiveManifest(
        session_id=session.id,
        created_at=(
            existing.created_at
            if existing is not None
            else datetime.now(tz=UTC)
        ),
        closed_at=None if existing is None else existing.closed_at,
        config_hash=manager.config_hash(),
        archive_root=str(log_dir),
        files={category: f"{category}.jsonl" for category in LOG_CATEGORIES},
        templates={},
        rotation={
            "enabled": True,
            "max_bytes": 10 * 1024 * 1024,
            "backup_count": 5,
        },
    )
    manifest_path.write_text(
        manifest.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    return manifest


__all__ = [
    "configure_sidecar_logging",
    "write_sidecar_session_log_manifest",
]
