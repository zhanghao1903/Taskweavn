"""Diagnostics projection for runtime config ConfigBus publications."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from pydantic import Field

from taskweavn.runtime_config.config_bus import (
    RuntimeConfigBusConsumerResult,
    RuntimeConfigBusPublication,
)
from taskweavn.runtime_config.models import RuntimeConfigModel, RuntimeConfigScope


class RuntimeConfigBusPublicationSummary(RuntimeConfigModel):
    """Compact diagnostics summary for one ConfigBus publication."""

    event_id: str = Field(min_length=1)
    change_id: str = Field(min_length=1)
    patch_id: str = Field(min_length=1)
    scope: RuntimeConfigScope
    accepted_keys: tuple[str, ...]
    active_keys: tuple[str, ...]
    pending_keys: tuple[str, ...]
    base_config_hash: str = Field(min_length=1)
    resulting_config_hash: str = Field(min_length=1)
    published_at: datetime
    consumer_results: tuple[RuntimeConfigBusConsumerResult, ...]


class RuntimeConfigBusDiagnosticsSnapshot(RuntimeConfigModel):
    """Read-only diagnostics snapshot for recent ConfigBus publications."""

    schema_version: str = "plato.runtime_config_configbus_diagnostics.v1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total_publication_count: int = Field(ge=0)
    publications: tuple[RuntimeConfigBusPublicationSummary, ...]


def runtime_config_bus_diagnostics_snapshot(
    publications: Iterable[RuntimeConfigBusPublication],
    *,
    limit: int = 20,
) -> RuntimeConfigBusDiagnosticsSnapshot:
    """Project recent ConfigBus publications into diagnostics-safe summaries."""

    if limit < 0:
        raise ValueError("limit must be >= 0")
    all_publications = tuple(publications)
    selected = all_publications[-limit:] if limit else ()
    return RuntimeConfigBusDiagnosticsSnapshot(
        total_publication_count=len(all_publications),
        publications=tuple(_publication_summary(publication) for publication in selected),
    )


def _publication_summary(
    publication: RuntimeConfigBusPublication,
) -> RuntimeConfigBusPublicationSummary:
    event = publication.event
    return RuntimeConfigBusPublicationSummary(
        event_id=event.event_id,
        change_id=event.change_id,
        patch_id=event.patch_id,
        scope=event.scope,
        accepted_keys=tuple(event.accepted_values),
        active_keys=tuple(event.active_values),
        pending_keys=tuple(event.pending_values),
        base_config_hash=event.base_config_hash,
        resulting_config_hash=event.resulting_config_hash,
        published_at=event.published_at,
        consumer_results=publication.consumer_results,
    )


__all__ = [
    "RuntimeConfigBusDiagnosticsSnapshot",
    "RuntimeConfigBusPublicationSummary",
    "runtime_config_bus_diagnostics_snapshot",
]
