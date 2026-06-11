"""Product-facing token usage analytics contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

UsageAggregationDimension = Literal["task", "plan", "session", "workspace"]
UsageSource = Literal[
    "provider_reported",
    "provider_partial",
    "estimated",
    "unavailable",
]
CacheRateSource = Literal["hit_miss_tokens", "input_tokens", "unavailable"]


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class _UsageModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
        validate_assignment=True,
    )


class TokenUsageEvent(_UsageModel):
    """One normalized usage event for a completed LLM provider call."""

    usage_event_id: str = Field(min_length=1)
    occurred_at: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    session_id: str | None = None
    plan_id: str | None = None
    task_node_id: str | None = None
    agent_run_id: str | None = None
    request_purpose: str = Field(min_length=1)
    provider: str | None = None
    model: str | None = None
    provider_request_id_hash: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    cached_tokens: int | None = Field(default=None, ge=0)
    cache_hit_tokens: int | None = Field(default=None, ge=0)
    cache_miss_tokens: int | None = Field(default=None, ge=0)
    cache_hit_ratio: float | None = Field(default=None, ge=0, le=1)
    usage_source: UsageSource
    cache_rate_source: CacheRateSource
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("workspace_id")
    @classmethod
    def _validate_workspace_id(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError("workspace_id must be renderer-safe")
        return value

    @field_validator(
        "session_id",
        "plan_id",
        "task_node_id",
        "agent_run_id",
        "provider",
        "model",
        "provider_request_id_hash",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class TokenUsageSummary(_UsageModel):
    """Aggregate usage row for one Product dimension."""

    dimension: UsageAggregationDimension
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    session_id: str | None = None
    plan_id: str | None = None
    task_node_id: str | None = None
    call_count: int = Field(ge=0)
    unknown_usage_call_count: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    cached_tokens: int | None = Field(default=None, ge=0)
    cache_hit_tokens: int | None = Field(default=None, ge=0)
    cache_miss_tokens: int | None = Field(default=None, ge=0)
    cache_hit_ratio: float | None = Field(default=None, ge=0, le=1)
    cache_rate_source: CacheRateSource
    first_occurred_at: str | None = None
    last_occurred_at: str | None = None


class TokenUsageSummaryResponse(_UsageModel):
    """Workspace-scoped token usage summary response payload."""

    dimension: UsageAggregationDimension
    totals: TokenUsageSummary
    rows: tuple[TokenUsageSummary, ...] = ()

    @model_validator(mode="after")
    def _validate_totals_dimension(self) -> TokenUsageSummaryResponse:
        if self.totals.dimension != self.dimension:
            raise ValueError("totals dimension must match response dimension")
        return self


def usage_model_dump(model: _UsageModel) -> dict[str, Any]:
    """Return the JSON-ready camelCase contract shape."""

    return model.model_dump(mode="json", by_alias=True)
