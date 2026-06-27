"""Runtime Input Router foundation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast, get_args

from taskweavn.contract_revision.models import (
    ContractCommandRequest,
    ContractCommandResult,
)
from taskweavn.contract_revision.service import ContractRevisionCommandService
from taskweavn.execution_plane.errors import ExecutionPlaneError
from taskweavn.execution_plane.models import TaskError, TaskExecution
from taskweavn.execution_plane.service import TaskApiService
from taskweavn.server.read_only_inquiry import (
    DefaultReadOnlyInquiryService,
    DiagnosticSupportContextProvider,
    ReadOnlyInquiryService,
    WorkspaceInspectionContextProvider,
)
from taskweavn.server.runtime_input_activity import RuntimeInputActivityPublisher
from taskweavn.server.runtime_input_llm_router import (
    RuntimeInputRoutePlanner,
    RuntimeInputRouteProposal,
)
from taskweavn.server.runtime_input_router_logging import (
    log_runtime_input_router_dispatch,
)
from taskweavn.server.runtime_input_router_planner_dispatch import (
    PlannerDispatchHandlers,
    route_planner_result,
)
from taskweavn.server.runtime_input_wechat import (
    WeChatSendResolution,
    wechat_send_execution_payload,
    wechat_send_task_request,
)
from taskweavn.server.ui_contract.commands import (
    AnswerAskPayload,
    ResolveConfirmationPayload,
    RetryTaskPayload,
    StopTaskPayload,
)
from taskweavn.server.ui_contract.envelopes import (
    CommandRequest,
    CommandResponse,
    QueryResponse,
)
from taskweavn.server.ui_contract.gateway_protocols import (
    UiCommandGateway,
    UiQueryGateway,
)
from taskweavn.server.ui_contract.product_errors import ProductRecoveryAction
from taskweavn.server.ui_contract.read_only_inquiry import (
    ReadOnlyInquiryRef,
    ReadOnlyInquiryRefKind,
    ReadOnlyInquiryRequest,
    ReadOnlyInquiryResult,
    ReadOnlyInquiryScope,
    ReadOnlyInquiryStatus,
)
from taskweavn.server.ui_contract.runtime_input import (
    RuntimeInputConfidence,
    RuntimeInputDecisionScope,
    RuntimeInputDispatchTarget,
    RuntimeInputIntent,
    RuntimeInputOutcome,
    RuntimeInputOutcomeStatus,
    RuntimeInputRouteDecision,
    RuntimeInputRouteRequest,
    RuntimeInputRouteResult,
)
from taskweavn.server.ui_contract.view_models import (
    AskRequestView,
    ConfirmationActionView,
    SessionActivityItemKind,
    SessionActivityItemView,
    SessionActivityRefKind,
    SessionActivityRefView,
    SessionActivitySideEffect,
)
from taskweavn.server.ui_http_commands import (
    _answer_ask_with_resume_dispatch,
    _retry_task_with_optional_dispatch,
)
from taskweavn.task import ExecutionTriggerGateway

_VALID_PRODUCT_RECOVERY_ACTIONS: frozenset[str] = frozenset(
    get_args(ProductRecoveryAction)
)


class RuntimeInputRouter(Protocol):
    def route(
        self,
        request: RuntimeInputRouteRequest,
    ) -> QueryResponse[RuntimeInputRouteResult]: ...


@dataclass(frozen=True)
class DefaultRuntimeInputRouter:
    query_gateway: UiQueryGateway
    command_gateway: UiCommandGateway
    execution_trigger_gateway: ExecutionTriggerGateway | None = None
    read_only_inquiry_service: ReadOnlyInquiryService | None = None
    workspace_inspection_gateway: WorkspaceInspectionContextProvider | None = None
    diagnostic_support_provider: DiagnosticSupportContextProvider | None = None
    activity_publisher: RuntimeInputActivityPublisher | None = None
    contract_revision_service: ContractRevisionCommandService | None = None
    execution_plane_service: TaskApiService | None = None
    route_planner: RuntimeInputRoutePlanner | None = None

    def route(
        self,
        request: RuntimeInputRouteRequest,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        active_ask = self._active_ask(request)
        active_confirmation = self._active_confirmation(request)

        if request.mode == "ask":
            return self._answer_read_only_inquiry(request)
        if request.mode == "guide":
            return self._record_guidance(request)
        if request.mode == "change":
            return self._create_execution_task(request)

        planned = self._route_planner_result(
            request,
            active_ask=active_ask,
            active_confirmation=active_confirmation,
        )
        if planned is not None:
            return planned

        return self._unsupported(
            request,
            intent="unsupported",
            dispatch_target="unsupported",
            side_effect="no_effect",
            explanation=(
                "The Router could not produce a planner-backed route and no "
                "explicit input mode was provided."
            ),
            user_message=(
                "I could not route this input safely yet. No product or workspace state changed."
            ),
        )

    def _record_guidance(
        self,
        request: RuntimeInputRouteRequest,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        if self.contract_revision_service is None:
            return self._unsupported(
                request,
                intent="guidance",
                dispatch_target="record_guidance",
                side_effect="context_effect",
                explanation="Guidance routing is unavailable without command service.",
                user_message=(
                    "Guidance routing is not available through Runtime Input yet. "
                    "No product or workspace state changed."
                ),
            )
        decision = self._decision(
            request,
            intent="guidance",
            dispatch_target="record_guidance",
            side_effect="context_effect",
            explanation="Input recorded guidance as typed contract context.",
            related_refs=_selection_refs(request),
        )
        command_result = self.contract_revision_service.execute(
            ContractCommandRequest(
                command_id=request.command_id,
                idempotency_key=request.command_id,
                command_kind="record_guidance",
                workspace_id=request.workspace_id or "current",
                session_id=request.session_id,
                scope_kind=request.selection.scope_kind,
                plan_id=request.selection.plan_id,
                task_node_id=request.selection.task_node_id,
                source="runtime_input",
                router_decision_id=decision.id,
                payload={
                    "guidanceText": request.content,
                    "guidanceKind": "instruction",
                },
            )
        )
        accepted = command_result.status in {"accepted", "noop"}
        outcome = RuntimeInputOutcome(
            status="dispatched" if accepted else "rejected",
            user_message=(
                "Guidance was recorded for this scope."
                if accepted
                else "Guidance could not be recorded. No workspace files changed."
            ),
            recovery_actions=() if accepted else ("edit_input",),
        )
        return self._result(
            request,
            decision,
            outcome,
            activity=_activity_from_contract_result(request, decision, command_result)
            if command_result.activity is not None
            else None,
            activity_kind="guidance_recorded" if accepted else "recovery_note",
            publish_activity=not accepted,
        )

    def _create_execution_task(
        self,
        request: RuntimeInputRouteRequest,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        if self.contract_revision_service is None:
            return self._unsupported(
                request,
                intent="execution_request",
                dispatch_target="execution_handoff",
                side_effect="state_effect",
                explanation="Execution handoff is unavailable without command service.",
                user_message=(
                    "Workspace-changing input must go through a task execution "
                    "handoff. No product or workspace state changed."
                ),
            )
        plan_id = request.selection.plan_id
        scope_kind: Literal["plan", "session"] = "plan" if plan_id is not None else "session"
        decision = self._decision(
            request,
            intent="execution_request",
            dispatch_target="execution_handoff",
            side_effect="state_effect",
            explanation="Input created executable contract work without touching workspace files.",
            related_refs=_selection_refs(request),
        )
        command_result = self.contract_revision_service.execute(
            ContractCommandRequest(
                command_id=request.command_id,
                idempotency_key=request.command_id,
                command_kind="create_execution_task",
                workspace_id=request.workspace_id or "current",
                session_id=request.session_id,
                scope_kind=scope_kind,
                plan_id=plan_id,
                source="runtime_input",
                router_decision_id=decision.id,
                payload={"intent": request.content},
            )
        )
        accepted = command_result.status in {"accepted", "noop"}
        return self._result(
            request,
            decision,
            RuntimeInputOutcome(
                status="dispatched" if accepted else "rejected",
                user_message=(
                    "Execution work was added to the task plan."
                    if accepted
                    else ("Execution work could not be created. No workspace files changed.")
                ),
                recovery_actions=() if accepted else ("edit_input",),
            ),
            activity=_activity_from_contract_result(request, decision, command_result)
            if command_result.activity is not None
            else None,
            activity_kind="task_created" if accepted else "recovery_note",
            publish_activity=not accepted,
        )

    def _create_wechat_send_execution_task(
        self,
        request: RuntimeInputRouteRequest,
        resolution: WeChatSendResolution,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        if self.execution_plane_service is not None:
            return self._publish_wechat_send_execution_task(request, resolution)
        if self.contract_revision_service is None:
            return self._unsupported(
                request,
                intent="execution_request",
                dispatch_target="execution_handoff",
                side_effect="state_effect",
                explanation="WeChat send handoff is unavailable without command service.",
                user_message=(
                    "微信发送任务需要通过执行任务创建流程处理。当前流程不可用，"
                    "没有创建任务，也没有发送消息。"
                ),
            )
        plan_id = request.selection.plan_id
        scope_kind: Literal["plan", "session"] = "plan" if plan_id is not None else "session"
        decision = self._decision(
            request,
            intent="execution_request",
            dispatch_target="execution_handoff",
            side_effect="state_effect",
            explanation=(
                "Input created a bounded, confirmation-gated WeChat send execution task."
            ),
            related_refs=_selection_refs(request),
        )
        command_result = self.contract_revision_service.execute(
            ContractCommandRequest(
                command_id=request.command_id,
                idempotency_key=request.command_id,
                command_kind="create_execution_task",
                workspace_id=request.workspace_id or "current",
                session_id=request.session_id,
                scope_kind=scope_kind,
                plan_id=plan_id,
                source="runtime_input",
                router_decision_id=decision.id,
                payload=wechat_send_execution_payload(resolution),
            )
        )
        accepted = command_result.status in {"accepted", "noop"}
        return self._result(
            request,
            decision,
            RuntimeInputOutcome(
                status="dispatched" if accepted else "rejected",
                user_message=(
                    "微信发送任务已创建；真正发送前仍需要用户确认。"
                    if accepted
                    else "微信发送任务未能创建。没有发送消息。"
                ),
                recovery_actions=() if accepted else ("edit_input",),
            ),
            activity=_activity_from_contract_result(request, decision, command_result)
            if command_result.activity is not None
            else None,
            activity_kind="task_created" if accepted else "recovery_note",
            publish_activity=not accepted,
        )

    def _publish_wechat_send_execution_task(
        self,
        request: RuntimeInputRouteRequest,
        resolution: WeChatSendResolution,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        assert self.execution_plane_service is not None
        decision = self._decision(
            request,
            intent="execution_request",
            dispatch_target="execution_handoff",
            side_effect="execution_request",
            explanation=(
                "Input published a bounded, confirmation-gated WeChat send task "
                "through Execution Plane."
            ),
            related_refs=_selection_refs(request),
        )
        try:
            execution = self.execution_plane_service.publish_task(
                wechat_send_task_request(
                    resolution,
                    command_id=request.command_id,
                    session_id=request.session_id,
                    workspace_id=request.workspace_id,
                    original_content=request.content,
                )
            )
        except ExecutionPlaneError as exc:
            outcome = RuntimeInputOutcome(
                status="rejected",
                user_message=_wechat_publish_error_user_message(exc),
                recovery_actions=_wechat_publish_error_recovery_actions(exc),
            )
            return self._result(
                request,
                decision,
                outcome,
                activity=self._activity(
                    request,
                    decision,
                    outcome,
                    activity_kind="recovery_note",
                ),
                publish_activity=True,
            )

        task_error = _wechat_execution_error(self.execution_plane_service, execution)
        outcome = RuntimeInputOutcome(
            status="rejected" if execution.status == "failed" else "dispatched",
            user_message=_wechat_execution_user_message(execution, task_error),
            recovery_actions=_wechat_execution_recovery_actions(task_error),
        )
        return self._result(
            request,
            decision,
            outcome,
            activity=_wechat_execution_activity(
                request,
                decision,
                execution,
                outcome,
                activity_kind=(
                    "recovery_note" if execution.status == "failed" else "task_created"
                ),
                title=(
                    "WeChat send task failed"
                    if execution.status == "failed"
                    else "WeChat send task created"
                ),
            ),
        )

    def _active_ask(self, request: RuntimeInputRouteRequest) -> AskRequestView | None:
        ask_id = request.client_state.active_ask_id
        if ask_id is not None:
            detail_response = self.query_gateway.get_ask(request.session_id, ask_id)
            if (
                detail_response.ok
                and detail_response.data is not None
                and detail_response.data.status == "pending"
            ):
                return detail_response.data
            return None

        list_response = self.query_gateway.list_asks(
            request.session_id,
            status="pending",
            task_node_id=request.selection.task_node_id,
        )
        if not list_response.ok or list_response.data is None:
            return None
        if list_response.data.active_ask is not None:
            return list_response.data.active_ask
        if len(list_response.data.asks) == 1:
            return list_response.data.asks[0]
        return None

    def _active_confirmation(
        self,
        request: RuntimeInputRouteRequest,
    ) -> ConfirmationActionView | None:
        response = self.query_gateway.get_session_snapshot(request.session_id)
        if not response.ok or response.data is None:
            return None
        pending = [
            confirmation
            for confirmation in response.data.pending_confirmations
            if confirmation.status == "pending"
        ]
        confirmation_id = request.client_state.active_confirmation_id
        if confirmation_id is not None:
            for confirmation in pending:
                if confirmation.id == confirmation_id:
                    return confirmation
            return None
        task_node_id = request.selection.task_node_id
        if task_node_id is not None:
            task_pending = [
                confirmation
                for confirmation in pending
                if confirmation.task_node_id == task_node_id
            ]
            if len(task_pending) == 1:
                return task_pending[0]
        if len(pending) == 1:
            return pending[0]
        return None

    def _answer_ask(
        self,
        request: RuntimeInputRouteRequest,
        ask: AskRequestView,
        *,
        answer_text: str | None = None,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        text = answer_text or request.content
        decision = self._decision(
            request,
            intent="ask_answer",
            dispatch_target="resolve_ask",
            side_effect="resume_effect",
            explanation="Input answered the active ASK.",
            related_refs=(_ref("ask", ask.id, "Active ASK"),),
        )
        if self.contract_revision_service is not None:
            command_result = self.contract_revision_service.execute(
                ContractCommandRequest(
                    command_id=request.command_id,
                    idempotency_key=request.command_id,
                    command_kind="resolve_ask",
                    workspace_id=request.workspace_id or "current",
                    session_id=request.session_id,
                    scope_kind="ask",
                    ask_id=ask.id,
                    source="runtime_input",
                    router_decision_id=decision.id,
                    payload={"text": text},
                )
            )
            accepted = command_result.status in {"accepted", "noop"}
            return self._result(
                request,
                decision,
                RuntimeInputOutcome(
                    status="dispatched" if accepted else "rejected",
                    user_message=(
                        "The active ASK answer was recorded."
                        if accepted
                        else "The active ASK answer was rejected by the command handler."
                    ),
                    recovery_actions=() if accepted else ("answer_ask",),
                ),
                command_response=command_result.command_response,
                activity=_activity_from_contract_result(
                    request,
                    decision,
                    command_result,
                )
                if command_result.activity is not None
                else None,
                activity_kind="ask_answered" if accepted else "recovery_note",
                publish_activity=not accepted,
            )

        command_response = _answer_ask_with_resume_dispatch(
            self.command_gateway,
            self.execution_trigger_gateway,
            ask.id,
            CommandRequest[AnswerAskPayload](
                command_id=request.command_id,
                session_id=request.session_id,
                payload=AnswerAskPayload(text=text),
            ),
        )
        accepted = command_response.ok and command_response.result is not None
        return self._result(
            request,
            decision,
            RuntimeInputOutcome(
                status="dispatched" if accepted else "rejected",
                user_message=(
                    "The active ASK answer was recorded."
                    if accepted
                    else "The active ASK answer was rejected by the command handler."
                ),
                recovery_actions=() if accepted else ("answer_ask",),
            ),
            command_response=command_response,
            activity_kind="ask_answered" if accepted else "recovery_note",
        )

    def _resolve_confirmation(
        self,
        request: RuntimeInputRouteRequest,
        confirmation: ConfirmationActionView,
        value: str,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        decision = self._decision(
            request,
            intent="confirmation_response",
            dispatch_target="resolve_confirmation",
            side_effect="authorization_effect",
            explanation="Input resolved the active confirmation.",
            related_refs=(_ref("confirmation", confirmation.id, "Active confirmation"),),
        )
        if self.contract_revision_service is not None:
            command_result = self.contract_revision_service.execute(
                ContractCommandRequest(
                    command_id=request.command_id,
                    idempotency_key=request.command_id,
                    command_kind="resolve_confirmation",
                    workspace_id=request.workspace_id or "current",
                    session_id=request.session_id,
                    scope_kind="confirmation",
                    confirmation_id=confirmation.id,
                    source="runtime_input",
                    router_decision_id=decision.id,
                    payload={"value": value, "note": request.content},
                )
            )
            accepted = command_result.status in {"accepted", "noop"}
            return self._result(
                request,
                decision,
                RuntimeInputOutcome(
                    status="dispatched" if accepted else "rejected",
                    user_message=(
                        "The active confirmation response was recorded."
                        if accepted
                        else "The active confirmation response was rejected."
                    ),
                    recovery_actions=() if accepted else ("retry_command",),
                ),
                command_response=command_result.command_response,
                activity=_activity_from_contract_result(
                    request,
                    decision,
                    command_result,
                )
                if command_result.activity is not None
                else None,
                activity_kind="confirmation_resolved" if accepted else "recovery_note",
                publish_activity=not accepted,
            )

        command_response = self.command_gateway.resolve_confirmation(
            confirmation.id,
            CommandRequest[ResolveConfirmationPayload](
                command_id=request.command_id,
                session_id=request.session_id,
                payload=ResolveConfirmationPayload(value=value, note=request.content),
            ),
        )
        accepted = command_response.ok and command_response.result is not None
        return self._result(
            request,
            decision,
            RuntimeInputOutcome(
                status="dispatched" if accepted else "rejected",
                user_message=(
                    "The active confirmation response was recorded."
                    if accepted
                    else "The active confirmation response was rejected."
                ),
                recovery_actions=() if accepted else ("retry_command",),
            ),
            command_response=command_response,
            activity_kind="confirmation_resolved" if accepted else "recovery_note",
        )

    def _stop_selected_task(
        self,
        request: RuntimeInputRouteRequest,
        *,
        planner_proposal: RuntimeInputRouteProposal | None = None,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        task_node_id = request.selection.task_node_id
        if request.selection.scope_kind != "task" or task_node_id is None:
            return self._task_command_needs_scope(request, action="stop")
        command_response = self.command_gateway.stop_task(
            task_node_id,
            CommandRequest[StopTaskPayload](
                command_id=request.command_id,
                session_id=request.session_id,
                payload=StopTaskPayload(reason=request.content),
            ),
        )
        accepted = command_response.ok and command_response.result is not None
        decision = self._decision(
            request,
            intent="command",
            dispatch_target="existing_command",
            side_effect="state_effect",
            explanation=(
                planner_proposal.visible_reasoning_summary
                if planner_proposal is not None
                else "Input routed to stop-task command."
            ),
            confidence=(
                planner_proposal.confidence if planner_proposal is not None else "high"
            ),
            related_refs=(_ref("task", task_node_id, "Selected task"),),
        )
        return self._result(
            request,
            decision,
            RuntimeInputOutcome(
                status="dispatched" if accepted else "rejected",
                user_message=(
                    "The selected task stop command was dispatched."
                    if accepted
                    else "The selected task stop command was rejected."
                ),
                recovery_actions=() if accepted else ("retry_command",),
            ),
            command_response=command_response,
        )

    def _retry_selected_task(
        self,
        request: RuntimeInputRouteRequest,
        *,
        planner_proposal: RuntimeInputRouteProposal | None = None,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        task_node_id = request.selection.task_node_id
        if request.selection.scope_kind != "task" or task_node_id is None:
            return self._task_command_needs_scope(request, action="retry")
        command_response = _retry_task_with_optional_dispatch(
            self.command_gateway,
            self.execution_trigger_gateway,
            task_node_id,
            CommandRequest[RetryTaskPayload](
                command_id=request.command_id,
                session_id=request.session_id,
                payload=RetryTaskPayload(
                    instruction=request.content,
                    start_immediately=True,
                ),
            ),
        )
        accepted = command_response.ok and command_response.result is not None
        decision = self._decision(
            request,
            intent="command",
            dispatch_target="existing_command",
            side_effect="state_effect",
            explanation=(
                planner_proposal.visible_reasoning_summary
                if planner_proposal is not None
                else "Input routed to retry-task command."
            ),
            confidence=(
                planner_proposal.confidence if planner_proposal is not None else "high"
            ),
            related_refs=(_ref("task", task_node_id, "Selected task"),),
        )
        return self._result(
            request,
            decision,
            RuntimeInputOutcome(
                status="dispatched" if accepted else "rejected",
                user_message=(
                    "The selected task retry command was dispatched."
                    if accepted
                    else "The selected task retry command was rejected."
                ),
                recovery_actions=() if accepted else ("retry_command",),
            ),
            command_response=command_response,
        )

    def _task_command_needs_scope(
        self,
        request: RuntimeInputRouteRequest,
        *,
        action: str,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        decision = self._decision(
            request,
            intent="clarification",
            dispatch_target="clarification",
            side_effect="no_effect",
            explanation=f"Planner-routed {action} command requires a selected task.",
        )
        return self._result(
            request,
            decision,
            RuntimeInputOutcome(
                status="needs_clarification",
                user_message=(
                    f"Select a task before asking Plato to {action} it. "
                    "No product or workspace state changed."
                ),
            ),
        )

    def _answer_read_only_inquiry(
        self,
        request: RuntimeInputRouteRequest,
        *,
        planner_proposal: RuntimeInputRouteProposal | None = None,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        inquiry_service = self.read_only_inquiry_service or DefaultReadOnlyInquiryService(
            self.query_gateway,
            workspace_inspection_gateway=self.workspace_inspection_gateway,
            diagnostic_support_provider=self.diagnostic_support_provider,
        )
        inquiry_response = inquiry_service.answer(
            ReadOnlyInquiryRequest(
                inquiry_id=request.command_id,
                session_id=request.session_id,
                workspace_id=request.workspace_id,
                question=request.content,
                scope=ReadOnlyInquiryScope(
                    kind=request.selection.scope_kind,
                    plan_id=request.selection.plan_id,
                    task_node_id=request.selection.task_node_id,
                ),
                refs=_merge_inquiry_refs(
                    request.inquiry_refs,
                    () if planner_proposal is None else planner_proposal.read_only_refs,
                    _inquiry_refs(request),
                ),
            )
        )
        if not inquiry_response.ok or inquiry_response.data is None:
            return self._unsupported(
                request,
                intent="question",
                dispatch_target="read_only_inquiry",
                side_effect="no_effect",
                explanation="Read-Only Inquiry Context could not answer the question.",
                user_message=(
                    "Answer-only workspace inquiry is not available. "
                    "No product or workspace state changed."
                ),
            )

        inquiry_result = inquiry_response.data
        explanation = (
            planner_proposal.visible_reasoning_summary
            if planner_proposal is not None
            else "Input was answered through Read-Only Inquiry Context."
        )
        decision = self._decision(
            request,
            intent="question",
            dispatch_target="read_only_inquiry",
            side_effect="no_effect",
            explanation=explanation,
            confidence=(
                inquiry_result.answer.confidence if inquiry_result.answer is not None else "low"
            ),
            related_refs=(
                inquiry_result.activity.related_refs
                if inquiry_result.activity is not None
                else _selection_refs(request)
            ),
        )
        user_message = (
            inquiry_result.answer.body
            if inquiry_result.answer is not None
            else _inquiry_fallback_message(inquiry_result)
        )
        activity = inquiry_result.activity or self._activity(
            request,
            decision,
            RuntimeInputOutcome(
                status=_runtime_outcome_status(inquiry_result.status),
                user_message=user_message,
            ),
            activity_kind=(
                "answer" if inquiry_result.status == "answered" else "router_interpretation"
            ),
        )
        return self._result(
            request,
            decision,
            RuntimeInputOutcome(
                status=_runtime_outcome_status(inquiry_result.status),
                user_message=user_message,
                recovery_actions=() if inquiry_result.status == "answered" else ("edit_input",),
            ),
            activity=activity,
            inquiry_result=inquiry_result,
        )

    def _route_planner_result(
        self,
        request: RuntimeInputRouteRequest,
        *,
        active_ask: AskRequestView | None,
        active_confirmation: ConfirmationActionView | None,
    ) -> QueryResponse[RuntimeInputRouteResult] | None:
        return route_planner_result(
            request,
            self.route_planner,
            active_ask=active_ask is not None,
            active_confirmation=active_confirmation is not None,
            handlers=self._planner_dispatch_handlers(
                active_ask=active_ask,
                active_confirmation=active_confirmation,
            ),
        )

    def _planner_dispatch_handlers(
        self,
        *,
        active_ask: AskRequestView | None,
        active_confirmation: ConfirmationActionView | None,
    ) -> PlannerDispatchHandlers:
        return PlannerDispatchHandlers(
            answer_read_only_inquiry=(
                lambda request, proposal: self._answer_read_only_inquiry(
                    request,
                    planner_proposal=proposal,
                )
            ),
            record_guidance=self._record_guidance,
            create_execution_task=self._create_execution_task,
            create_wechat_send_execution_task=self._create_wechat_send_execution_task,
            stop_selected_task=(
                lambda request, proposal: self._stop_selected_task(
                    request,
                    planner_proposal=proposal,
                )
            ),
            retry_selected_task=(
                lambda request, proposal: self._retry_selected_task(
                    request,
                    planner_proposal=proposal,
                )
            ),
            resolve_ask=(
                lambda request, proposal: self._planner_resolve_ask(
                    request,
                    proposal,
                    active_ask=active_ask,
                )
            ),
            resolve_confirmation=(
                lambda request, proposal: self._planner_resolve_confirmation(
                    request,
                    proposal,
                    active_confirmation=active_confirmation,
                )
            ),
            planner_clarification=self._planner_clarification,
            unsupported=self._unsupported,
        )

    def _planner_resolve_ask(
        self,
        request: RuntimeInputRouteRequest,
        proposal: RuntimeInputRouteProposal,
        *,
        active_ask: AskRequestView | None,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        if active_ask is None:
            return self._unsupported(
                request,
                intent=proposal.intent,
                dispatch_target="unsupported",
                side_effect="no_effect",
                explanation="Planner proposed ASK resolution but no active ASK exists.",
                user_message=(
                    "There is no active ASK to answer. "
                    "No product or workspace state changed."
                ),
            )
        draft = proposal.ask_answer_draft
        if draft is None:
            return self._unsupported(
                request,
                intent=proposal.intent,
                dispatch_target="unsupported",
                side_effect="no_effect",
                explanation="Planner resolve_ask proposal did not include answer draft.",
                user_message=(
                    "The Router could not validate that ASK answer. "
                    "No product or workspace state changed."
                ),
            )
        if draft.ask_id is not None and draft.ask_id != active_ask.id:
            return self._unsupported(
                request,
                intent=proposal.intent,
                dispatch_target="unsupported",
                side_effect="no_effect",
                explanation="Planner ASK answer draft targeted a non-active ASK.",
                user_message=(
                    "That ASK is no longer active. "
                    "No product or workspace state changed."
                ),
            )
        return self._answer_ask(request, active_ask, answer_text=draft.answer_text)

    def _planner_resolve_confirmation(
        self,
        request: RuntimeInputRouteRequest,
        proposal: RuntimeInputRouteProposal,
        *,
        active_confirmation: ConfirmationActionView | None,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        if active_confirmation is None:
            return self._unsupported(
                request,
                intent=proposal.intent,
                dispatch_target="unsupported",
                side_effect="no_effect",
                explanation=(
                    "Planner proposed confirmation resolution but no active "
                    "confirmation exists."
                ),
                user_message=(
                    "There is no active confirmation to resolve. "
                    "No product or workspace state changed."
                ),
            )
        draft = proposal.confirmation_response_draft
        if draft is None:
            return self._unsupported(
                request,
                intent=proposal.intent,
                dispatch_target="unsupported",
                side_effect="no_effect",
                explanation=(
                    "Planner resolve_confirmation proposal did not include "
                    "confirmation response draft."
                ),
                user_message=(
                    "The Router could not validate that confirmation response. "
                    "No product or workspace state changed."
                ),
            )
        if (
            draft.confirmation_id is not None
            and draft.confirmation_id != active_confirmation.id
        ):
            return self._unsupported(
                request,
                intent=proposal.intent,
                dispatch_target="unsupported",
                side_effect="no_effect",
                explanation=(
                    "Planner confirmation response draft targeted a non-active "
                    "confirmation."
                ),
                user_message=(
                    "That confirmation is no longer active. "
                    "No product or workspace state changed."
                ),
            )
        return self._resolve_confirmation(
            request,
            active_confirmation,
            draft.resolution,
        )

    def _planner_clarification(
        self,
        request: RuntimeInputRouteRequest,
        proposal: RuntimeInputRouteProposal,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        decision = self._decision(
            request,
            intent="clarification",
            dispatch_target="clarification",
            side_effect="no_effect",
            explanation=proposal.visible_reasoning_summary,
            confidence=proposal.confidence,
        )
        return self._result(
            request,
            decision,
            RuntimeInputOutcome(
                status="needs_clarification",
                user_message=proposal.user_message,
                recovery_actions=("edit_input",),
            ),
        )

    def _unsupported(
        self,
        request: RuntimeInputRouteRequest,
        *,
        intent: RuntimeInputIntent,
        dispatch_target: RuntimeInputDispatchTarget,
        side_effect: SessionActivitySideEffect,
        explanation: str,
        user_message: str,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        decision = self._decision(
            request,
            intent=intent,
            dispatch_target=dispatch_target,
            side_effect=side_effect,
            explanation=explanation,
            confidence="low" if intent in {"unsupported", "question"} else "medium",
        )
        return self._result(
            request,
            decision,
            RuntimeInputOutcome(
                status="unsupported",
                user_message=user_message,
                recovery_actions=("edit_input",),
            ),
        )

    def _decision(
        self,
        request: RuntimeInputRouteRequest,
        *,
        intent: RuntimeInputIntent,
        dispatch_target: RuntimeInputDispatchTarget,
        side_effect: SessionActivitySideEffect,
        explanation: str,
        confidence: RuntimeInputConfidence = "high",
        related_refs: tuple[SessionActivityRefView, ...] = (),
    ) -> RuntimeInputRouteDecision:
        return RuntimeInputRouteDecision(
            intent=intent,
            scope=RuntimeInputDecisionScope(
                kind=request.selection.scope_kind,
                plan_id=request.selection.plan_id,
                task_node_id=request.selection.task_node_id,
            ),
            confidence=confidence,
            side_effect=side_effect,
            dispatch_target=dispatch_target,
            explanation=explanation,
            related_refs=related_refs or _selection_refs(request),
        )

    def _result(
        self,
        request: RuntimeInputRouteRequest,
        decision: RuntimeInputRouteDecision,
        outcome: RuntimeInputOutcome,
        *,
        command_response: CommandResponse | None = None,
        inquiry_result: ReadOnlyInquiryResult | None = None,
        activity: SessionActivityItemView | None = None,
        activity_kind: SessionActivityItemKind = "router_interpretation",
        publish_activity: bool = True,
        publish_conversation: bool = True,
    ) -> QueryResponse[RuntimeInputRouteResult]:
        projected_activity = activity or self._activity(
            request,
            decision,
            outcome,
            activity_kind=activity_kind,
        )
        self._publish_runtime_conversation(
            request,
            decision,
            outcome,
            enabled=publish_conversation,
        )
        self._publish_runtime_activity(
            request,
            projected_activity,
            outcome,
            enabled=publish_activity,
        )
        log_runtime_input_router_dispatch(
            request,
            decision,
            outcome,
            command_response=command_response,
            inquiry_result=inquiry_result,
        )
        return QueryResponse[RuntimeInputRouteResult](
            request_id=request.command_id,
            ok=True,
            data=RuntimeInputRouteResult(
                session_id=request.session_id,
                decision=decision,
                outcome=outcome,
                activity=projected_activity,
                command_response=command_response,
                inquiry_result=inquiry_result,
            ),
        )

    def _publish_runtime_conversation(
        self,
        request: RuntimeInputRouteRequest,
        decision: RuntimeInputRouteDecision,
        outcome: RuntimeInputOutcome,
        *,
        enabled: bool,
    ) -> None:
        if not enabled or self.activity_publisher is None:
            return
        publish = getattr(
            self.activity_publisher,
            "publish_router_conversation",
            None,
        )
        if callable(publish):
            publish(request, decision, outcome)

    def _publish_runtime_activity(
        self,
        request: RuntimeInputRouteRequest,
        activity: SessionActivityItemView,
        outcome: RuntimeInputOutcome,
        *,
        enabled: bool,
    ) -> None:
        if not enabled or self.activity_publisher is None:
            return
        publish = getattr(self.activity_publisher, "publish_router_activity", None)
        if callable(publish):
            publish(request, activity, outcome_status=outcome.status)

    def _activity(
        self,
        request: RuntimeInputRouteRequest,
        decision: RuntimeInputRouteDecision,
        outcome: RuntimeInputOutcome,
        *,
        activity_kind: SessionActivityItemKind = "router_interpretation",
    ) -> SessionActivityItemView:
        return SessionActivityItemView(
            id=f"activity:{decision.id}",
            session_id=request.session_id,
            kind=activity_kind,
            title=_activity_title(decision),
            body=outcome.user_message,
            scope_kind=decision.scope.kind,
            plan_id=decision.scope.plan_id,
            task_node_id=decision.scope.task_node_id,
            side_effect=decision.side_effect,
            related_refs=decision.related_refs,
            source_kind="router",
            source_id=decision.id,
            disclosure_level="public",
        )


def _runtime_outcome_status(status: ReadOnlyInquiryStatus) -> RuntimeInputOutcomeStatus:
    if status == "answered":
        return "answered"
    if status == "needs_clarification":
        return "needs_clarification"
    if status == "rejected":
        return "rejected"
    return "unsupported"


def _inquiry_fallback_message(inquiry_result: ReadOnlyInquiryResult) -> str:
    if inquiry_result.warnings:
        return inquiry_result.warnings[0].message
    if inquiry_result.status == "needs_clarification":
        return "Read-only inquiry needs clarification. No product or workspace state changed."
    if inquiry_result.status == "rejected":
        return "Read-only inquiry was rejected. No product or workspace state changed."
    return "Read-only inquiry is unsupported for this input. No product or workspace state changed."


def _selection_refs(
    request: RuntimeInputRouteRequest,
) -> tuple[SessionActivityRefView, ...]:
    refs: list[SessionActivityRefView] = [_ref("session", request.session_id, "Session")]
    if request.selection.plan_id is not None:
        refs.append(_ref("plan", request.selection.plan_id, "Plan"))
    if request.selection.task_node_id is not None:
        refs.append(_ref("task", request.selection.task_node_id, "Task"))
    return tuple(refs)


def _inquiry_refs(
    request: RuntimeInputRouteRequest,
) -> tuple[ReadOnlyInquiryRef, ...]:
    kind_by_object: dict[str, ReadOnlyInquiryRefKind] = {
        "plan": "plan",
        "draft_task": "task",
        "draft_tree": "plan",
        "draft_subtree": "task",
        "published_task": "task",
        "message": "activity",
    }
    refs: list[ReadOnlyInquiryRef] = []
    for ref in request.selection.refs:
        kind = kind_by_object.get(ref.kind)
        if kind is None:
            continue
        refs.append(
            ReadOnlyInquiryRef(
                kind=kind,
                id=ref.id,
                label=ref.kind.replace("_", " "),
            )
        )
    return tuple(refs)


def _merge_inquiry_refs(
    *groups: tuple[ReadOnlyInquiryRef, ...],
) -> tuple[ReadOnlyInquiryRef, ...]:
    seen: set[tuple[str, str | None, str | None, str | None]] = set()
    refs: list[ReadOnlyInquiryRef] = []
    for group in groups:
        for ref in group:
            key = (ref.kind, ref.id, ref.path, ref.evidence_id)
            if key in seen:
                continue
            seen.add(key)
            refs.append(ref)
    return tuple(refs)


def _ref(kind: SessionActivityRefKind, ref_id: str, label: str) -> SessionActivityRefView:
    return SessionActivityRefView(
        kind=kind,
        id=ref_id,
        label=label,
    )


def _activity_from_contract_result(
    request: RuntimeInputRouteRequest,
    decision: RuntimeInputRouteDecision,
    command_result: ContractCommandResult,
) -> SessionActivityItemView:
    assert command_result.activity is not None
    return SessionActivityItemView(
        id=f"activity:{decision.id}",
        session_id=request.session_id,
        kind=_contract_activity_kind(command_result),
        title=command_result.activity.title,
        body=command_result.activity.body,
        scope_kind=decision.scope.kind,
        plan_id=decision.scope.plan_id,
        task_node_id=decision.scope.task_node_id,
        side_effect=command_result.side_effect,
        related_refs=command_result.activity.related_refs,
        source_kind="router",
        source_id=decision.id,
        disclosure_level=command_result.activity.disclosure_level,
    )


def _wechat_execution_activity(
    request: RuntimeInputRouteRequest,
    decision: RuntimeInputRouteDecision,
    execution: TaskExecution,
    outcome: RuntimeInputOutcome,
    *,
    activity_kind: SessionActivityItemKind = "task_created",
    title: str = "WeChat send task created",
) -> SessionActivityItemView:
    return SessionActivityItemView(
        id=f"activity:{decision.id}",
        session_id=request.session_id,
        kind=activity_kind,
        title=title,
        body=outcome.user_message,
        scope_kind=decision.scope.kind,
        plan_id=decision.scope.plan_id,
        task_node_id=decision.scope.task_node_id,
        side_effect=decision.side_effect,
        related_refs=decision.related_refs
        + (_ref("task", execution.task_id, "Execution Plane task"),),
        source_kind="router",
        source_id=decision.id,
        disclosure_level="public",
    )


def _wechat_execution_user_message(
    execution: TaskExecution,
    error: TaskError | None = None,
) -> str:
    if execution.status == "waiting_for_user":
        return "微信发送任务已创建，正在等待用户确认。"
    if execution.status == "failed":
        if error is None:
            return "微信发送任务失败。没有发送消息。请查看错误和证据。"
        lines = [
            "微信发送任务失败。没有发送消息。",
            f"错误代码：{error.code}",
            f"错误信息：{error.message}",
        ]
        if error.recovery_hint is not None:
            lines.append(f"恢复建议：{error.recovery_hint}")
        return "\n".join(lines)
    if execution.status == "done":
        return "微信发送任务已完成。"
    return "微信发送任务已创建；真正发送前仍需要用户确认。"


def _wechat_publish_error_user_message(error: ExecutionPlaneError) -> str:
    summary = (
        "当前执行环境不支持微信发送能力。没有发送消息。"
        if error.code == "capability_not_available"
        else "微信发送任务未能创建。没有发送消息。"
    )
    lines = [
        summary,
        f"错误代码：{error.code}",
        f"错误信息：{error.message}",
    ]
    recovery_hint = error.details.get("recoveryHint") or error.details.get(
        "recovery_hint"
    )
    if isinstance(recovery_hint, str) and recovery_hint:
        lines.append(f"恢复建议：{recovery_hint}")
    return "\n".join(lines)


def _wechat_publish_error_recovery_actions(
    error: ExecutionPlaneError,
) -> tuple[ProductRecoveryAction, ...]:
    detail_actions = _product_recovery_actions_from_details(error.details)
    if detail_actions:
        return detail_actions
    if error.retryable and error.code == "capability_not_available":
        return ("open_settings", "retry_command")
    if error.retryable:
        return ("retry_command",)
    return ("edit_input",)


def _product_recovery_actions_from_details(
    details: dict[str, Any],
) -> tuple[ProductRecoveryAction, ...]:
    raw_actions = details.get("recoveryActions")
    if raw_actions is None:
        raw_actions = details.get("recovery_actions")

    if isinstance(raw_actions, str):
        candidates = [action.strip() for action in raw_actions.split(",")]
    elif isinstance(raw_actions, (list, tuple)):
        candidates = [action for action in raw_actions if isinstance(action, str)]
    else:
        return ()

    actions: list[ProductRecoveryAction] = []
    for candidate in candidates:
        if candidate not in _VALID_PRODUCT_RECOVERY_ACTIONS:
            continue
        action = cast(ProductRecoveryAction, candidate)
        if action in actions:
            continue
        actions.append(action)

    if len(actions) > 1 and "none" in actions:
        actions = [action for action in actions if action != "none"]
    return tuple(actions)


def _wechat_execution_recovery_actions(
    error: TaskError | None,
) -> tuple[ProductRecoveryAction, ...]:
    if error is None:
        return ("open_audit",)
    if error.retryable:
        return ("open_settings", "retry_command")
    return ("open_audit",)


def _wechat_execution_error(
    service: TaskApiService | None,
    execution: TaskExecution,
) -> TaskError | None:
    if execution.status != "failed" or execution.error_ref is None or service is None:
        return None
    try:
        return service.get_error(execution.error_ref)
    except ExecutionPlaneError:
        return None


def _contract_activity_kind(
    command_result: ContractCommandResult,
) -> SessionActivityItemKind:
    if command_result.status not in {"accepted", "noop"}:
        return "recovery_note"
    if command_result.command_kind == "record_guidance":
        return "guidance_recorded"
    if command_result.command_kind == "resolve_ask":
        return "ask_answered"
    if command_result.command_kind == "resolve_confirmation":
        return "confirmation_resolved"
    if command_result.command_kind == "create_task_node":
        return "task_created"
    if command_result.command_kind == "delete_task_node":
        return "task_removed"
    if command_result.command_kind == "patch_task_node":
        return "task_changed"
    if command_result.command_kind == "create_execution_task":
        return "task_created"
    return "router_interpretation"


def _activity_title(decision: RuntimeInputRouteDecision) -> str:
    if decision.intent == "ask_answer":
        return "ASK answered"
    if decision.intent == "confirmation_response":
        return "Confirmation resolved"
    if decision.intent == "command":
        return "Runtime command routed"
    if decision.intent == "clarification":
        return "Runtime input needs clarification"
    if decision.intent == "question":
        return "Read-only question answered"
    if decision.intent == "guidance":
        return "Guidance recorded"
    return "Runtime input routed"


__all__ = ["DefaultRuntimeInputRouter", "RuntimeInputRouter"]
