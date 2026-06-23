"""Runtime configuration gateway for sidecar diagnostics."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from taskweavn.runtime_config import (
    EffectiveRuntimeConfig,
    EffectiveRuntimeConfigValue,
    RuntimeConfigLayer,
    RuntimeConfigRegistry,
    RuntimeConfigResolver,
    RuntimeConfigScope,
    build_default_runtime_config_registry,
    environment_runtime_config_layer,
    process_runtime_config_layer,
)


class RuntimeConfigGateway(Protocol):
    """Read-only diagnostics boundary for effective runtime config."""

    def schema(self) -> dict[str, object]: ...

    def effective(self, scope: RuntimeConfigScope) -> EffectiveRuntimeConfig: ...

    def explain(
        self,
        key: str,
        scope: RuntimeConfigScope,
    ) -> EffectiveRuntimeConfigValue: ...


@dataclass(frozen=True)
class DefaultRuntimeConfigGateway:
    """Resolve runtime config from the current process inputs and environment."""

    layers: tuple[RuntimeConfigLayer, ...] = ()
    default_scope: RuntimeConfigScope = RuntimeConfigScope(level="process")

    @classmethod
    def from_process_inputs(
        cls,
        values: Mapping[str, Any],
        *,
        workspace_id: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> DefaultRuntimeConfigGateway:
        layers = (
            environment_runtime_config_layer(os.environ if env is None else env),
            process_runtime_config_layer(values),
        )
        return cls(
            layers=layers,
            default_scope=RuntimeConfigScope(
                level="workspace" if workspace_id else "process",
                workspace_id=workspace_id,
            ),
        )

    def schema(self) -> dict[str, object]:
        return _registry().to_schema_payload()

    def effective(self, scope: RuntimeConfigScope) -> EffectiveRuntimeConfig:
        resolver = RuntimeConfigResolver(_registry())
        return resolver.resolve(
            scope=_merge_default_scope(scope, self.default_scope),
            layers=self.layers,
        )

    def explain(
        self,
        key: str,
        scope: RuntimeConfigScope,
    ) -> EffectiveRuntimeConfigValue:
        resolver = RuntimeConfigResolver(_registry())
        return resolver.explain(
            key=key,
            scope=_merge_default_scope(scope, self.default_scope),
            layers=self.layers,
        )


def _merge_default_scope(
    scope: RuntimeConfigScope,
    default_scope: RuntimeConfigScope,
) -> RuntimeConfigScope:
    if (
        scope.level != "process"
        or scope.workspace_id is not None
        or scope.session_id is not None
        or scope.task_id is not None
        or scope.agent_run_id is not None
    ):
        return scope
    return default_scope


def _registry() -> RuntimeConfigRegistry:
    return build_default_runtime_config_registry()


__all__ = [
    "DefaultRuntimeConfigGateway",
    "RuntimeConfigGateway",
]
