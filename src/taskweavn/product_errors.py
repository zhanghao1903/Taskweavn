"""Product-level error taxonomy shared by backend domains and UI contracts."""

from __future__ import annotations

from typing import Literal

ProductErrorCategory = Literal[
    "input_validation",
    "missing_context",
    "command_conflict",
    "backend_busy",
    "network_or_event_sync",
    "llm_auth_or_config",
    "llm_rate_or_retry_exhausted",
    "llm_context_or_capability",
    "tool_or_sandbox_failure",
    "task_execution_failed",
    "task_cancelled_or_interrupted",
    "audit_evidence_partial",
    "unexpected_internal",
]

ProductRecoveryAction = Literal[
    "edit_input",
    "answer_ask",
    "retry_command",
    "retry_task",
    "refresh_snapshot",
    "wait_for_events",
    "open_audit",
    "open_settings",
    "export_diagnostics",
    "none",
]

ProductErrorSeverity = Literal[
    "recoverable",
    "action_required",
    "blocked",
    "fatal",
    "unknown",
]


def product_error_details(
    category: ProductErrorCategory,
    recovery_actions: tuple[ProductRecoveryAction, ...],
    *,
    severity: ProductErrorSeverity = "recoverable",
    user_message_key: str | None = None,
    diagnostic_refs: dict[str, object] | None = None,
    audit_ref: dict[str, object] | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build stable product metadata for errors and failure summaries."""

    details: dict[str, object] = {
        "productCategory": category,
        "recoveryActions": list(recovery_actions),
        "severity": severity,
    }
    if user_message_key is not None:
        details["userMessageKey"] = user_message_key
    if diagnostic_refs:
        details["diagnosticRefs"] = diagnostic_refs
    if audit_ref:
        details["auditRef"] = audit_ref
    if extra:
        details.update(extra)
    return details


def product_error_details_for_api_error(
    code: str,
    *,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    """Map transport-level API errors to Product 1.0 error semantics."""

    if code == "bad_request":
        return product_error_details(
            "input_validation",
            ("edit_input",),
            severity="action_required",
            user_message_key="api.bad_request",
            extra=extra,
        )
    if code == "not_found":
        return product_error_details(
            "missing_context",
            ("refresh_snapshot",),
            severity="action_required",
            user_message_key="api.not_found",
            extra=extra,
        )
    if code in {"version_conflict", "idempotency_conflict"}:
        return product_error_details(
            "command_conflict",
            ("refresh_snapshot", "retry_command"),
            severity="recoverable",
            user_message_key=f"api.{code}",
            extra=extra,
        )
    if code == "command_rejected":
        return product_error_details(
            "command_conflict",
            ("refresh_snapshot",),
            severity="action_required",
            user_message_key="api.command_rejected",
            extra=extra,
        )
    if code == "permission_denied":
        return product_error_details(
            "missing_context",
            ("open_audit",),
            severity="blocked",
            user_message_key="api.permission_denied",
            extra=extra,
        )
    if code == "backend_busy":
        return product_error_details(
            "backend_busy",
            ("wait_for_events", "retry_command"),
            severity="recoverable",
            user_message_key="api.backend_busy",
            extra=extra,
        )
    if code == "resync_required":
        return product_error_details(
            "network_or_event_sync",
            ("refresh_snapshot", "wait_for_events"),
            severity="recoverable",
            user_message_key="api.resync_required",
            extra=extra,
        )
    return product_error_details(
        "unexpected_internal",
        ("refresh_snapshot", "export_diagnostics"),
        severity="unknown",
        user_message_key="api.internal_error",
        extra=extra,
    )


def product_error_details_for_llm_classification(
    classification: object,
    *,
    retry_count: int = 0,
    diagnostic_refs: dict[str, object] | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    """Map LLM provider classifications without coupling callers to LLM types."""

    value = getattr(classification, "value", classification)
    classification_value = str(value)
    details_extra = {"llmClassification": classification_value, **(extra or {})}
    if retry_count:
        details_extra["retryCount"] = retry_count

    if classification_value == "fatal_auth":
        return product_error_details(
            "llm_auth_or_config",
            ("open_settings", "export_diagnostics"),
            severity="action_required",
            user_message_key="llm.auth_or_config",
            diagnostic_refs=diagnostic_refs,
            extra=details_extra,
        )
    if classification_value in {"retryable", "rate_limit"}:
        return product_error_details(
            "llm_rate_or_retry_exhausted",
            ("wait_for_events", "retry_task", "export_diagnostics"),
            severity="recoverable",
            user_message_key="llm.rate_or_retry_exhausted",
            diagnostic_refs=diagnostic_refs,
            extra=details_extra,
        )
    if classification_value in {"context_limit", "fatal_capability"}:
        return product_error_details(
            "llm_context_or_capability",
            ("edit_input", "open_settings", "export_diagnostics"),
            severity="action_required",
            user_message_key="llm.context_or_capability",
            diagnostic_refs=diagnostic_refs,
            extra=details_extra,
        )
    if classification_value == "fatal_request":
        return product_error_details(
            "llm_auth_or_config",
            ("open_settings", "export_diagnostics"),
            severity="action_required",
            user_message_key="llm.request_or_config",
            diagnostic_refs=diagnostic_refs,
            extra=details_extra,
        )
    return product_error_details(
        "unexpected_internal",
        ("open_audit", "export_diagnostics"),
        severity="unknown",
        user_message_key="llm.unknown_failure",
        diagnostic_refs=diagnostic_refs,
        extra=details_extra,
    )


def product_error_details_for_task_failure(
    *,
    error_type: str | None = None,
    interrupted: bool = False,
    can_retry: bool = True,
    diagnostic_refs: dict[str, object] | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    """Map Task execution failures to stable recovery guidance."""

    actions: tuple[ProductRecoveryAction, ...]
    if can_retry:
        actions = ("retry_task", "open_audit", "export_diagnostics")
    else:
        actions = ("open_audit", "export_diagnostics")
    details_extra = dict(extra or {})
    if error_type:
        details_extra["errorType"] = error_type
    if interrupted:
        return product_error_details(
            "task_cancelled_or_interrupted",
            actions,
            severity="recoverable",
            user_message_key="task.cancelled_or_interrupted",
            diagnostic_refs=diagnostic_refs,
            extra=details_extra,
        )
    return product_error_details(
        "task_execution_failed",
        actions,
        severity="recoverable" if can_retry else "blocked",
        user_message_key="task.execution_failed",
        diagnostic_refs=diagnostic_refs,
        extra=details_extra,
    )


def merge_product_error_details(
    code: str,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    """Attach default product metadata while preserving explicit caller details."""

    existing = dict(details or {})
    if "productCategory" in existing and "recoveryActions" in existing:
        return existing
    return product_error_details_for_api_error(code, extra=existing)


__all__ = [
    "ProductErrorCategory",
    "ProductErrorSeverity",
    "ProductRecoveryAction",
    "merge_product_error_details",
    "product_error_details",
    "product_error_details_for_api_error",
    "product_error_details_for_llm_classification",
    "product_error_details_for_task_failure",
]
