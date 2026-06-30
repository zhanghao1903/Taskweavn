"""ToolEvent observer helpers for app-control package clients."""

from __future__ import annotations

from dataclasses import dataclass, field

from app_control_protocol import ToolEvent
from app_control_protocol.json_types import JsonValue


@dataclass
class RecordingToolObserver:
    """Small testable observer that stores package events as dictionaries."""

    events: list[dict[str, JsonValue]] = field(default_factory=list)

    def on_event(self, event: ToolEvent) -> None:
        self.events.append(event.to_dict())
