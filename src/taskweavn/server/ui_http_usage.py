"""HTTP helpers for Product token usage analytics."""

from __future__ import annotations

from typing import Any, Protocol, cast

from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import ApiError, QueryResponse
from taskweavn.server.ui_http_query_params import _request_query
from taskweavn.server.ui_http_responses import (
    _contract_response,
    _error_response,
    _request_id_hint,
)
from taskweavn.usage import (
    SqliteTokenUsageStore,
    TokenUsageFilter,
    TokenUsageSummaryResponse,
    UsageAggregationDimension,
)

_DIMENSIONS: set[str] = {"task", "plan", "session", "workspace"}


class TokenUsageSummaryGateway(Protocol):
    def summarize(
        self,
        *,
        dimension: UsageAggregationDimension,
        filters: TokenUsageFilter,
    ) -> TokenUsageSummaryResponse: ...


class DefaultTokenUsageSummaryGateway:
    """Query usage summaries for one workspace-local ledger."""

    def __init__(
        self,
        *,
        store: SqliteTokenUsageStore,
        workspace_id: str,
    ) -> None:
        self._store = store
        self._workspace_id = workspace_id

    def summarize(
        self,
        *,
        dimension: UsageAggregationDimension,
        filters: TokenUsageFilter,
    ) -> TokenUsageSummaryResponse:
        safe_filters = TokenUsageFilter(
            workspace_id=self._workspace_id,
            session_id=filters.session_id,
            plan_id=filters.plan_id,
            task_node_id=filters.task_node_id,
            from_time=filters.from_time,
            to_time=filters.to_time,
            provider=filters.provider,
            model=filters.model,
        )
        return self._store.summarize(dimension=dimension, filters=safe_filters)


def _usage_token_summary_response(
    request: HttpApiRequest,
    gateway: TokenUsageSummaryGateway | None,
) -> HttpApiResponse:
    if gateway is None:
        return _error_response(
            503,
            ApiError(
                code="internal_error",
                message="token usage gateway is not configured",
                details={"route": "usage_token_summary"},
            ),
            request_id=_request_id_hint(request),
        )

    query = _request_query(request)
    raw_dimension = query.get("dimension", "workspace")
    if raw_dimension not in _DIMENSIONS:
        return _error_response(
            400,
            ApiError(
                code="bad_request",
                message="invalid usage aggregation dimension",
                details={
                    "dimension": raw_dimension,
                    "allowed": sorted(_DIMENSIONS),
                },
            ),
            request_id=_request_id_hint(request),
        )

    filters = TokenUsageFilter(
        workspace_id="current",
        session_id=query.get("sessionId"),
        plan_id=query.get("planId"),
        task_node_id=query.get("taskNodeId"),
        from_time=query.get("from"),
        to_time=query.get("to"),
        provider=query.get("provider"),
        model=query.get("model"),
    )
    summary = gateway.summarize(
        dimension=cast(UsageAggregationDimension, raw_dimension),
        filters=filters,
    )
    request_id = _request_id_hint(request)
    response_kwargs: dict[str, Any] = {"ok": True, "data": summary}
    if request_id is not None:
        response_kwargs["request_id"] = request_id
    return _contract_response(QueryResponse[TokenUsageSummaryResponse](**response_kwargs))


__all__ = [
    "DefaultTokenUsageSummaryGateway",
    "TokenUsageSummaryGateway",
    "_usage_token_summary_response",
]
