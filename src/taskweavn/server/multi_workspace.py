"""Multi-workspace routing for the local Plato sidecar."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

from taskweavn.core import Session, SessionManager, WorkspaceLayout
from taskweavn.server.sidecar import SidecarTransport
from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import ApiError
from taskweavn.server.ui_http import SidecarAuth
from taskweavn.server.ui_http_query_params import _request_query
from taskweavn.server.ui_http_responses import (
    _error_response,
    _json_response,
    _normalize_headers,
    _request_id_hint,
)
from taskweavn.server.ui_http_routes import _match_route


@dataclass(frozen=True)
class WorkspaceRegistryEntry:
    """Internal sidecar registration for one local workspace."""

    workspace_id: str
    root_path: Path
    label: str
    is_current: bool = False
    last_opened_at: str | None = None

    def __post_init__(self) -> None:
        if not self.workspace_id.strip():
            raise ValueError("workspace_id must not be empty")
        if "/" in self.workspace_id or "\\" in self.workspace_id:
            raise ValueError("workspace_id must not contain path separators")


class WorkspaceRuntime(Protocol):
    """Runtime shape required by the multi-workspace router."""

    transport: SidecarTransport

    def close(self) -> None: ...


class WorkspaceRuntimeRegistry:
    """Lazy registry from renderer-safe workspace IDs to runtime instances."""

    def __init__(
        self,
        *,
        entries: tuple[WorkspaceRegistryEntry, ...],
        current_workspace_id: str,
        runtime_factory: Callable[[WorkspaceRegistryEntry], WorkspaceRuntime],
    ) -> None:
        if not entries:
            raise ValueError("workspace registry must contain at least one workspace")
        self._entries = {entry.workspace_id: entry for entry in entries}
        if len(self._entries) != len(entries):
            raise ValueError("workspace registry contains duplicate workspace IDs")
        if current_workspace_id not in self._entries:
            raise ValueError("current workspace ID is not registered")
        self.current_workspace_id = current_workspace_id
        self._runtime_factory = runtime_factory
        self._runtimes: dict[str, WorkspaceRuntime] = {}

    def get_runtime(self, workspace_id: str) -> WorkspaceRuntime:
        entry = self._entries.get(workspace_id)
        if entry is None:
            raise WorkspaceUnavailableError(workspace_id)
        if not entry.root_path.exists():
            raise WorkspaceUnavailableError(workspace_id)
        runtime = self._runtimes.get(workspace_id)
        if runtime is None:
            runtime = self._runtime_factory(entry)
            self._runtimes[workspace_id] = runtime
        return runtime

    def catalog(self) -> dict[str, object]:
        workspaces: list[dict[str, object]] = []
        for entry in self._entries.values():
            workspaces.append(self._catalog_entry(entry))
        return {
            "currentWorkspaceId": self.current_workspace_id,
            "workspaces": workspaces,
        }

    def close_all(self) -> None:
        runtimes = tuple(self._runtimes.values())
        self._runtimes.clear()
        for runtime in runtimes:
            runtime.close()

    def _catalog_entry(self, entry: WorkspaceRegistryEntry) -> dict[str, object]:
        if not entry.root_path.exists():
            return {
                "workspaceId": entry.workspace_id,
                "label": entry.label,
                "status": "unavailable",
                "isCurrent": entry.workspace_id == self.current_workspace_id,
                "sessionCount": 0,
                "recentSessions": [],
                "updatedAt": entry.last_opened_at,
            }

        layout = WorkspaceLayout(entry.root_path)
        manager = SessionManager(layout)
        try:
            sessions = manager.list()
        finally:
            manager.close()

        return {
            "workspaceId": entry.workspace_id,
            "label": entry.label,
            "status": "available",
            "isCurrent": entry.workspace_id == self.current_workspace_id,
            "sessionCount": len(sessions),
            "recentSessions": [
                _session_summary(session, entry) for session in sessions[:20]
            ],
            "updatedAt": (
                sessions[0].last_active_at.isoformat()
                if sessions
                else entry.last_opened_at
            ),
        }


class WorkspaceUnavailableError(RuntimeError):
    """Raised when a workspace ID cannot be routed safely."""

    def __init__(self, workspace_id: str) -> None:
        super().__init__(f"workspace is unavailable: {workspace_id}")
        self.workspace_id = workspace_id


class MultiWorkspacePlatoUiHttpTransport:
    """Top-level transport that routes workspace-scoped requests."""

    def __init__(
        self,
        *,
        registry: WorkspaceRuntimeRegistry,
        auth: SidecarAuth | None = None,
    ) -> None:
        self._registry = registry
        self._auth = auth

    def handle(self, request: HttpApiRequest) -> HttpApiResponse:
        route = _match_route(request.path)
        if route is not None and route.name == "workspaces":
            auth_response = self._authorize(request, allow_query_token=False)
            if auth_response is not None:
                return auth_response
            if request.method.upper() != "GET":
                return _error_response(
                    405,
                    ApiError(
                        code="bad_request",
                        message="workspaces requires GET",
                        details={"allowed_method": "GET"},
                    ),
                    request_id=_request_id_hint(request),
                    headers={"allow": "GET"},
                )
            return _json_response(
                {"ok": True, "data": self._registry.catalog(), "error": None}
            )

        if route is not None and route.workspace_id:
            auth_response = self._authorize(
                request,
                allow_query_token=route.name == "events",
            )
            if auth_response is not None:
                return auth_response
            try:
                runtime = self._registry.get_runtime(route.workspace_id)
            except WorkspaceUnavailableError as exc:
                return _workspace_unavailable_response(request, exc.workspace_id)
            workspace_context_response = _validate_workspace_context(
                request,
                route_name=route.name,
                workspace_id=route.workspace_id,
            )
            if workspace_context_response is not None:
                return workspace_context_response
            return runtime.transport.handle(
                _active_workspace_request(
                    request,
                    route_name=route.name,
                    workspace_id=route.workspace_id,
                )
            )

        current_runtime = self._registry.get_runtime(self._registry.current_workspace_id)
        return current_runtime.transport.handle(request)

    def _authorize(
        self,
        request: HttpApiRequest,
        *,
        allow_query_token: bool,
    ) -> HttpApiResponse | None:
        if self._auth is None:
            return None
        if _authorized(self._auth, request, allow_query_token=allow_query_token):
            return None
        return _error_response(
            401,
            ApiError(code="permission_denied", message="invalid sidecar token"),
            request_id=_request_id_hint(request),
        )


def _active_workspace_request(
    request: HttpApiRequest,
    *,
    route_name: str,
    workspace_id: str,
) -> HttpApiRequest:
    body = request.body
    if route_name == "runtime_input_route" and isinstance(body, dict):
        body = {**body, "workspaceId": workspace_id}
    return request.model_copy(
        update={"path": _active_workspace_path(request.path), "body": body}
    )


def _validate_workspace_context(
    request: HttpApiRequest,
    *,
    route_name: str,
    workspace_id: str,
) -> HttpApiResponse | None:
    if route_name != "runtime_input_route" or not isinstance(request.body, dict):
        return None
    body_workspace_id = request.body.get("workspaceId", request.body.get("workspace_id"))
    if body_workspace_id is None or body_workspace_id == workspace_id:
        return None
    return _error_response(
        400,
        ApiError(
            code="bad_request",
            message="body workspaceId must match path workspaceId",
            details={
                "body_workspace_id": body_workspace_id,
                "path_workspace_id": workspace_id,
            },
        ),
        request_id=_request_id_hint(request),
    )


def _active_workspace_path(path: str) -> str:
    split = urlsplit(path)
    parts = tuple(part for part in split.path.strip("/").split("/") if part)
    if len(parts) < 5 or parts[:3] != ("api", "v1", "workspaces"):
        return path
    rewritten_parts = ("api", "v1", *parts[4:])
    rewritten_path = "/" + "/".join(quote(part, safe="") for part in rewritten_parts)
    if split.query:
        return f"{rewritten_path}?{split.query}"
    return rewritten_path


def _authorized(
    auth: SidecarAuth,
    request: HttpApiRequest,
    *,
    allow_query_token: bool,
) -> bool:
    headers = _normalize_headers(request.headers)
    if headers.get("authorization") == f"Bearer {auth.token}":
        return True
    query_token = _request_query(request).get(auth.query_token_name)
    return allow_query_token and query_token == auth.token


def _workspace_unavailable_response(
    request: HttpApiRequest,
    workspace_id: str,
) -> HttpApiResponse:
    return _error_response(
        404,
        ApiError(
            code="not_found",
            message="workspace is unavailable",
            retryable=True,
            details={
                "product_error_category": "workspace_unavailable",
                "recovery_actions": ["open_workspace"],
                "workspaceId": workspace_id,
            },
        ),
        request_id=_request_id_hint(request),
    )


def _session_summary(
    session: Session,
    entry: WorkspaceRegistryEntry,
) -> dict[str, Any]:
    return {
        "id": session.id,
        "workspaceId": entry.workspace_id,
        "workspaceLabel": entry.label,
        "name": session.name,
        "createdAt": session.created_at.isoformat(),
        "updatedAt": session.last_active_at.isoformat(),
        "status": session.status,
    }


__all__ = [
    "MultiWorkspacePlatoUiHttpTransport",
    "WorkspaceRegistryEntry",
    "WorkspaceRuntime",
    "WorkspaceRuntimeRegistry",
    "WorkspaceUnavailableError",
]
