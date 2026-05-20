"""Shared framework-neutral HTTP transport models."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


class _FrozenTransportModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class HttpApiRequest(_FrozenTransportModel):
    """Small framework-neutral request shape used by HTTP/RPC adapters."""

    method: str = Field(min_length=1)
    path: str = Field(min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | None = None


class ApiErrorBody(_FrozenTransportModel):
    """Stable transport error body for non-UI-contract transports."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class HttpApiResponse(_FrozenTransportModel):
    """Small framework-neutral response shape used by HTTP/RPC adapters."""

    status_code: int = Field(ge=100, le=599)
    headers: dict[str, str] = Field(
        default_factory=lambda: {"content-type": "application/json"}
    )
    body: Any


__all__ = [
    "ApiErrorBody",
    "HttpApiRequest",
    "HttpApiResponse",
]
