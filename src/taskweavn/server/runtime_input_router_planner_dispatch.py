"""Planner proposal dispatch boundary for Runtime Input Router."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from taskweavn.server.runtime_input_llm_router import (
    RuntimeInputRoutePlanner,
    RuntimeInputRouteProposal,
)
from taskweavn.server.runtime_input_router_task_drafts import (
    wechat_resolution_from_task_request_draft,
)
from taskweavn.server.runtime_input_wechat import WeChatSendResolution
from taskweavn.server.ui_contract.envelopes import QueryResponse
from taskweavn.server.ui_contract.runtime_input import (
    RuntimeInputDispatchTarget,
    RuntimeInputRouteRequest,
    RuntimeInputRouteResult,
)

type PlannerDispatchResponse = QueryResponse[RuntimeInputRouteResult]

_PLANNER_BASE_DISPATCH_TARGETS: tuple[RuntimeInputDispatchTarget, ...] = (
    "read_only_inquiry",
    "record_guidance",
    "existing_command",
    "execution_handoff",
    "clarification",
    "unsupported",
)


@dataclass(frozen=True)
class PlannerDispatchHandlers:
    answer_read_only_inquiry: Callable[
        [RuntimeInputRouteRequest, RuntimeInputRouteProposal],
        PlannerDispatchResponse,
    ]
    record_guidance: Callable[[RuntimeInputRouteRequest], PlannerDispatchResponse]
    create_execution_task: Callable[[RuntimeInputRouteRequest], PlannerDispatchResponse]
    create_wechat_send_execution_task: Callable[
        [RuntimeInputRouteRequest, WeChatSendResolution],
        PlannerDispatchResponse,
    ]
    stop_selected_task: Callable[
        [RuntimeInputRouteRequest, RuntimeInputRouteProposal],
        PlannerDispatchResponse,
    ]
    retry_selected_task: Callable[
        [RuntimeInputRouteRequest, RuntimeInputRouteProposal],
        PlannerDispatchResponse,
    ]
    resolve_ask: Callable[
        [RuntimeInputRouteRequest, RuntimeInputRouteProposal],
        PlannerDispatchResponse,
    ]
    resolve_confirmation: Callable[
        [RuntimeInputRouteRequest, RuntimeInputRouteProposal],
        PlannerDispatchResponse,
    ]
    planner_clarification: Callable[
        [RuntimeInputRouteRequest, RuntimeInputRouteProposal],
        PlannerDispatchResponse,
    ]
    unsupported: Callable[..., PlannerDispatchResponse]


def route_planner_result(
    request: RuntimeInputRouteRequest,
    route_planner: RuntimeInputRoutePlanner | None,
    *,
    active_ask: bool,
    active_confirmation: bool,
    handlers: PlannerDispatchHandlers,
) -> PlannerDispatchResponse | None:
    if route_planner is None:
        return None
    allowed_dispatch_targets = _allowed_dispatch_targets(
        active_ask=active_ask,
        active_confirmation=active_confirmation,
    )
    planner_result = route_planner.plan(
        request,
        allowed_dispatch_targets=allowed_dispatch_targets,
        active_ask=active_ask,
        active_confirmation=active_confirmation,
    )
    proposal = planner_result.proposal
    if planner_result.status != "planned" or proposal is None:
        return handlers.unsupported(
            request,
            intent="unsupported",
            dispatch_target="unsupported",
            side_effect="no_effect",
            explanation=planner_result.warning
            or f"Router planner returned {planner_result.status}.",
            user_message=(
                "The Router planner could not produce a safe route. "
                "No product or workspace state changed."
            ),
        )
    return dispatch_planner_proposal(request, proposal, handlers=handlers)


def dispatch_planner_proposal(
    request: RuntimeInputRouteRequest,
    proposal: RuntimeInputRouteProposal,
    *,
    handlers: PlannerDispatchHandlers,
) -> PlannerDispatchResponse | None:
    if proposal.dispatch_target == "read_only_inquiry":
        return handlers.answer_read_only_inquiry(request, proposal)
    if proposal.dispatch_target == "record_guidance":
        return handlers.record_guidance(request)
    if proposal.dispatch_target == "existing_command":
        return _dispatch_existing_command(request, proposal, handlers=handlers)
    if proposal.dispatch_target == "resolve_ask":
        return handlers.resolve_ask(request, proposal)
    if proposal.dispatch_target == "resolve_confirmation":
        return handlers.resolve_confirmation(request, proposal)
    if proposal.dispatch_target == "execution_handoff":
        return _dispatch_execution_handoff(request, proposal, handlers=handlers)
    if proposal.dispatch_target == "clarification":
        return handlers.planner_clarification(request, proposal)
    if proposal.dispatch_target == "unsupported":
        return handlers.unsupported(
            request,
            intent=proposal.intent,
            dispatch_target="unsupported",
            side_effect="no_effect",
            explanation=proposal.visible_reasoning_summary,
            user_message=proposal.user_message,
        )
    return handlers.unsupported(
        request,
        intent=proposal.intent,
        dispatch_target="unsupported",
        side_effect="no_effect",
        explanation=(
            "Planner proposal used an unsupported dispatch target for this "
            f"router slice: {proposal.dispatch_target}."
        ),
        user_message=(
            "The Router could not dispatch that route safely. "
            "No product or workspace state changed."
        ),
    )


def _allowed_dispatch_targets(
    *,
    active_ask: bool,
    active_confirmation: bool,
) -> tuple[RuntimeInputDispatchTarget, ...]:
    targets = list(_PLANNER_BASE_DISPATCH_TARGETS)
    if active_ask:
        targets.append("resolve_ask")
    if active_confirmation:
        targets.append("resolve_confirmation")
    return tuple(targets)


def _dispatch_execution_handoff(
    request: RuntimeInputRouteRequest,
    proposal: RuntimeInputRouteProposal,
    *,
    handlers: PlannerDispatchHandlers,
) -> PlannerDispatchResponse:
    task_request_draft = proposal.task_request_draft
    if task_request_draft is None:
        return handlers.unsupported(
            request,
            intent=proposal.intent,
            dispatch_target="unsupported",
            side_effect="no_effect",
            explanation="Planner execution_handoff proposal did not include task draft.",
            user_message=(
                "The Router could not validate that task request. "
                "No product or workspace state changed."
            ),
        )
    wechat_resolution = wechat_resolution_from_task_request_draft(task_request_draft)
    if wechat_resolution is not None:
        return handlers.create_wechat_send_execution_task(request, wechat_resolution)
    return handlers.create_execution_task(request)


def _dispatch_existing_command(
    request: RuntimeInputRouteRequest,
    proposal: RuntimeInputRouteProposal,
    *,
    handlers: PlannerDispatchHandlers,
) -> PlannerDispatchResponse:
    command_draft = proposal.command_draft
    if command_draft is None:
        return handlers.unsupported(
            request,
            intent=proposal.intent,
            dispatch_target="unsupported",
            side_effect="no_effect",
            explanation="Planner existing_command proposal did not include command draft.",
            user_message=(
                "The Router could not validate that command. "
                "No product or workspace state changed."
            ),
        )
    if command_draft.command_kind == "stop_task":
        return handlers.stop_selected_task(request, proposal)
    if command_draft.command_kind == "retry_task":
        return handlers.retry_selected_task(request, proposal)
    return handlers.unsupported(
        request,
        intent=proposal.intent,
        dispatch_target="unsupported",
        side_effect="no_effect",
        explanation=(
            "Planner command draft was valid but unsupported by this router slice: "
            f"{command_draft.command_kind}."
        ),
        user_message=(
            "That command is not available through Runtime Input yet. "
            "No product or workspace state changed."
        ),
    )


__all__ = [
    "PlannerDispatchHandlers",
    "dispatch_planner_proposal",
    "route_planner_result",
]
