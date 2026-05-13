"""Structured logging sinks."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Protocol

from taskweavn.observability.formatting import event_to_json, event_to_pretty
from taskweavn.observability.models import LogEvent, LogSinkConfig


class LogSink(Protocol):
    """Output target for structured log events."""

    name: str

    def emit(self, event: LogEvent) -> None: ...
    def close(self) -> None: ...


class FileSink:
    """File sink with path-template rendering and single-process line safety."""

    def __init__(self, config: LogSinkConfig, *, archive_root: Path) -> None:
        if config.type != "file":
            raise ValueError("FileSink requires a file sink config")
        assert config.path_template is not None
        self.name = config.name
        self._config = config
        self._archive_root = archive_root
        self._lock = threading.Lock()

    def emit(self, event: LogEvent) -> None:
        path = self._render_path(event)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._rotate_if_needed(path)
            with path.open("a", encoding="utf-8") as handle:
                if self._config.format == "pretty":
                    handle.write(event_to_pretty(event))
                else:
                    handle.write(event_to_json(event))
                handle.write("\n")

    def close(self) -> None:
        """No-op: this sink opens files per write."""

    def _render_path(self, event: LogEvent) -> Path:
        path_template = self._config.path_template
        assert path_template is not None
        context = event.context
        values = {
            "archive_root": str(self._archive_root),
            "category": event.category,
            "session_id": context.session_id or "_unknown",
            "task_id": context.task_id or "_unknown",
            "agent_id": context.agent_id or "_unknown",
            "date": event.ts.date().isoformat(),
        }
        return Path(path_template.format_map(_DefaultMapping(values)))

    def _rotate_if_needed(self, path: Path) -> None:
        rotation = self._config.rotation
        if rotation is None or rotation.max_bytes is None or not path.exists():
            return
        if path.stat().st_size < rotation.max_bytes:
            return
        for index in range(rotation.backup_count - 1, 0, -1):
            src = path.with_name(f"{path.name}.{index}")
            dst = path.with_name(f"{path.name}.{index + 1}")
            if src.exists():
                src.replace(dst)
        if rotation.backup_count > 0:
            path.replace(path.with_name(f"{path.name}.1"))
        else:
            path.unlink()


class ConsoleSink:
    """Human-readable console sink."""

    def __init__(self, config: LogSinkConfig) -> None:
        if config.type != "console":
            raise ValueError("ConsoleSink requires a console sink config")
        self.name = config.name
        self._config = config
        self._lock = threading.Lock()

    def emit(self, event: LogEvent) -> None:
        with self._lock:
            if self._config.format == "jsonl":
                print(event_to_json(event), file=sys.stderr)
            else:
                print(event_to_pretty(event), file=sys.stderr)

    def close(self) -> None:
        """No-op."""


class NullSink:
    """Sink that discards all events."""

    def __init__(self, config: LogSinkConfig) -> None:
        if config.type != "null":
            raise ValueError("NullSink requires a null sink config")
        self.name = config.name

    def emit(self, event: LogEvent) -> None:
        """Discard the event."""

    def close(self) -> None:
        """No-op."""


def build_sink(config: LogSinkConfig, *, archive_root: Path) -> LogSink:
    """Build a concrete sink from config."""
    if config.type == "file":
        return FileSink(config, archive_root=archive_root)
    if config.type == "console":
        return ConsoleSink(config)
    return NullSink(config)


class _DefaultMapping(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "_unknown"


__all__ = ["ConsoleSink", "FileSink", "LogSink", "NullSink", "build_sink"]
