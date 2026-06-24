"""HTTP adapter for read-only runtime configuration diagnostics."""

from __future__ import annotations

from typing import Literal, cast

from pydantic import Field, ValidationError, model_validator

from taskweavn.runtime_config import (
    RuntimeConfigActor,
    RuntimeConfigChange,
    RuntimeConfigChangeStoreError,
    RuntimeConfigModel,
    RuntimeConfigMutationService,
    RuntimeConfigPatch,
    RuntimeConfigRegistryError,
    RuntimeConfigResolverError,
    RuntimeConfigScope,
    RuntimeConfigScopeLevel,
    RuntimeConfigSnapshotRecord,
)
from taskweavn.server.runtime_config_gateway import RuntimeConfigGateway
from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import ApiError
from taskweavn.server.ui_http_query_params import _request_query
from taskweavn.server.ui_http_responses import (
    _error_response,
    _json_response,
    _request_id_hint,
)


def _runtime_config_response(
    request: HttpApiRequest,
    *,
    route_name: str,
    gateway: RuntimeConfigGateway | None,
    mutation_service: RuntimeConfigMutationService | None = None,
    config_hash: str = "",
) -> HttpApiResponse:
    if route_name == "runtime_config_patch":
        return _runtime_config_patch_response(
            request,
            gateway=gateway,
            mutation_service=mutation_service,
        )

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


def _runtime_config_patch_response(
    request: HttpApiRequest,
    *,
    gateway: RuntimeConfigGateway | None,
    mutation_service: RuntimeConfigMutationService | None,
) -> HttpApiResponse:
    if gateway is None or mutation_service is None:
        return _error_response(
            503,
            ApiError(
                code="internal_error",
                message="runtime config mutation service is not configured",
                details={
                    "route": "runtime_config_patch",
                    "hasGateway": gateway is not None,
                    "hasMutationService": mutation_service is not None,
                },
            ),
            request_id=_request_id_hint(request),
        )
    if request.body is None:
        return _error_response(
            400,
            ApiError(
                code="bad_request",
                message="runtime config patch request body must be a JSON object",
            ),
            request_id=_request_id_hint(request),
        )
    try:
        parsed = RuntimeConfigPatchHttpRequest.model_validate(request.body)
    except ValidationError as exc:
        return _error_response(
            400,
            ApiError(
                code="bad_request",
                message="request body does not match runtime config patch contract",
                details={"errors": exc.errors()},
            ),
            request_id=_request_id_hint(request),
        )

    if not parsed.dry_run and parsed.idempotency_key is None:
        return _error_response(
            400,
            ApiError(
                code="bad_request",
                message="runtime config patch requires idempotencyKey unless dryRun=true",
            ),
            request_id=_request_id_hint(request),
        )

    existing_change = None
    if parsed.idempotency_key is not None and not parsed.dry_run:
        existing_change = gateway.get_change_by_idempotency_key(
            parsed.idempotency_key,
            parsed.scope,
        )
        if existing_change is not None:
            if not _matches_existing_patch(parsed, existing_change):
                return _error_response(
                    409,
                    ApiError(
                        code="idempotency_conflict",
                        message=(
                            "runtime config idempotency key was reused for a "
                            "different patch"
                        ),
                        details={"idempotencyKey": parsed.idempotency_key},
                    ),
                    request_id=parsed.idempotency_key,
                )
            data = _patch_response_payload(
                existing_change,
                gateway=gateway,
                replayed=True,
            ).model_dump(mode="json", by_alias=True)
            return _json_response({"ok": True, "data": data, "error": None})

    patch_id = parsed.idempotency_key or _request_id_hint(request) or "dry-run"
    patch = RuntimeConfigPatch(
        patch_id=f"runtime_config_patch:{patch_id}",
        idempotency_key=None if parsed.dry_run else parsed.idempotency_key,
        scope=parsed.scope,
        actor=_runtime_config_actor(),
        reason=parsed.reason,
        values=parsed.values,
        expected_base_config_hash=parsed.expected_base_config_hash,
        dry_run=parsed.dry_run,
        allow_partial_acceptance=parsed.allow_partial_acceptance,
    )
    try:
        change = mutation_service.apply_patch(patch)
    except RuntimeConfigChangeStoreError as exc:
        return _error_response(
            503,
            ApiError(
                code="internal_error",
                message=str(exc),
                retryable=True,
                details={"route": "runtime_config_patch"},
            ),
            request_id=parsed.idempotency_key,
        )

    data = _patch_response_payload(
        change,
        gateway=gateway,
        replayed=False,
        dry_run=parsed.dry_run,
    ).model_dump(mode="json", by_alias=True)
    return _json_response({"ok": True, "data": data, "error": None})


class RuntimeConfigPatchHttpRequest(RuntimeConfigModel):
    """HTTP request payload for controlled runtime config mutation."""

    schema_version: str = "plato.runtime_config_patch_request.v1"
    idempotency_key: str | None = Field(default=None, min_length=1)
    scope: RuntimeConfigScope
    values: dict[str, object] = Field(min_length=1)
    expected_base_config_hash: str | None = Field(default=None, min_length=1)
    reason: str | None = Field(default=None, min_length=1)
    dry_run: bool = False
    allow_partial_acceptance: bool = False

    @model_validator(mode="after")
    def _http_scope_is_writable(self) -> RuntimeConfigPatchHttpRequest:
        if self.scope.level in {"process", "agent_run"}:
            raise ValueError(
                "runtime config HTTP writes do not support process or agent_run scope"
            )
        return self


class RuntimeConfigSnapshotRef(RuntimeConfigModel):
    """Stable reference to a persisted runtime config snapshot."""

    snapshot_id: str = Field(min_length=1)
    config_hash: str = Field(min_length=1)


RuntimeConfigWriteWarningCode = Literal[
    "pending_restart",
    "pending_next_agent_run",
    "pending_next_task",
    "higher_priority_source_active",
    "partial_acceptance",
]


class RuntimeConfigWriteWarning(RuntimeConfigModel):
    """User-facing warning derived from runtime config patch facts."""

    code: RuntimeConfigWriteWarningCode
    message: str = Field(min_length=1)
    config_keys: tuple[str, ...] = ()


class RuntimeConfigPatchResponse(RuntimeConfigModel):
    """HTTP response payload for controlled runtime config mutation."""

    schema_version: str = "plato.runtime_config_patch_response.v1"
    change: RuntimeConfigChange
    snapshot_ref: RuntimeConfigSnapshotRef | None = None
    replayed: bool = False
    dry_run: bool = False
    warnings: tuple[RuntimeConfigWriteWarning, ...] = ()


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


def _matches_existing_patch(
    parsed: RuntimeConfigPatchHttpRequest,
    existing: RuntimeConfigChange,
) -> bool:
    if existing.scope != parsed.scope:
        return False
    if existing.requested_values != parsed.values:
        return False
    return not (
        parsed.expected_base_config_hash is not None
        and parsed.expected_base_config_hash != existing.base_config_hash
    )


def _patch_response_payload(
    change: RuntimeConfigChange,
    *,
    gateway: RuntimeConfigGateway,
    replayed: bool,
    dry_run: bool = False,
) -> RuntimeConfigPatchResponse:
    snapshot_ref = None
    if not dry_run and change.resulting_config_hash is not None:
        snapshot = gateway.get_snapshot(change.resulting_config_hash)
        if snapshot is not None:
            snapshot_ref = RuntimeConfigSnapshotRef(
                snapshot_id=snapshot.snapshot_id,
                config_hash=snapshot.config_hash,
            )
    return RuntimeConfigPatchResponse(
        change=change,
        snapshot_ref=snapshot_ref,
        replayed=replayed,
        dry_run=dry_run,
        warnings=_write_warnings(change),
    )


def _write_warnings(
    change: RuntimeConfigChange,
) -> tuple[RuntimeConfigWriteWarning, ...]:
    warnings: list[RuntimeConfigWriteWarning] = []
    pending_keys = {
        status: tuple(
            key
            for key, key_status in change.effective_status_by_key.items()
            if key_status == status
        )
        for status in {
            "pending_restart",
            "pending_next_agent_run",
            "pending_next_task",
        }
    }
    for status, keys in sorted(pending_keys.items()):
        if keys:
            warnings.append(
                RuntimeConfigWriteWarning(
                    code=cast(RuntimeConfigWriteWarningCode, status),
                    message=f"Runtime config keys are {status}.",
                    config_keys=keys,
                )
            )
    if change.accepted_values and change.rejected_values:
        warnings.append(
            RuntimeConfigWriteWarning(
                code="partial_acceptance",
                message="Runtime config patch was partially accepted.",
                config_keys=tuple(change.rejected_values),
            )
        )
    higher_priority_keys = tuple(
        key
        for key, rejection in change.rejected_values.items()
        if rejection.code == "higher_priority_source_active"
    )
    if higher_priority_keys:
        warnings.append(
            RuntimeConfigWriteWarning(
                code="higher_priority_source_active",
                message="A higher-priority runtime config source is active.",
                config_keys=higher_priority_keys,
            )
        )
    return tuple(warnings)


def _runtime_config_actor() -> RuntimeConfigActor:
    return RuntimeConfigActor(
        actor_type="user",
        actor_id="local-sidecar",
        display_name="Local Sidecar",
    )


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
