"""SSE response helpers for Plato UI transport."""

from __future__ import annotations

from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_events import UiEventSource, sse_stream
from taskweavn.server.ui_http_query_params import _request_query
from taskweavn.server.ui_http_routes import _Route

_SSE_HEADERS = {
    "cache-control": "no-cache",
    "connection": "keep-alive",
    "content-type": "text/event-stream",
}


def _sse_response(
    event_source: UiEventSource,
    request: HttpApiRequest,
    route: _Route,
) -> HttpApiResponse:
    cursor = _request_query(request).get("cursor")
    events = tuple(event_source.subscribe(
        route.session_id,
        cursor=cursor,
    ))
    body = sse_stream(events)
    return HttpApiResponse(
        status_code=200,
        headers=dict(_SSE_HEADERS),
        body=body,
    )
