"""Read/query HTTP route helpers for Plato UI transport."""

from __future__ import annotations

from taskweavn.server.runtime_input_router import RuntimeInputRouter
from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import UiQueryGateway
from taskweavn.server.ui_http_activity import _session_activity_response
from taskweavn.server.ui_http_query_params import (
    _bool_query,
    _int_query,
    _optional_bool_query,
    _request_query,
)
from taskweavn.server.ui_http_responses import _contract_response
from taskweavn.server.ui_http_routes import _Route
from taskweavn.server.ui_http_runtime_input import _runtime_input_route_response


def _query_route_response(
    request: HttpApiRequest,
    route: _Route,
    *,
    query_gateway: UiQueryGateway,
    runtime_input_router: RuntimeInputRouter | None,
) -> HttpApiResponse | None:
    route_name = route.name
    if route_name == "session_activity":
        return _session_activity_response(
            request,
            session_id=route.session_id,
            query_gateway=query_gateway,
        )
    if route_name == "runtime_input_route":
        return _runtime_input_route_response(
            request,
            session_id=route.session_id,
            workspace_id=route.workspace_id or None,
            router=runtime_input_router,
        )
    if route_name == "audit_snapshot":
        query = _request_query(request)
        return _contract_response(
            query_gateway.get_audit_snapshot(
                route.session_id,
                task_node_id=route.task_node_id or None,
                entry=query.get("entry"),
                filter_kind=query.get("filter", "all"),
                record_id=query.get("recordId"),
                include_detail=_optional_bool_query(query, "includeDetail"),
                limit=_int_query(query, "limit", default=50),
                cursor=query.get("cursor"),
            )
        )
    if route_name == "asks":
        query = _request_query(request)
        return _contract_response(
            query_gateway.list_asks(
                route.session_id,
                status=query.get("status"),
                task_node_id=query.get("taskNodeId"),
            )
        )
    if route_name == "ask_detail":
        return _contract_response(query_gateway.get_ask(route.session_id, route.ask_id))
    if route_name == "audit_records":
        query = _request_query(request)
        return _contract_response(
            query_gateway.list_audit_records(
                route.session_id,
                task_node_id=route.task_node_id or None,
                filter_kind=query.get("filter", "all"),
                kind=query.get("kind"),
                from_time=query.get("from"),
                to_time=query.get("to"),
                limit=_int_query(query, "limit", default=50),
                cursor=query.get("cursor"),
                include_hidden_reasons=_bool_query(
                    query,
                    "includeHiddenReasons",
                    default=False,
                ),
            )
        )
    if route_name == "audit_record_detail":
        query = _request_query(request)
        return _contract_response(
            query_gateway.get_audit_record_detail(
                route.session_id,
                route.record_id,
                include_evidence=_bool_query(
                    query,
                    "includeEvidence",
                    default=False,
                ),
                include_sanitized_payload=_bool_query(
                    query,
                    "includeSanitizedPayload",
                    default=False,
                ),
            )
        )
    if route_name == "audit_evidence_detail":
        query = _request_query(request)
        return _contract_response(
            query_gateway.get_evidence_detail(
                route.session_id,
                route.evidence_id,
                include_sanitized_payload=_bool_query(
                    query,
                    "includeSanitizedPayload",
                    default=False,
                ),
            )
        )
    return None


__all__ = ["_query_route_response"]
