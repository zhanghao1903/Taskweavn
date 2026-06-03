"""Debug trace helper for Main Page runtime behavior."""

from __future__ import annotations

import contextlib
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger("taskweavn.main_page.trace")
_FALSE_VALUES = {"0", "false", "no", "off", "silent"}
_TRUE_VALUES = {"1", "true", "yes", "on"}
_SUPPRESSED_EVENTS = {
    "http.events.request",
    "http.events.response",
    "ui_event.latest_cursor",
    "ui_event.subscribe.cursor_missing",
    "ui_event.subscribe.result",
}


def main_page_trace(event: str, /, **context: Any) -> None:
    """Emit lightweight behavior traces while Main Page integration settles.

    Set ``PLATO_MAIN_PAGE_TRACE=0`` to disable logger output.
    Set ``PLATO_MAIN_PAGE_TRACE_PRINT=1`` to also mirror traces to stdout.
    Set ``PLATO_MAIN_PAGE_TRACE_FILE=/path/to/file.jsonl`` to append JSONL.
    """

    if event in _SUPPRESSED_EVENTS:
        return

    trace_file = os.environ.get("PLATO_MAIN_PAGE_TRACE_FILE")
    if not _trace_enabled() and not trace_file:
        return

    entry = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "event": event,
        **context,
    }
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True, default=str)

    if _trace_enabled():
        _LOGGER.info("[plato:main-page-trace] %s", line)

    if _raw_stdout_enabled():
        print(f"[plato:main-page-trace] {line}", flush=True)

    if trace_file:
        _append_trace_file(Path(trace_file), line)


def _trace_enabled() -> bool:
    value = os.environ.get("PLATO_MAIN_PAGE_TRACE", "1").strip().lower()
    return value not in _FALSE_VALUES


def _raw_stdout_enabled() -> bool:
    value = os.environ.get("PLATO_MAIN_PAGE_TRACE_PRINT", "0").strip().lower()
    return value in _TRUE_VALUES


def _append_trace_file(path: Path, line: str) -> None:
    with contextlib.suppress(Exception):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")


__all__ = ["main_page_trace"]
