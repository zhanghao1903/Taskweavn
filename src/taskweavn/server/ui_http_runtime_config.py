"""HTTP adapter for read-only runtime configuration diagnostics."""

from __future__ import annotations

from typing import cast

from pydantic import Field, ValidationError

from taskweavn.runtime_config import (
    RuntimeConfigChange,
    RuntimeConfigModel,
    RuntimeConfigRegistryError,
    RuntimeConfigResolverError,
    RuntimeConfigSnapshotRecord,
)
from taskweavn.runtime_config.models import RuntimeConfigScope, RuntimeConfigScopeLevel
from taskweavn.server.runtime_config_gateway import RuntimeConfigGateway
from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import ApiError
from taskweavn.server.ui_http_query_params import _request_query
from taskweavn.server.ui_http_responses import _error_response, _json_response, _request_id_hint


def _runtime_config_response(
    request: HttpApiRequest,
    *,
    route_name: str,
    gateway: RuntimeConfigGateway | None,
    config_hash: str = "",
) -> HttpApiResponse:
    if gateway is None:
        return _error_response(
            503,
            ApiError(
                code="internal_error",
                message="runtime config gateway is not configured",
                details={"route": route_name},
            ),
            request_id=_request_id_hint(request),
        )
    try:
        if route_name == "runtime_config_schema":
            data = gateway.schema()
        elif route_name == "runtime_config_effective":
            data = gateway.effective(_scope_from_query(request)).model_dump(
                mode="json",
                by_alias=True,
            )
        elif route_name == "runtime_config_changes":
            scope = _scope_from_query(request)
            data = RuntimeConfigChangeListResponse(
                scope=scope,
                changes=gateway.list_changes(scope),
            ).model_dump(mode="json", by_alias=True)
        elif route_name == "runtime_config_snapshot":
            if not config_hash:
                return _error_response(
                    400,
                    ApiError(
                        code="bad_request",
                        message="runtime config snapshot requires config hash",
                    ),
                    request_id=_request_id_hint(request),
                )
            snapshot = gateway.get_snapshot(config_hash)
            if snapshot is None:
                return _error_response(
                    404,
                    ApiError(
                        code="not_found",
                        message="runtime config snapshot not found",
                        details={"configHash": config_hash},
                    ),
                    request_id=_request_id_hint(request),
                )
            data = RuntimeConfigSnapshotLookupResponse(
                snapshot=snapshot,
            ).model_dump(mode="json", by_alias=True)
        else:
            key = _request_query(request).get("key")
            if not key:
                return _error_response(
                    400,
                    ApiError(
                        code="bad_request",
                        message="runtime config explain requires key query parameter",
                    ),
                    request_id=_request_id_hint(request),
                )
            data = gateway.explain(key, _scope_from_query(request)).model_dump(
                mode="json",
                by_alias=True,
            )
    except (RuntimeConfigRegistryError, RuntimeConfigResolverError, ValidationError) as exc:
        return _error_response(
            400,
            ApiError(
                code="bad_request",
                message=str(exc),
                details={"route": route_name},
            ),
            request_id=_request_id_hint(request),
        )
    return _json_response({"ok": True, "data": data, "error": None})


class RuntimeConfigChangeListResponse(RuntimeConfigModel):
    """Read-only HTTP response for scoped runtime config change history."""

    schema_version: str = "plato.runtime_config_changes.v1"
    scope: RuntimeConfigScope
    changes: tuple[RuntimeConfigChange, ...] = ()
    total_count: int = Field(default=0, ge=0)

    def model_post_init(self, __context: object) -> None:
        object.__setattr__(self, "total_count", len(self.changes))


class RuntimeConfigSnapshotLookupResponse(RuntimeConfigModel):
    """Read-only HTTP response for a durable runtime config snapshot lookup."""

    schema_version: str = "plato.runtime_config_snapshot.v1"
    snapshot: RuntimeConfigSnapshotRecord


def _scope_from_query(request: HttpApiRequest) -> RuntimeConfigScope:
    query = _request_query(request)
    explicit_level = query.get("scope") or query.get("level")
    level = (
        _scope_level(explicit_level)
        if explicit_level is not None
        else _inferred_scope_level(query)
    )
    return RuntimeConfigScope(
        level=level,
        workspace_id=query.get("workspaceId") or query.get("workspace_id"),
        session_id=query.get("sessionId") or query.get("session_id"),
        task_id=query.get("taskId") or query.get("task_id"),
        agent_run_id=query.get("agentRunId") or query.get("agent_run_id"),
    )


def _inferred_scope_level(query: dict[str, str]) -> RuntimeConfigScopeLevel:
    if query.get("agentRunId") or query.get("agent_run_id"):
        return "agent_run"
    if query.get("taskId") or query.get("task_id"):
        return "task"
    if query.get("sessionId") or query.get("session_id"):
        return "session"
    if query.get("workspaceId") or query.get("workspace_id"):
        return "workspace"
    return "process"


def _scope_level(raw: str) -> RuntimeConfigScopeLevel:
    if raw in {"global", "workspace", "session", "task", "agent_run", "process"}:
        return cast(RuntimeConfigScopeLevel, raw)
    raise RuntimeConfigResolverError(f"invalid runtime config scope: {raw!r}")


__all__ = ["_runtime_config_response"]
