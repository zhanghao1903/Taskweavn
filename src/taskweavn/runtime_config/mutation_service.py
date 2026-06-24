"""Runtime configuration mutation service."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from taskweavn.runtime_config.config_bus import RuntimeConfigBus
from taskweavn.runtime_config.defaults import build_default_runtime_config_registry
from taskweavn.runtime_config.models import (
    EffectiveRuntimeConfig,
    RuntimeConfigChange,
    RuntimeConfigLayer,
    RuntimeConfigPatch,
    RuntimeConfigRejection,
    RuntimeConfigScope,
    RuntimeConfigSnapshotRecord,
    RuntimeConfigSource,
)
from taskweavn.runtime_config.registry import RuntimeConfigRegistry, RuntimeConfigRegistryError
from taskweavn.runtime_config.resolver import (
    RuntimeConfigResolver,
    RuntimeConfigResolverError,
)
from taskweavn.runtime_config.sqlite_store import RuntimeConfigChangeStore

_RUNTIME_PATCH_PRIORITY = 80
_DURABLE_PATCH_SCOPE_LEVELS = {"global", "workspace", "session", "task"}
_REDACTED_VALUE = "<redacted>"


@runtime_checkable
class RuntimeConfigMutationService(Protocol):
    """Validate and persist runtime config patch requests."""

    def validate_patch(self, patch: RuntimeConfigPatch) -> RuntimeConfigChange: ...

    def apply_patch(self, patch: RuntimeConfigPatch) -> RuntimeConfigChange: ...


@dataclass(frozen=True)
class RuntimeConfigMutationServiceConfig:
    """Dependencies for the runtime config mutation service."""

    store: RuntimeConfigChangeStore
    config_bus: RuntimeConfigBus | None = None
    registry: RuntimeConfigRegistry = field(
        default_factory=build_default_runtime_config_registry
    )
    base_layers: tuple[RuntimeConfigLayer, ...] = ()


class DefaultRuntimeConfigMutationService:
    """Default runtime config mutation service for backend/control-plane tests."""

    def __init__(self, config: RuntimeConfigMutationServiceConfig) -> None:
        self._store = config.store
        self._registry = config.registry
        self._resolver = RuntimeConfigResolver(config.registry)
        self._base_layers = config.base_layers
        self._config_bus = config.config_bus

    def validate_patch(self, patch: RuntimeConfigPatch) -> RuntimeConfigChange:
        base_config = self._resolve_base(patch.scope)
        requested_values = dict(patch.values)
        redacted_keys: list[str] = []
        accepted_values: dict[str, Any] = {}
        rejected_values: dict[str, RuntimeConfigRejection] = {}

        if (
            patch.expected_base_config_hash is not None
            and patch.expected_base_config_hash != base_config.config_hash
        ):
            rejected_values = {
                key: RuntimeConfigRejection(
                    code="stale_base_config",
                    message="Patch base config hash does not match current effective config.",
                    details={
                        "expectedBaseConfigHash": patch.expected_base_config_hash,
                        "currentBaseConfigHash": base_config.config_hash,
                    },
                )
                for key in requested_values
            }
            return self._build_rejected_change(
                patch=patch,
                requested_values=requested_values,
                rejected_values=rejected_values,
                base_config=base_config,
                redacted_keys=tuple(redacted_keys),
            )

        for key, raw_value in patch.values.items():
            try:
                config_key = self._registry.get(key)
            except RuntimeConfigRegistryError:
                rejected_values[key] = RuntimeConfigRejection(
                    code="unknown_key",
                    message=f"Unknown runtime config key: {key}",
                    details={"key": key},
                )
                continue

            if patch.scope.level not in _DURABLE_PATCH_SCOPE_LEVELS:
                rejected_values[key] = RuntimeConfigRejection(
                    code="unsupported_scope",
                    message=(
                        f"Runtime config patches for scope {patch.scope.level!r} "
                        "are not durable in C5."
                    ),
                    details={"scopeLevel": patch.scope.level},
                )
                continue

            if patch.scope.level not in config_key.scope_levels:
                rejected_values[key] = RuntimeConfigRejection(
                    code="unsupported_scope",
                    message=(
                        f"Runtime config key {key!r} does not support scope "
                        f"{patch.scope.level!r}."
                    ),
                    details={
                        "scopeLevel": patch.scope.level,
                        "supportedScopeLevels": list(config_key.scope_levels),
                    },
                )
                continue

            if config_key.secret:
                requested_values[key] = _REDACTED_VALUE
                redacted_keys.append(key)
                rejected_values[key] = RuntimeConfigRejection(
                    code="secret_not_patchable",
                    message="Secrets are owned by the Settings secret boundary.",
                    details={"redacted": True},
                )
                continue

            try:
                accepted_values[key] = self._normalize_patch_value(
                    scope=patch.scope,
                    key=key,
                    value=raw_value,
                    patch_id=patch.patch_id,
                )
            except RuntimeConfigResolverError as exc:
                rejected_values[key] = RuntimeConfigRejection(
                    code="invalid_value",
                    message=str(exc),
                    details={"key": key},
                )

        if not accepted_values:
            return self._build_rejected_change(
                patch=patch,
                requested_values=requested_values,
                rejected_values=rejected_values,
                base_config=base_config,
                redacted_keys=tuple(redacted_keys),
            )

        if not rejected_values and _patch_is_no_op(base_config, accepted_values):
            return RuntimeConfigChange(
                change_id=_new_change_id(),
                patch_id=patch.patch_id,
                idempotency_key=patch.idempotency_key,
                scope=patch.scope,
                actor=patch.actor,
                reason=patch.reason,
                status="no_op",
                requested_values=requested_values,
                redacted_keys=tuple(redacted_keys),
                base_config_hash=base_config.config_hash,
                resulting_config_hash=base_config.config_hash,
                created_at=patch.requested_at,
            )

        candidate_config = self._resolve_candidate(
            patch.scope,
            patch.patch_id,
            accepted_values,
        )
        return RuntimeConfigChange(
            change_id=_new_change_id(),
            patch_id=patch.patch_id,
            idempotency_key=patch.idempotency_key,
            scope=patch.scope,
            actor=patch.actor,
            reason=patch.reason,
            status="accepted",
            requested_values=requested_values,
            accepted_values=accepted_values,
            rejected_values=rejected_values,
            redacted_keys=tuple(redacted_keys),
            base_config_hash=base_config.config_hash,
            resulting_config_hash=candidate_config.config_hash,
            effective_status_by_key={
                key: candidate_config.values[key].effective_status
                for key in accepted_values
            },
            created_at=patch.requested_at,
        )

    def apply_patch(self, patch: RuntimeConfigPatch) -> RuntimeConfigChange:
        if patch.idempotency_key is not None:
            existing = self._store.get_change_by_idempotency_key(
                patch.idempotency_key,
                patch.scope,
            )
            if existing is not None:
                return existing

        change = self.validate_patch(patch)
        if patch.dry_run:
            return change

        self._store.append_change(change)
        snapshot = self._snapshot_for_change(change)
        if snapshot is not None:
            self._store.save_snapshot(snapshot)
        if change.status == "accepted" and self._config_bus is not None:
            self._config_bus.publish_change(change)
        return change

    def _build_rejected_change(
        self,
        *,
        patch: RuntimeConfigPatch,
        requested_values: Mapping[str, Any],
        rejected_values: Mapping[str, RuntimeConfigRejection],
        base_config: EffectiveRuntimeConfig,
        redacted_keys: tuple[str, ...],
    ) -> RuntimeConfigChange:
        return RuntimeConfigChange(
            change_id=_new_change_id(),
            patch_id=patch.patch_id,
            idempotency_key=patch.idempotency_key,
            scope=patch.scope,
            actor=patch.actor,
            reason=patch.reason,
            status="rejected",
            requested_values=dict(requested_values),
            rejected_values=dict(rejected_values),
            redacted_keys=redacted_keys,
            base_config_hash=base_config.config_hash,
            created_at=patch.requested_at,
        )

    def _resolve_base(self, scope: RuntimeConfigScope) -> EffectiveRuntimeConfig:
        return self._resolver.resolve(scope=scope, layers=self._base_layers)

    def _resolve_candidate(
        self,
        scope: RuntimeConfigScope,
        patch_id: str,
        values: Mapping[str, Any],
    ) -> EffectiveRuntimeConfig:
        patch_layer = _runtime_patch_layer(scope, patch_id, values)
        return self._resolver.resolve(
            scope=scope,
            layers=(*self._base_layers, patch_layer),
        )

    def _normalize_patch_value(
        self,
        *,
        scope: RuntimeConfigScope,
        key: str,
        value: Any,
        patch_id: str,
    ) -> Any:
        config = self._resolver.resolve(
            scope=scope,
            layers=(_runtime_patch_layer(scope, patch_id, {key: value}),),
        )
        return config.values[key].value

    def _snapshot_for_change(
        self,
        change: RuntimeConfigChange,
    ) -> RuntimeConfigSnapshotRecord | None:
        if change.status == "rejected":
            return None
        if change.status == "no_op":
            effective_config = self._resolve_base(change.scope)
        else:
            effective_config = self._resolve_candidate(
                change.scope,
                change.patch_id,
                change.accepted_values,
            )
        return RuntimeConfigSnapshotRecord(
            snapshot_id=f"runtime_config_snapshot:{change.change_id}",
            config_hash=effective_config.config_hash,
            scope=change.scope,
            effective_config=effective_config,
            created_by_change_id=change.change_id,
            created_at=datetime.now(UTC),
        )


def _runtime_patch_layer(
    scope: RuntimeConfigScope,
    patch_id: str,
    values: Mapping[str, Any],
) -> RuntimeConfigLayer:
    return RuntimeConfigLayer(
        source=RuntimeConfigSource(
            source_id=f"runtime_patch:{patch_id}",
            kind="runtime_patch",
            scope=scope,
            priority=_RUNTIME_PATCH_PRIORITY,
        ),
        values=dict(values),
    )


def _patch_is_no_op(
    base_config: EffectiveRuntimeConfig,
    accepted_values: Mapping[str, Any],
) -> bool:
    return all(
        _json_equivalent(base_config.values[key].value, value)
        for key, value in accepted_values.items()
    )


def _json_equivalent(left: object, right: object) -> bool:
    return json.dumps(left, sort_keys=True, default=list) == json.dumps(
        right,
        sort_keys=True,
        default=list,
    )


def _new_change_id() -> str:
    return f"runtime_config_change:{uuid4().hex}"


__all__ = [
    "DefaultRuntimeConfigMutationService",
    "RuntimeConfigMutationService",
    "RuntimeConfigMutationServiceConfig",
]
