"""Client-side UI log sinks for the local Plato sidecar."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from taskweavn.core import WorkspaceLayout


class ClientErrorLogSink(Protocol):
    """Sink for browser-side error logs forwarded through the local sidecar."""

    def write_error(self, session_id: str, payload: dict[str, Any]) -> None:
        """Persist one frontend error log payload."""


@dataclass
class FileClientErrorLogSink:
    """Append frontend error logs to the session log directory as JSONL."""

    layout: WorkspaceLayout
    filename: str = "frontend-errors.jsonl"
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def write_error(self, session_id: str, payload: dict[str, Any]) -> None:
        log_dir = self.layout.session_logs_dir(session_id)
        log_dir.mkdir(parents=True, exist_ok=True)
        row = {
            "receivedAt": datetime.now(UTC).isoformat(),
            "sessionId": session_id,
            "payload": payload,
        }
        line = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        with self._lock, (log_dir / self.filename).open("a", encoding="utf-8") as file:
            file.write(f"{line}\n")


__all__ = [
    "ClientErrorLogSink",
    "FileClientErrorLogSink",
]
