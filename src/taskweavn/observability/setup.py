"""Configure TaskWeavn logging.

Four named loggers route to four files:

    taskweavn.tool        -> tool.log         (Runtime dispatch + result + duration)
    taskweavn.action      -> action.log       (every Action that lands on EventStream)
    taskweavn.observation -> observation.log  (every Observation that lands on EventStream)
    taskweavn.llm         -> llm.log          (LLM request + response)

The public functions in this module are the compatibility surface from the
early channel logger. Internally they now install a bridge into the structured
``LoggingManager`` so old call sites and the new object-aware logger share the
same rules/sinks.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from taskweavn.observability.bridge import StructuredLogHandler
from taskweavn.observability.manager import (
    build_legacy_logging_config,
    build_session_logging_config,
    get_logging_manager,
)
from taskweavn.observability.models import (
    LogArchiveManifest,
    LogCategory,
    LoggingConfig,
)

LOGGER_PREFIX = "taskweavn"
CHANNELS: tuple[str, ...] = ("tool", "action", "observation", "llm")


class JSONLineFormatter(logging.Formatter):
    """One-line JSON formatter; payload comes from ``extra={"data": ...}``."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "msg": record.getMessage(),
        }
        data = getattr(record, "data", None)
        if data is not None:
            payload["data"] = data
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def get_channel_logger(channel: str) -> logging.Logger:
    """Return the logger for a known channel."""
    if channel not in CHANNELS:
        raise ValueError(
            f"unknown logging channel: {channel!r}; expected one of {CHANNELS}"
        )
    return logging.getLogger(f"{LOGGER_PREFIX}.{channel}")


def configure_logging(
    log_dir: Path | str,
    *,
    level: str | int = logging.INFO,
) -> dict[str, Path]:
    """Wire each channel logger to ``<log_dir>/<channel>.log``.

    Idempotent: any FileHandler attached by a previous call is removed before
    the new one is added. Returns the map ``{channel: path}``.
    """
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    get_logging_manager().apply_config(build_legacy_logging_config(directory, level=level))

    paths: dict[str, Path] = {}

    for channel in CHANNELS:
        logger = get_channel_logger(channel)
        # Drop FileHandlers from prior configure_logging calls to keep tests clean.
        for handler in list(logger.handlers):
            if isinstance(handler, logging.FileHandler):
                logger.removeHandler(handler)
                handler.close()
        path = directory / f"{channel}.log"
        handler = StructuredLogHandler(path, category=cast(LogCategory, channel))
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
        paths[channel] = path

    return paths


def load_logging_config(path: Path | str) -> LoggingConfig:
    """Load a complete structured logging config from JSON.

    YAML is intentionally not parsed in the first implementation because the
    project does not depend on PyYAML. The error is explicit so users know to
    provide JSON until a configuration subsystem owns YAML parsing.
    """
    config_path = Path(path)
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        raise ValueError("YAML logging config is not supported yet; use JSON")
    return LoggingConfig.model_validate_json(config_path.read_text(encoding="utf-8"))


def configure_session_logging(
    log_dir: Path | str,
    *,
    session_id: str,
    level: str | int = logging.INFO,
    profile: str | None = None,
    config_path: Path | str | None = None,
) -> LogArchiveManifest:
    """Configure structured logging with a session archive manifest.

    This is the preferred CLI/runtime entry point. It creates a session-scoped
    archive layout under ``<log_dir>/sessions/<session_id>/`` and writes a
    ``manifest.json`` that tells users and tools where category logs live.
    """
    config = (
        load_logging_config(config_path)
        if config_path is not None
        else build_session_logging_config(log_dir, level=level)
    )
    manager = get_logging_manager()
    manager.apply_config(config)
    if profile is not None:
        manager.apply_profile(session_id, profile)
    return manager.write_session_manifest(
        session_id,
        active_config_path=config_path,
    )


# Attach NullHandlers at import so the loggers never warn about missing handlers.
for _channel in CHANNELS:
    _bootstrap = logging.getLogger(f"{LOGGER_PREFIX}.{_channel}")
    if not _bootstrap.handlers:
        _bootstrap.addHandler(logging.NullHandler())
