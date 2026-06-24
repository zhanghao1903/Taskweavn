"""Read-only runtime config diagnostics gateway."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from pydantic import Field

from taskweavn.runtime_config import (
    EffectiveRuntimeConfig,
    EffectiveRuntimeConfigValue,
    RuntimeConfigBusDiagnosticsSnapshot,
    RuntimeConfigBusPublication,
    RuntimeConfigModel,
    RuntimeConfigScope,
    RuntimeConfigSnapshotRecord,
    runtime_config_bus_diagnostics_snapshot,
)
from taskweavn.runtime_config.models import RuntimeConfigChange
from taskweavn.server.runtime_config_gateway import RuntimeConfigGateway


class RuntimeConfigDiagnosticsSnapshot(RuntimeConfigModel):
    """Combined read-only runtime config diagnostics snapshot."""

    schema_version: str = "plato.runtime_config_diagnostics.v1"
    scope: RuntimeConfigScope
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    effective_config: EffectiveRuntimeConfig
    explained_values: dict[str, EffectiveRuntimeConfigValue]
    changes: tuple[RuntimeConfigChange, ...]
    snapshot_records: tuple[RuntimeConfigSnapshotRecord, ...]
    missing_snapshot_hashes: tuple[str, ...]
    config_bus: RuntimeConfigBusDiagnosticsSnapshot


class RuntimeConfigDiagnosticsGateway(Protocol):
    """Read-only combined diagnostics boundary for runtime config facts."""

    def snapshot(
        self,
        scope: RuntimeConfigScope,
        *,
        explain_keys: Iterable[str] = (),
        snapshot_hashes: Iterable[str] = (),
        config_bus_limit: int = 20,
    ) -> RuntimeConfigDiagnosticsSnapshot: ...


@dataclass(frozen=True)
class DefaultRuntimeConfigDiagnosticsGateway:
    """Default runtime config diagnostics projection over existing gateways."""

    runtime_config_gateway: RuntimeConfigGateway
    config_bus_publications: Iterable[RuntimeConfigBusPublication] = field(
        default_factory=tuple
    )

    def snapshot(
        self,
        scope: RuntimeConfigScope,
        *,
        explain_keys: Iterable[str] = (),
        snapshot_hashes: Iterable[str] = (),
        config_bus_limit: int = 20,
    ) -> RuntimeConfigDiagnosticsSnapshot:
        """Return a read-only diagnostics snapshot for one runtime config scope."""

        explained_values = {
            key: self.runtime_config_gateway.explain(key, scope)
            for key in tuple(explain_keys)
        }
        found_snapshots: list[RuntimeConfigSnapshotRecord] = []
        missing_hashes: list[str] = []
        for config_hash in tuple(snapshot_hashes):
            record = self.runtime_config_gateway.get_snapshot(config_hash)
            if record is None:
                missing_hashes.append(config_hash)
            else:
                found_snapshots.append(record)

        return RuntimeConfigDiagnosticsSnapshot(
            scope=scope,
            effective_config=self.runtime_config_gateway.effective(scope),
            explained_values=explained_values,
            changes=self.runtime_config_gateway.list_changes(scope),
            snapshot_records=tuple(found_snapshots),
            missing_snapshot_hashes=tuple(missing_hashes),
            config_bus=runtime_config_bus_diagnostics_snapshot(
                self.config_bus_publications,
                limit=config_bus_limit,
            ),
        )


__all__ = [
    "DefaultRuntimeConfigDiagnosticsGateway",
    "RuntimeConfigDiagnosticsGateway",
    "RuntimeConfigDiagnosticsSnapshot",
]
