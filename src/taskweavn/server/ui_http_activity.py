"""HTTP helpers for Session Conversation / Activity queries."""

from __future__ import annotations

from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract.gateway_protocols import UiQueryGateway
from taskweavn.server.ui_http_query_params import _int_query, _request_query
from taskweavn.server.ui_http_responses import _contract_response


def _session_activity_response(
    request: HttpApiRequest,
    *,
    session_id: str,
    query_gateway: UiQueryGateway,
) -> HttpApiResponse:
    query = _request_query(request)
    return _contract_response(
        query_gateway.list_session_activity(
            session_id,
            limit=_int_query(query, "limit", default=50),
            cursor=query.get("cursor"),
        )
    )


__all__ = ["_session_activity_response"]
