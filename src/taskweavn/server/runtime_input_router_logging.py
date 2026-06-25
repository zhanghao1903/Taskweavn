"""Summary logging helpers for Runtime Input Router dispatches."""

from __future__ import annotations

from typing import Any

from taskweavn.observability import LogContext, get_object_logger
from taskweavn.server.ui_contract.envelopes import CommandResponse
from taskweavn.server.ui_contract.read_only_inquiry import ReadOnlyInquiryResult
from taskweavn.server.ui_contract.runtime_input import (
    RuntimeInputOutcome,
    RuntimeInputRouteDecision,
    RuntimeInputRouteRequest,
)


def log_runtime_input_router_dispatch(
    request: RuntimeInputRouteRequest,
    decision: RuntimeInputRouteDecision,
    outcome: RuntimeInputOutcome,
    *,
    command_response: CommandResponse | None = None,
    inquiry_result: ReadOnlyInquiryResult | None = None,
) -> None:
    """Log final routing facts without recording raw user input."""

    get_object_logger("runtime").info(
        "runtime_input_router_dispatch",
        context=LogContext(
            session_id=request.session_id,
            agent_id="runtime_input_router",
        ),
        data={
            "request_id": request.command_id,
            "workspace_id": request.workspace_id,
            "decision_id": decision.id,
            "intent": decision.intent,
            "dispatch_target": decision.dispatch_target,
            "side_effect": decision.side_effect,
            "confidence": decision.confidence,
            "scope_kind": decision.scope.kind,
            "plan_id": decision.scope.plan_id,
            "task_node_id": decision.scope.task_node_id,
            "outcome_status": outcome.status,
            "recovery_actions": list(outcome.recovery_actions),
            "pending_clarification_kind": (
                None
                if outcome.pending_clarification is None
                else outcome.pending_clarification.kind
            ),
            "command_response": _command_response_summary(command_response),
            "inquiry_result": _inquiry_result_summary(inquiry_result),
            "related_ref_count": len(decision.related_refs),
            "requires_confirmation": decision.dispatch_target
            == "resolve_confirmation",
        },
    )


def _command_response_summary(
    command_response: CommandResponse | None,
) -> dict[str, Any] | None:
    if command_response is None:
        return None
    result = command_response.result
    return {
        "ok": command_response.ok,
        "request_id": command_response.request_id,
        "status": None if result is None else result.status,
        "command_id": None if result is None else result.command_id,
        "published_task_count": 0 if result is None else len(result.published_task_ids),
        "emitted_message_count": 0 if result is None else len(result.emitted_message_ids),
        "error_code": None if command_response.error is None else command_response.error.code,
    }


def _inquiry_result_summary(
    inquiry_result: ReadOnlyInquiryResult | None,
) -> dict[str, Any] | None:
    if inquiry_result is None:
        return None
    return {
        "inquiry_id": inquiry_result.inquiry_id,
        "status": inquiry_result.status,
        "evidence_ref_count": len(inquiry_result.evidence_refs),
        "warning_count": len(inquiry_result.warnings),
    }


__all__ = ["log_runtime_input_router_dispatch"]
