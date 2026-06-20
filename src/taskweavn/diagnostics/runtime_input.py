"""Runtime Input Router diagnostic summary collection."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from taskweavn.interaction import AgentMessage

RUNTIME_INPUT_DIAGNOSTIC_SCHEMA_VERSION = (
    "plato.runtime_input.diagnostic_summary.v1"
)


@dataclass
class _RuntimeInputRouteSummary:
    command_id: str
    user_message_ids: list[str] = field(default_factory=list)
    router_trace_message_ids: list[str] = field(default_factory=list)
    question_card_message_ids: list[str] = field(default_factory=list)
    activity_message_ids: list[str] = field(default_factory=list)
    downstream_command_ids: list[str] = field(default_factory=list)
    decision_ids: list[str] = field(default_factory=list)
    audit_record_ids: list[str] = field(default_factory=list)
    audit_evidence_ids: list[str] = field(default_factory=list)
    related_refs: list[dict[str, Any]] = field(default_factory=list)
    input_preview: str | None = None
    intent: str | None = None
    scope_kind: str | None = None
    confidence: str | None = None
    side_effect: str | None = None
    dispatch_target: str | None = None
    outcome_status: str | None = None
    explanation_preview: str | None = None
    activity_kinds: list[str] = field(default_factory=list)
    contract_command_kinds: list[str] = field(default_factory=list)
    contract_command_statuses: list[str] = field(default_factory=list)


def collect_runtime_input_diagnostic_summary(
    *,
    session_id: str,
    messages: Iterable[AgentMessage],
    max_routes: int,
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Build a safe route-level summary from durable Router messages.

    The collector intentionally reads only persisted MessageStream facts. It
    does not inspect raw provider payloads, raw prompts, hidden LLM logs, or
    command internals. The bundle writer applies the standard diagnostics
    redaction pass to the returned payload.
    """

    routes: dict[str, _RuntimeInputRouteSummary] = {}
    total_runtime_messages = 0
    for message in sorted(messages, key=lambda item: (item.created_at, item.message_id)):
        command_id, role = _runtime_input_route_key(message)
        if command_id is None or role is None:
            continue
        total_runtime_messages += 1
        route = routes.setdefault(command_id, _RuntimeInputRouteSummary(command_id))
        _merge_message(route, message, role)

    if not routes:
        return None, ("runtime input route messages are not present",)

    ordered = sorted(
        routes.values(),
        key=lambda route: (
            route.user_message_ids[:1],
            route.router_trace_message_ids[:1],
            route.command_id,
        ),
    )
    if max_routes == 0:
        selected = []
    elif max_routes > 0:
        selected = ordered[-max_routes:]
    else:
        selected = ordered
    warnings: list[str] = []
    if len(ordered) > len(selected):
        warnings.append(
            f"runtime input route summary truncated from {len(ordered)} to "
            f"{len(selected)} route(s)"
        )

    payload = {
        "schemaVersion": RUNTIME_INPUT_DIAGNOSTIC_SCHEMA_VERSION,
        "sessionId": session_id,
        "routeCount": len(ordered),
        "includedRouteCount": len(selected),
        "runtimeMessageCount": total_runtime_messages,
        "truncated": len(ordered) > len(selected),
        "redactionPolicy": {
            "source": "MessageStream safe Router context",
            "modelInputData": "excluded",
            "llmProviderData": "excluded",
            "rawLogsIncluded": False,
            "rawSqlRowsIncluded": False,
        },
        "routes": [_route_payload(route) for route in selected],
    }
    return payload, tuple(warnings)


def _merge_message(
    route: _RuntimeInputRouteSummary,
    message: AgentMessage,
    role: str,
) -> None:
    _append_unique(route.audit_record_ids, f"record-message-{message.message_id}")
    _append_unique(route.audit_evidence_ids, f"evidence-record-message-{message.message_id}")

    if role == "user_input":
        _append_unique(route.user_message_ids, message.message_id)
        route.input_preview = message.content
    elif role == "router_trace":
        _append_unique(route.router_trace_message_ids, message.message_id)
        _merge_router_trace(route, message)
    elif role == "question_card":
        _append_unique(route.question_card_message_ids, message.message_id)
        _merge_question_card(route, message)
    elif role == "activity":
        _append_unique(route.activity_message_ids, message.message_id)
        _merge_activity(route, message)
    elif role == "contract_command":
        _append_unique(route.activity_message_ids, message.message_id)
        _merge_contract_command(route, message)


def _merge_router_trace(route: _RuntimeInputRouteSummary, message: AgentMessage) -> None:
    if message.related_action_id is not None:
        _append_unique(route.decision_ids, message.related_action_id)
    for ref in _refs_from_context(message.context):
        _append_unique_mapping(route.related_refs, ref)
    render = message.context.get("conversation_render")
    if not isinstance(render, Mapping):
        return
    trace = render.get("routerTrace")
    if not isinstance(trace, Mapping):
        return
    route.intent = _string(trace.get("intent")) or route.intent
    route.scope_kind = _string(trace.get("scopeKind")) or route.scope_kind
    route.confidence = _string(trace.get("confidence")) or route.confidence
    route.side_effect = _string(trace.get("sideEffect")) or route.side_effect
    route.dispatch_target = _string(trace.get("dispatchTarget")) or route.dispatch_target
    route.outcome_status = _string(trace.get("outcomeStatus")) or route.outcome_status
    route.explanation_preview = _string(trace.get("explanation")) or route.explanation_preview


def _merge_question_card(route: _RuntimeInputRouteSummary, message: AgentMessage) -> None:
    if message.related_action_id is not None:
        _append_unique(route.decision_ids, message.related_action_id)
    render = message.context.get("conversation_render")
    if not isinstance(render, Mapping):
        return
    card = render.get("questionCard")
    if not isinstance(card, Mapping):
        return
    target_ref = card.get("targetRef")
    if isinstance(target_ref, Mapping):
        _append_unique_mapping(route.related_refs, dict(target_ref))


def _merge_activity(route: _RuntimeInputRouteSummary, message: AgentMessage) -> None:
    if message.related_action_id is not None:
        _append_unique(route.decision_ids, message.related_action_id)
    context = message.context
    _append_unique_string(route.decision_ids, context.get("runtime_input_decision_id"))
    _append_unique_string(route.activity_kinds, context.get("runtime_input_activity_kind"))
    route.side_effect = _string(context.get("runtime_input_side_effect")) or route.side_effect
    route.outcome_status = (
        _string(context.get("runtime_input_outcome_status")) or route.outcome_status
    )
    for ref in _refs_from_context(context):
        _append_unique_mapping(route.related_refs, ref)


def _merge_contract_command(
    route: _RuntimeInputRouteSummary,
    message: AgentMessage,
) -> None:
    if message.related_action_id is not None:
        _append_unique(route.downstream_command_ids, message.related_action_id)
    context = message.context
    _append_unique_string(route.downstream_command_ids, context.get("contract_command_id"))
    _append_unique_string(route.activity_kinds, context.get("runtime_input_activity_kind"))
    _append_unique_string(route.contract_command_kinds, context.get("contract_command_kind"))
    _append_unique_string(route.contract_command_statuses, context.get("contract_command_status"))
    route.side_effect = _string(context.get("runtime_input_side_effect")) or route.side_effect
    for key, kind in (
        ("contract_guidance_id", "guidance"),
        ("contract_ask_id", "ask"),
        ("contract_confirmation_id", "confirmation"),
        ("contract_plan_id", "plan"),
        ("contract_task_node_id", "task"),
    ):
        value = _string(context.get(key))
        if value is None:
            continue
        _append_unique_mapping(
            route.related_refs,
            {
                "kind": kind,
                "id": value,
                "label": f"{kind}:{value}",
            },
        )


def _runtime_input_route_key(message: AgentMessage) -> tuple[str | None, str | None]:
    message_id = message.message_id
    if message_id.startswith("runtime-input-user-"):
        return message_id.removeprefix("runtime-input-user-"), "user_input"
    if message_id.startswith("runtime-input-trace-"):
        return message_id.removeprefix("runtime-input-trace-"), "router_trace"
    if message_id.startswith("runtime-question-"):
        return message_id.removeprefix("runtime-question-"), "question_card"
    if message_id.startswith("runtime-input-activity-"):
        remaining = message_id.removeprefix("runtime-input-activity-")
        _, _, command_id = remaining.partition("-")
        if command_id:
            return command_id, "activity"
    contract_command_id = _string(message.context.get("contract_command_id"))
    if contract_command_id is not None and message.context.get("contract_command_kind"):
        return contract_command_id, "contract_command"
    return None, None


def _refs_from_context(context: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    raw_refs = context.get("activity_related_refs")
    if not isinstance(raw_refs, list):
        return ()
    refs: list[dict[str, Any]] = []
    for raw_ref in raw_refs:
        if isinstance(raw_ref, Mapping):
            refs.append(dict(raw_ref))
    return tuple(refs)


def _route_payload(route: _RuntimeInputRouteSummary) -> dict[str, Any]:
    return {
        "commandId": route.command_id,
        "decisionIds": tuple(route.decision_ids),
        "conversationMessageIds": tuple(
            [
                *route.user_message_ids,
                *route.router_trace_message_ids,
                *route.question_card_message_ids,
            ]
        ),
        "activityMessageIds": tuple(route.activity_message_ids),
        "downstreamCommandIds": tuple(route.downstream_command_ids),
        "auditRefs": {
            "recordIds": tuple(route.audit_record_ids),
            "evidenceIds": tuple(route.audit_evidence_ids),
        },
        "inputPreview": route.input_preview,
        "intent": route.intent,
        "scopeKind": route.scope_kind,
        "confidence": route.confidence,
        "sideEffect": route.side_effect,
        "dispatchTarget": route.dispatch_target,
        "outcomeStatus": route.outcome_status,
        "explanationPreview": route.explanation_preview,
        "activityKinds": tuple(route.activity_kinds),
        "contractCommandKinds": tuple(route.contract_command_kinds),
        "contractCommandStatuses": tuple(route.contract_command_statuses),
        "relatedRefs": tuple(route.related_refs),
        "diagnosticDescriptor": {
            "kind": "runtime_input_route",
            "redacted": True,
            "linksUserInput": bool(route.user_message_ids),
            "linksRouterDecision": bool(route.decision_ids),
            "linksActivity": bool(route.activity_message_ids),
            "linksDownstreamCommand": bool(route.downstream_command_ids),
            "linksAuditRecord": bool(route.audit_record_ids),
        },
    }


def _append_unique(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def _append_unique_string(target: list[str], value: Any) -> None:
    text = _string(value)
    if text is not None:
        _append_unique(target, text)


def _append_unique_mapping(target: list[dict[str, Any]], value: dict[str, Any]) -> None:
    if value not in target:
        target.append(value)


def _string(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


__all__ = [
    "RUNTIME_INPUT_DIAGNOSTIC_SCHEMA_VERSION",
    "collect_runtime_input_diagnostic_summary",
]
