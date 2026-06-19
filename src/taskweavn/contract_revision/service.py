"""Contract Revision command service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from taskweavn.contract_revision.activity import ContractRevisionActivityPublisher
from taskweavn.contract_revision.guidance_store import GuidanceFactStore
from taskweavn.contract_revision.idempotency_store import ContractCommandIdempotencyStore
from taskweavn.contract_revision.interaction_commands import (
    ContractInteractionCommandHandler,
    ContractInteractionCommandOutcome,
)
from taskweavn.contract_revision.models import (
    ContractCommandActivityDescriptor,
    ContractCommandAuditDescriptor,
    ContractCommandDiagnosticDescriptor,
    ContractCommandRequest,
    ContractCommandResult,
    ContractCommandStatus,
    CreateExecutionTaskPayload,
    CreateTaskNodePayload,
    DeleteTaskNodePayload,
    GuidanceFact,
    PatchTaskNodePayload,
    RecordGuidancePayload,
    ResolveAskPayload,
    ResolveConfirmationContractPayload,
)
from taskweavn.contract_revision.tasknode_commands import (
    ContractTaskNodeCommandHandler,
    ContractTaskNodeCommandOutcome,
)
from taskweavn.server.ui_contract.envelopes import CommandResponse
from taskweavn.server.ui_contract.refs import ObjectRef
from taskweavn.server.ui_contract.view_models import (
    SessionActivityRefView,
    SessionActivitySideEffect,
)
from taskweavn.task.plan_stores import PlanStore

_GUIDANCE_PREVIEW_LIMIT = 160
_CONFIRMATION_SIDE_EFFECT: SessionActivitySideEffect = "authorization_effect"


@dataclass(frozen=True)
class ContractRevisionCommandService:
    """Executes command-backed Contract Revision operations."""

    idempotency_store: ContractCommandIdempotencyStore
    guidance_store: GuidanceFactStore
    workspace_id: str
    plan_store: PlanStore | None = None
    interaction_handler: ContractInteractionCommandHandler | None = None
    task_node_handler: ContractTaskNodeCommandHandler | None = None
    activity_publisher: ContractRevisionActivityPublisher | None = None

    def execute(self, request: ContractCommandRequest) -> ContractCommandResult:
        request_hash = _hash_request(request)
        cached = self.idempotency_store.get(
            request.session_id,
            request.idempotency_key,
        )
        if cached is not None:
            if cached.request_hash != request_hash:
                return _result(
                    request,
                    status="conflict",
                    side_effect="no_effect",
                    reason_code="idempotency_conflict",
                    message_key="contractRevision.idempotencyConflict",
                    diagnostics=_diagnostics(
                        request,
                        status="conflict",
                        side_effect="no_effect",
                        reason_code="idempotency_conflict",
                    ),
                )
            if cached.result is not None:
                return cached.result
            return _result(
                request,
                status="conflict",
                side_effect="no_effect",
                reason_code="incomplete_idempotent_command",
                message_key="contractRevision.incompleteReplay",
            )

        if request.command_kind == "record_guidance":
            result = self._record_guidance(request)
        elif request.command_kind == "resolve_ask":
            result = self._resolve_ask(request)
        elif request.command_kind == "resolve_confirmation":
            result = self._resolve_confirmation(request)
        elif request.command_kind == "patch_task_node":
            result = self._patch_task_node(request)
        elif request.command_kind == "create_task_node":
            result = self._create_task_node(request)
        elif request.command_kind == "delete_task_node":
            result = self._delete_task_node(request)
        elif request.command_kind == "create_execution_task":
            result = self._create_execution_task(request)
        else:
            result = _result(
                request,
                status="unsupported",
                side_effect="no_effect",
                reason_code="unsupported_command",
                message_key="contractRevision.unsupportedCommand",
                diagnostics=_diagnostics(
                    request,
                    status="unsupported",
                    side_effect="no_effect",
                    reason_code="unsupported_command",
                ),
            )
        self.idempotency_store.put_completed(
            request,
            request_hash=request_hash,
            result=result,
        )
        if self.activity_publisher is not None:
            self.activity_publisher.publish_command_activity(result)
        return result

    def _resolve_ask(self, request: ContractCommandRequest) -> ContractCommandResult:
        if self.interaction_handler is None:
            return _unsupported_interaction_result(request)
        try:
            payload = ResolveAskPayload.model_validate(request.payload)
        except ValidationError:
            return _invalid_interaction_payload_result(
                request,
                message_key="contractRevision.invalidAskResolutionPayload",
            )
        outcome = self.interaction_handler.resolve_ask(request, payload)
        return self._interaction_result(
            request,
            outcome,
            accepted_side_effect="resume_effect",
            accepted_title="ASK answered",
            target_ref=ObjectRef(kind="message", id=request.ask_id)
            if request.ask_id is not None
            else None,
            refs=_interaction_refs("ask", request.ask_id, "ASK"),
            message_key="contractRevision.askResolved",
        )

    def _resolve_confirmation(
        self,
        request: ContractCommandRequest,
    ) -> ContractCommandResult:
        if self.interaction_handler is None:
            return _unsupported_interaction_result(request)
        try:
            payload = ResolveConfirmationContractPayload.model_validate(
                request.payload
            )
        except ValidationError:
            return _invalid_interaction_payload_result(
                request,
                message_key="contractRevision.invalidConfirmationPayload",
            )
        outcome = self.interaction_handler.resolve_confirmation(request, payload)
        return self._interaction_result(
            request,
            outcome,
            accepted_side_effect=_CONFIRMATION_SIDE_EFFECT,
            accepted_title="Confirmation resolved",
            target_ref=ObjectRef(kind="message", id=request.confirmation_id)
            if request.confirmation_id is not None
            else None,
            refs=_interaction_refs(
                "confirmation",
                request.confirmation_id,
                "Confirmation",
            ),
            message_key="contractRevision.confirmationResolved",
        )

    def _interaction_result(
        self,
        request: ContractCommandRequest,
        outcome: ContractInteractionCommandOutcome,
        *,
        accepted_side_effect: SessionActivitySideEffect,
        accepted_title: str,
        target_ref: ObjectRef | None,
        refs: tuple[SessionActivityRefView, ...],
        message_key: str,
    ) -> ContractCommandResult:
        if not outcome.accepted:
            reason_code = outcome.reason_code or "command_rejected"
            return _result(
                request,
                status="rejected",
                side_effect="no_effect",
                refs=refs,
                reason_code=reason_code,
                message_key="contractRevision.interactionRejected",
                diagnostics=_diagnostics(
                    request,
                    status="rejected",
                    side_effect="no_effect",
                    reason_code=reason_code,
                ),
                command_response=outcome.command_response,
            )

        activity = ContractCommandActivityDescriptor(
            title=accepted_title,
            body=outcome.message,
            related_refs=refs,
        )
        audit = ContractCommandAuditDescriptor(
            command_id=request.command_id,
            command_kind=request.command_kind,
            status="accepted",
            side_effect=accepted_side_effect,
            scope_kind=request.scope_kind,
            session_id=request.session_id,
            plan_id=request.plan_id,
            task_node_id=request.task_node_id,
            target_ref=target_ref,
            summary=f"{accepted_title} through Contract Revision command.",
        )
        return _result(
            request,
            status="accepted",
            side_effect=accepted_side_effect,
            refs=refs,
            activity=activity,
            audit=audit,
            diagnostics=_diagnostics(
                request,
                status="accepted",
                side_effect=accepted_side_effect,
            ),
            message_key=message_key,
            command_response=outcome.command_response,
        )

    def _patch_task_node(
        self,
        request: ContractCommandRequest,
    ) -> ContractCommandResult:
        if self.task_node_handler is None:
            return _result(
                request,
                status="unsupported",
                side_effect="no_effect",
                reason_code="unsupported_command",
                message_key="contractRevision.unsupportedTaskNodeCommand",
                diagnostics=_diagnostics(
                    request,
                    status="unsupported",
                    side_effect="no_effect",
                    reason_code="unsupported_command",
                ),
            )
        try:
            payload = PatchTaskNodePayload.model_validate(request.payload)
        except ValidationError:
            return _result(
                request,
                status="rejected",
                side_effect="no_effect",
                reason_code="invalid_payload",
                message_key="contractRevision.invalidTaskNodePatchPayload",
                diagnostics=_diagnostics(
                    request,
                    status="rejected",
                    side_effect="no_effect",
                    reason_code="invalid_payload",
                ),
            )
        outcome = self.task_node_handler.patch_task_node(request, payload)
        return self._task_node_result(request, outcome)

    def _create_task_node(
        self,
        request: ContractCommandRequest,
    ) -> ContractCommandResult:
        if self.task_node_handler is None:
            return _unsupported_task_node_result(request)
        try:
            payload = CreateTaskNodePayload.model_validate(request.payload)
        except ValidationError:
            return _invalid_task_node_payload_result(request)
        outcome = self.task_node_handler.create_task_node(request, payload)
        return self._task_node_result(request, outcome)

    def _delete_task_node(
        self,
        request: ContractCommandRequest,
    ) -> ContractCommandResult:
        if self.task_node_handler is None:
            return _unsupported_task_node_result(request)
        try:
            payload = DeleteTaskNodePayload.model_validate(request.payload)
        except ValidationError:
            return _invalid_task_node_payload_result(request)
        outcome = self.task_node_handler.delete_task_node(request, payload)
        return self._task_node_result(request, outcome)

    def _create_execution_task(
        self,
        request: ContractCommandRequest,
    ) -> ContractCommandResult:
        if self.task_node_handler is None:
            return _unsupported_task_node_result(request)
        try:
            payload = CreateExecutionTaskPayload.model_validate(request.payload)
        except ValidationError:
            return _invalid_task_node_payload_result(request)
        outcome = self.task_node_handler.create_execution_task(request, payload)
        return self._task_node_result(request, outcome)

    def _task_node_result(
        self,
        request: ContractCommandRequest,
        outcome: ContractTaskNodeCommandOutcome,
    ) -> ContractCommandResult:
        plan_id = outcome.plan_id or request.plan_id
        task_node_id = (
            outcome.task_node.task_node_id
            if outcome.task_node is not None
            else request.task_node_id
        )
        refs = _task_node_refs(plan_id=plan_id, task_node_id=task_node_id)
        if not outcome.accepted or outcome.status != "accepted":
            result_status: ContractCommandStatus = outcome.status
            if not outcome.accepted and result_status == "accepted":
                result_status = "rejected"
            reason_code = outcome.reason_code
            if result_status != "noop":
                reason_code = reason_code or "command_rejected"
            return _result(
                request,
                status=result_status,
                side_effect="no_effect",
                refs=refs,
                reason_code=reason_code,
                message_key="contractRevision.taskNodePatchRejected",
                diagnostics=_diagnostics(
                    request,
                    status=result_status,
                    side_effect="no_effect",
                    reason_code=reason_code,
                ),
                command_response=outcome.command_response,
                plan_id=plan_id,
                task_node_id=task_node_id,
            )
        activity = ContractCommandActivityDescriptor(
            title=_task_node_activity_title(request),
            body=outcome.message,
            related_refs=refs,
        )
        audit = ContractCommandAuditDescriptor(
            command_id=request.command_id,
            command_kind=request.command_kind,
            status="accepted",
            side_effect="state_effect",
            scope_kind=request.scope_kind,
            session_id=request.session_id,
            plan_id=plan_id,
            task_node_id=task_node_id,
            target_ref=ObjectRef(kind="published_task", id=task_node_id)
            if task_node_id is not None
            else None,
            summary=f"{_task_node_activity_title(request)} through Contract Revision command.",
        )
        return _result(
            request,
            status="accepted",
            side_effect="state_effect",
            refs=refs,
            activity=activity,
            audit=audit,
            diagnostics=_diagnostics(
                request,
                status="accepted",
                side_effect="state_effect",
            ),
            message_key=_task_node_message_key(request),
            command_response=outcome.command_response,
            new_version=(
                outcome.task_node.version if outcome.task_node is not None else None
            ),
            plan_id=plan_id,
            task_node_id=task_node_id,
        )

    def _record_guidance(self, request: ContractCommandRequest) -> ContractCommandResult:
        try:
            payload = RecordGuidancePayload.model_validate(request.payload)
        except ValidationError:
            return _result(
                request,
                status="rejected",
                side_effect="no_effect",
                reason_code="invalid_payload",
                message_key="contractRevision.invalidGuidancePayload",
                diagnostics=_diagnostics(
                    request,
                    status="rejected",
                    side_effect="no_effect",
                    reason_code="invalid_payload",
                ),
            )
        invalid_scope = self._invalid_scope_reason(request)
        if invalid_scope is not None:
            return _result(
                request,
                status="rejected",
                side_effect="no_effect",
                reason_code=invalid_scope,
                message_key="contractRevision.invalidGuidanceScope",
                diagnostics=_diagnostics(
                    request,
                    status="rejected",
                    side_effect="no_effect",
                    reason_code=invalid_scope,
                    preview=_preview(payload.guidance_text),
                ),
            )
        fact = GuidanceFact(
            workspace_id=request.workspace_id or self.workspace_id,
            session_id=request.session_id,
            scope_kind=_guidance_scope(request),
            plan_id=request.plan_id,
            task_node_id=request.task_node_id,
            guidance_kind=payload.guidance_kind,
            guidance_text=payload.guidance_text,
            applies_to_future_tasks=payload.applies_to_future_tasks,
            source_command_id=request.command_id,
            source_router_decision_id=request.router_decision_id,
            source_message_ref=request.input_message_ref,
        )
        saved = self.guidance_store.create(fact)
        refs = _guidance_refs(request, saved.guidance_id)
        activity = ContractCommandActivityDescriptor(
            title="Guidance recorded",
            body=_activity_body(payload.guidance_text),
            related_refs=refs,
        )
        audit = ContractCommandAuditDescriptor(
            command_id=request.command_id,
            command_kind=request.command_kind,
            status="accepted",
            side_effect="context_effect",
            scope_kind=request.scope_kind,
            session_id=request.session_id,
            plan_id=request.plan_id,
            task_node_id=request.task_node_id,
            target_ref=_target_ref(request),
            summary=(
                f"Recorded {payload.guidance_kind} guidance for "
                f"{request.scope_kind} scope."
            ),
        )
        diagnostics = _diagnostics(
            request,
            status="accepted",
            side_effect="context_effect",
            preview=_preview(payload.guidance_text),
            truncated=len(payload.guidance_text) > _GUIDANCE_PREVIEW_LIMIT,
        )
        return _result(
            request,
            status="accepted",
            side_effect="context_effect",
            refs=refs,
            activity=activity,
            audit=audit,
            diagnostics=diagnostics,
            guidance_id=saved.guidance_id,
            new_version=saved.version,
        )

    def _invalid_scope_reason(self, request: ContractCommandRequest) -> str | None:
        if request.scope_kind == "session":
            return None
        if self.plan_store is None:
            return None
        if request.scope_kind == "plan":
            if request.plan_id is None:
                return "target_not_found"
            plan = self.plan_store.get_plan(request.session_id, request.plan_id)
            return None if plan is not None else "target_not_found"
        if request.scope_kind == "task":
            if request.task_node_id is None:
                return "target_not_found"
            node = self.plan_store.get_task_node(
                request.session_id,
                request.task_node_id,
            )
            if node is None:
                return "target_not_found"
            if request.plan_id is not None and node.plan_id != request.plan_id:
                return "target_scope_mismatch"
            return None
        return "invalid_scope"


def _guidance_scope(
    request: ContractCommandRequest,
) -> Literal["session", "plan", "task"]:
    if request.scope_kind == "plan":
        return "plan"
    if request.scope_kind == "task":
        return "task"
    return "session"


def _target_ref(request: ContractCommandRequest) -> ObjectRef | None:
    if request.scope_kind == "task" and request.task_node_id is not None:
        return ObjectRef(kind="published_task", id=request.task_node_id)
    if request.scope_kind == "plan" and request.plan_id is not None:
        return ObjectRef(kind="plan", id=request.plan_id)
    return None


def _guidance_refs(
    request: ContractCommandRequest,
    guidance_id: str,
) -> tuple[SessionActivityRefView, ...]:
    refs: list[SessionActivityRefView] = [
        SessionActivityRefView(
            kind="message",
            id=guidance_id,
            label="Guidance",
        )
    ]
    if request.plan_id is not None:
        refs.append(
            SessionActivityRefView(
                kind="plan",
                id=request.plan_id,
                label="Plan",
                object_ref=ObjectRef(kind="plan", id=request.plan_id),
            )
        )
    if request.task_node_id is not None:
        refs.append(
            SessionActivityRefView(
                kind="task",
                id=request.task_node_id,
                label="Task",
                object_ref=ObjectRef(kind="published_task", id=request.task_node_id),
            )
        )
    return tuple(refs)


def _interaction_refs(
    kind: Literal["ask", "confirmation"],
    ref_id: str | None,
    label: str,
) -> tuple[SessionActivityRefView, ...]:
    if ref_id is None:
        return ()
    return (
        SessionActivityRefView(
            kind=kind,
            id=ref_id,
            label=label,
            object_ref=ObjectRef(kind="message", id=ref_id),
        ),
    )


def _task_node_refs(
    *,
    plan_id: str | None,
    task_node_id: str | None,
) -> tuple[SessionActivityRefView, ...]:
    refs: list[SessionActivityRefView] = []
    if plan_id is not None:
        refs.append(
            SessionActivityRefView(
                kind="plan",
                id=plan_id,
                label="Plan",
                object_ref=ObjectRef(kind="plan", id=plan_id),
            )
        )
    if task_node_id is not None:
        refs.append(
            SessionActivityRefView(
                kind="task",
                id=task_node_id,
                label="Task",
                object_ref=ObjectRef(kind="published_task", id=task_node_id),
            )
        )
    return tuple(refs)


def _task_node_activity_title(request: ContractCommandRequest) -> str:
    if request.command_kind == "create_task_node":
        return "Task created"
    if request.command_kind == "delete_task_node":
        return "Task removed"
    if request.command_kind == "create_execution_task":
        return "Execution work created"
    return "Task changed"


def _task_node_message_key(request: ContractCommandRequest) -> str:
    if request.command_kind == "create_task_node":
        return "contractRevision.taskNodeCreated"
    if request.command_kind == "delete_task_node":
        return "contractRevision.taskNodeDeleted"
    if request.command_kind == "create_execution_task":
        return "contractRevision.executionTaskCreated"
    return "contractRevision.taskNodePatched"


def _unsupported_task_node_result(
    request: ContractCommandRequest,
) -> ContractCommandResult:
    return _result(
        request,
        status="unsupported",
        side_effect="no_effect",
        reason_code="unsupported_command",
        message_key="contractRevision.unsupportedTaskNodeCommand",
        diagnostics=_diagnostics(
            request,
            status="unsupported",
            side_effect="no_effect",
            reason_code="unsupported_command",
        ),
    )


def _invalid_task_node_payload_result(
    request: ContractCommandRequest,
) -> ContractCommandResult:
    return _result(
        request,
        status="rejected",
        side_effect="no_effect",
        reason_code="invalid_payload",
        message_key="contractRevision.invalidTaskNodePayload",
        diagnostics=_diagnostics(
            request,
            status="rejected",
            side_effect="no_effect",
            reason_code="invalid_payload",
        ),
    )


def _unsupported_interaction_result(
    request: ContractCommandRequest,
) -> ContractCommandResult:
    return _result(
        request,
        status="unsupported",
        side_effect="no_effect",
        reason_code="unsupported_command",
        message_key="contractRevision.unsupportedInteractionCommand",
        diagnostics=_diagnostics(
            request,
            status="unsupported",
            side_effect="no_effect",
            reason_code="unsupported_command",
        ),
    )


def _invalid_interaction_payload_result(
    request: ContractCommandRequest,
    *,
    message_key: str,
) -> ContractCommandResult:
    return _result(
        request,
        status="rejected",
        side_effect="no_effect",
        reason_code="invalid_payload",
        message_key=message_key,
        diagnostics=_diagnostics(
            request,
            status="rejected",
            side_effect="no_effect",
            reason_code="invalid_payload",
        ),
    )


def _result(
    request: ContractCommandRequest,
    *,
    status: ContractCommandStatus,
    side_effect: SessionActivitySideEffect,
    plan_id: str | None = None,
    task_node_id: str | None = None,
    refs: tuple[SessionActivityRefView, ...] = (),
    activity: ContractCommandActivityDescriptor | None = None,
    audit: ContractCommandAuditDescriptor | None = None,
    diagnostics: ContractCommandDiagnosticDescriptor | None = None,
    command_response: CommandResponse | None = None,
    new_version: int | None = None,
    reason_code: str | None = None,
    message_key: str | None = None,
    guidance_id: str | None = None,
) -> ContractCommandResult:
    return ContractCommandResult(
        command_id=request.command_id,
        idempotency_key=request.idempotency_key,
        command_kind=request.command_kind,
        status=status,
        side_effect=side_effect,
        scope_kind=request.scope_kind,
        session_id=request.session_id,
        plan_id=request.plan_id if plan_id is None else plan_id,
        task_node_id=request.task_node_id if task_node_id is None else task_node_id,
        ask_id=request.ask_id,
        confirmation_id=request.confirmation_id,
        refs=refs,
        activity=activity,
        audit=audit,
        diagnostics=diagnostics,
        command_response=command_response,
        new_version=new_version,
        reason_code=reason_code,
        message_key=message_key,
        guidance_id=guidance_id,
    )


def _diagnostics(
    request: ContractCommandRequest,
    *,
    status: ContractCommandStatus,
    side_effect: SessionActivitySideEffect,
    reason_code: str | None = None,
    preview: str | None = None,
    truncated: bool = False,
) -> ContractCommandDiagnosticDescriptor:
    return ContractCommandDiagnosticDescriptor(
        command_kind=request.command_kind,
        status=status,
        side_effect=side_effect,
        scope_kind=request.scope_kind,
        reason_code=reason_code,
        router_decision_id=request.router_decision_id,
        preview=preview,
        truncated=truncated,
    )


def _hash_request(request: ContractCommandRequest) -> str:
    payload = request.model_dump(mode="json", exclude={"command_id"})
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _activity_body(text: str) -> str:
    preview = _preview(text)
    return f"Guidance recorded: {preview}"


def _preview(text: str) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= _GUIDANCE_PREVIEW_LIMIT:
        return normalized
    return normalized[: _GUIDANCE_PREVIEW_LIMIT - 1] + "..."


__all__ = ["ContractRevisionCommandService"]
