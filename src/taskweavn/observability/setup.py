"""Configure file-per-channel JSONL logging.

Four named loggers route to four files:

    taskweavn.tool        -> tool.log         (Runtime dispatch + result + duration)
    taskweavn.action      -> action.log       (every Action that lands on EventStream)
    taskweavn.observation -> observation.log  (every Observation that lands on EventStream)
    taskweavn.llm         -> llm.log          (LLM request + response)

Each line is a single JSON object: ``{"ts", "msg", "data"}``. Loggers default
to :class:`logging.NullHandler` so production stays silent until
:func:`configure_logging` runs (typically from the CLI).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

    formatter = JSONLineFormatter()
    paths: dict[str, Path] = {}

    for channel in CHANNELS:
        logger = get_channel_logger(channel)
        # Drop FileHandlers from prior configure_logging calls to keep tests clean.
        for handler in list(logger.handlers):
            if isinstance(handler, logging.FileHandler):
                logger.removeHandler(handler)
                handler.close()
        path = directory / f"{channel}.log"
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
        paths[channel] = path

    return paths


# Attach NullHandlers at import so the loggers never warn about missing handlers.
for _channel in CHANNELS:
    _bootstrap = logging.getLogger(f"{LOGGER_PREFIX}.{_channel}")
    if not _bootstrap.handlers:
        _bootstrap.addHandler(logging.NullHandler())
