"""Execution Plane service errors."""

from __future__ import annotations

from typing import Any, Literal

ExecutionPlaneErrorCode = Literal[
    "invalid_task_request",
    "idempotency_conflict",
    "capability_not_available",
    "permission_denied",
    "task_not_found",
    "task_not_cancellable",
    "task_not_retryable",
    "lease_conflict",
    "execution_failed",
    "result_not_found",
    "evidence_not_found",
]


class ExecutionPlaneError(RuntimeError):
    """Machine-readable error raised by Task API service operations."""

    def __init__(
        self,
        code: ExecutionPlaneErrorCode,
        message: str,
        *,
        status_code: int = 400,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = dict(details or {})
