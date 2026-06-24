"""Internal runtime config change publication bus."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import Field, model_validator

from taskweavn.runtime_config.models import (
    RuntimeConfigActor,
    RuntimeConfigChange,
    RuntimeConfigEffectiveStatus,
    RuntimeConfigModel,
    RuntimeConfigScope,
)

RuntimeConfigBusEventType = Literal["runtime_config.changed"]
RuntimeConfigBusConsumerStatus = Literal["applied", "skipped", "failed"]


class RuntimeConfigBusError(RuntimeError):
    """Raised when ConfigBus subscription or publication is invalid."""


class RuntimeConfigBusEvent(RuntimeConfigModel):
    """Typed internal event for an accepted runtime config change."""

    event_id: str = Field(min_length=1)
    event_type: RuntimeConfigBusEventType = "runtime_config.changed"
    change_id: str = Field(min_length=1)
    patch_id: str = Field(min_length=1)
    scope: RuntimeConfigScope
    actor: RuntimeConfigActor
    reason: str | None = Field(default=None, min_length=1)
    accepted_values: dict[str, Any]
    active_values: dict[str, Any] = Field(default_factory=dict)
    pending_values: dict[str, Any] = Field(default_factory=dict)
    effective_status_by_key: dict[str, RuntimeConfigEffectiveStatus]
    base_config_hash: str = Field(min_length=1)
    resulting_config_hash: str = Field(min_length=1)
    change_created_at: datetime
    published_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _event_is_consistent(self) -> RuntimeConfigBusEvent:
        accepted_keys = set(self.accepted_values)
        status_keys = set(self.effective_status_by_key)
        if accepted_keys != status_keys:
            raise ValueError("accepted values and effective statuses must match")
        if set(self.active_values) | set(self.pending_values) != accepted_keys:
            raise ValueError("active and pending values must partition accepted values")
        if set(self.active_values) & set(self.pending_values):
            raise ValueError("active and pending values must not overlap")
        active_status_errors = [
            key
            for key in self.active_values
            if self.effective_status_by_key[key] != "active"
        ]
        if active_status_errors:
            raise ValueError("active values require active effective status")
        pending_status_errors = [
            key
            for key in self.pending_values
            if self.effective_status_by_key[key] == "active"
        ]
        if pending_status_errors:
            raise ValueError("pending values cannot use active effective status")
        return self


class RuntimeConfigBusConsumerResult(RuntimeConfigModel):
    """Result reported by one ConfigBus consumer."""

    consumer_id: str = Field(min_length=1)
    status: RuntimeConfigBusConsumerStatus
    applied_keys: tuple[str, ...] = ()
    skipped_keys: tuple[str, ...] = ()
    message: str | None = Field(default=None, min_length=1)
    error_type: str | None = Field(default=None, min_length=1)


class RuntimeConfigBusPublication(RuntimeConfigModel):
    """ConfigBus publication result for diagnostics and tests."""

    event: RuntimeConfigBusEvent
    consumer_results: tuple[RuntimeConfigBusConsumerResult, ...]


RuntimeConfigBusHandler = Callable[
    [RuntimeConfigBusEvent],
    RuntimeConfigBusConsumerResult | None,
]


@runtime_checkable
class RuntimeConfigBus(Protocol):
    """Internal runtime config publication boundary."""

    def subscribe(
        self,
        consumer_id: str,
        handler: RuntimeConfigBusHandler,
    ) -> None: ...

    def unsubscribe(self, consumer_id: str) -> None: ...

    def publish_change(
        self,
        change: RuntimeConfigChange,
    ) -> RuntimeConfigBusPublication | None: ...


class InMemoryRuntimeConfigBus:
    """Deterministic in-process ConfigBus for sidecar runtime wiring."""

    def __init__(self) -> None:
        self._handlers: dict[str, RuntimeConfigBusHandler] = {}
        self._publications: list[RuntimeConfigBusPublication] = []

    @property
    def publications(self) -> tuple[RuntimeConfigBusPublication, ...]:
        """Return publications captured by this in-memory bus."""

        return tuple(self._publications)

    def subscribe(
        self,
        consumer_id: str,
        handler: RuntimeConfigBusHandler,
    ) -> None:
        """Subscribe one consumer by stable ID."""

        if not consumer_id:
            raise RuntimeConfigBusError("consumer_id must not be empty")
        if consumer_id in self._handlers:
            raise RuntimeConfigBusError(
                f"runtime config consumer already subscribed: {consumer_id}"
            )
        self._handlers[consumer_id] = handler

    def unsubscribe(self, consumer_id: str) -> None:
        """Remove one consumer if it is currently subscribed."""

        self._handlers.pop(consumer_id, None)

    def publish_change(
        self,
        change: RuntimeConfigChange,
    ) -> RuntimeConfigBusPublication | None:
        """Publish an accepted config change to current subscribers."""

        if change.status != "accepted":
            return None
        event = runtime_config_bus_event_from_change(change)
        results = tuple(
            self._deliver(consumer_id, handler, event)
            for consumer_id, handler in tuple(self._handlers.items())
        )
        publication = RuntimeConfigBusPublication(
            event=event,
            consumer_results=results,
        )
        self._publications.append(publication)
        return publication

    def _deliver(
        self,
        consumer_id: str,
        handler: RuntimeConfigBusHandler,
        event: RuntimeConfigBusEvent,
    ) -> RuntimeConfigBusConsumerResult:
        try:
            result = handler(event)
        except Exception as exc:  # pragma: no cover - exact exception is captured in tests
            return RuntimeConfigBusConsumerResult(
                consumer_id=consumer_id,
                status="failed",
                skipped_keys=tuple(event.accepted_values),
                message=str(exc),
                error_type=type(exc).__name__,
            )
        if result is None:
            return RuntimeConfigBusConsumerResult(
                consumer_id=consumer_id,
                status="skipped",
                skipped_keys=tuple(event.accepted_values),
                message="Consumer returned no result.",
            )
        if result.consumer_id != consumer_id:
            return RuntimeConfigBusConsumerResult(
                consumer_id=consumer_id,
                status="failed",
                skipped_keys=tuple(event.accepted_values),
                message="Consumer result ID must match subscription consumer_id.",
                error_type="RuntimeConfigBusError",
            )
        return result


def runtime_config_bus_event_from_change(
    change: RuntimeConfigChange,
) -> RuntimeConfigBusEvent:
    """Build a ConfigBus event from an accepted runtime config change."""

    if change.status != "accepted":
        raise RuntimeConfigBusError("only accepted runtime config changes publish")
    if change.resulting_config_hash is None:
        raise RuntimeConfigBusError("accepted runtime config change requires hash")
    active_values = {
        key: value
        for key, value in change.accepted_values.items()
        if change.effective_status_by_key[key] == "active"
    }
    pending_values = {
        key: value
        for key, value in change.accepted_values.items()
        if change.effective_status_by_key[key] != "active"
    }
    return RuntimeConfigBusEvent(
        event_id=f"runtime_config_event:{uuid4().hex}",
        change_id=change.change_id,
        patch_id=change.patch_id,
        scope=change.scope,
        actor=change.actor,
        reason=change.reason,
        accepted_values=dict(change.accepted_values),
        active_values=active_values,
        pending_values=pending_values,
        effective_status_by_key=dict(change.effective_status_by_key),
        base_config_hash=change.base_config_hash,
        resulting_config_hash=change.resulting_config_hash,
        change_created_at=change.created_at,
    )


__all__ = [
    "InMemoryRuntimeConfigBus",
    "RuntimeConfigBus",
    "RuntimeConfigBusConsumerResult",
    "RuntimeConfigBusConsumerStatus",
    "RuntimeConfigBusError",
    "RuntimeConfigBusEvent",
    "RuntimeConfigBusEventType",
    "RuntimeConfigBusHandler",
    "RuntimeConfigBusPublication",
    "runtime_config_bus_event_from_change",
]
