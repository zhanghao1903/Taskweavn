"""Error model for the Plato UI contract."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from taskweavn.product_errors import merge_product_error_details
from taskweavn.server.ui_contract.base import UiContractModel

ApiErrorCode = Literal[
    "bad_request",
    "not_found",
    "version_conflict",
    "command_rejected",
    "permission_denied",
    "backend_busy",
    "resync_required",
    "internal_error",
    "idempotency_conflict",
]


class ApiError(UiContractModel):
    code: ApiErrorCode
    message: str = Field(min_length=1)
    retryable: bool = False
    details: dict[str, object] = Field(default_factory=dict)


def bad_request(message: str, **details: object) -> ApiError:
    return ApiError(
        code="bad_request",
        message=message,
        details=merge_product_error_details("bad_request", details),
    )


def not_found(message: str, **details: object) -> ApiError:
    return ApiError(
        code="not_found",
        message=message,
        details=merge_product_error_details("not_found", details),
    )


def command_rejected(message: str, **details: object) -> ApiError:
    return ApiError(
        code="command_rejected",
        message=message,
        details=merge_product_error_details("command_rejected", details),
    )


def internal_error(message: str = "Internal error", **details: object) -> ApiError:
    return ApiError(
        code="internal_error",
        message=message,
        retryable=True,
        details=merge_product_error_details("internal_error", details),
    )
