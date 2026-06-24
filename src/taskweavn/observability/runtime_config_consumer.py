"""Runtime config ConfigBus consumer for observability settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from taskweavn.observability.manager import get_logging_manager
from taskweavn.observability.models import LOG_CATEGORIES, LogCategory
from taskweavn.runtime_config import (
    RuntimeConfigBus,
    RuntimeConfigBusConsumerResult,
    RuntimeConfigBusEvent,
)


class LoggingLevelApplier(Protocol):
    """Subset of LoggingManager used by the runtime config consumer."""

    def set_level(
        self,
        *,
        session_id: str | None,
        category: LogCategory,
        level: str | int,
        duration_seconds: float | None = None,
    ) -> None: ...


@dataclass(frozen=True)
class RuntimeConfigLoggingConsumer:
    """Apply live-safe logging config changes from ConfigBus events."""

    manager: LoggingLevelApplier
    consumer_id: str = "runtime-config-logging-consumer"
    categories: tuple[LogCategory, ...] = LOG_CATEGORIES

    @classmethod
    def from_global_manager(cls) -> RuntimeConfigLoggingConsumer:
        """Build a consumer against the process-wide logging manager."""

        return cls(manager=get_logging_manager())

    def handle_runtime_config_change(
        self,
        event: RuntimeConfigBusEvent,
    ) -> RuntimeConfigBusConsumerResult:
        """Apply supported active logging keys and skip everything else."""

        applied_keys: list[str] = []
        skipped_keys: list[str] = []
        level = event.active_values.get("logging.level")
        if level is not None:
            self._apply_level(event, level)
            applied_keys.append("logging.level")

        for key in event.accepted_values:
            if key not in applied_keys:
                skipped_keys.append(key)

        return RuntimeConfigBusConsumerResult(
            consumer_id=self.consumer_id,
            status="applied" if applied_keys else "skipped",
            applied_keys=tuple(applied_keys),
            skipped_keys=tuple(skipped_keys),
            message=_consumer_message(
                applied_keys=tuple(applied_keys),
                skipped_keys=tuple(skipped_keys),
            ),
        )

    def _apply_level(self, event: RuntimeConfigBusEvent, level: object) -> None:
        if not isinstance(level, str | int):
            raise ValueError("logging.level runtime config value must be a string or int")
        session_id = event.scope.session_id if event.scope.level == "session" else None
        for category in self.categories:
            self.manager.set_level(
                session_id=session_id,
                category=category,
                level=level,
            )


def subscribe_runtime_config_logging_consumer(
    bus: RuntimeConfigBus,
    *,
    manager: LoggingLevelApplier | None = None,
) -> RuntimeConfigLoggingConsumer:
    """Subscribe the first live-safe runtime config logging consumer."""

    consumer = RuntimeConfigLoggingConsumer(
        manager=manager if manager is not None else get_logging_manager(),
    )
    bus.subscribe(consumer.consumer_id, consumer.handle_runtime_config_change)
    return consumer


def _consumer_message(
    *,
    applied_keys: tuple[str, ...],
    skipped_keys: tuple[str, ...],
) -> str:
    if applied_keys and skipped_keys:
        return "Applied live logging config keys; skipped non-live or unsupported keys."
    if applied_keys:
        return "Applied live logging config keys."
    return "No supported active logging config keys to apply."


__all__ = [
    "LoggingLevelApplier",
    "RuntimeConfigLoggingConsumer",
    "subscribe_runtime_config_logging_consumer",
]
