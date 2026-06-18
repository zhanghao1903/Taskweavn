"""Adapters from Contract Revision TaskNode commands to existing handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from taskweavn.contract_revision.models import (
    ContractCommandRequest,
    ContractCommandStatus,
    CreateExecutionTaskPayload,
    CreateTaskNodePayload,
    DeleteTaskNodePayload,
    PatchTaskNodePayload,
)
from taskweavn.server.ui_contract.commands import UpdateTaskNodePayload
from taskweavn.server.ui_contract.envelopes import CommandRequest, CommandResponse
from taskweavn.server.ui_contract.gateway_protocols import UiCommandGateway
from taskweavn.task.plan_models import (
    Plan,
    PlanStatus,
    PlanTaskNode,
    PlanTaskNodeReadiness,
)
from taskweavn.task.plan_stores import PlanStore, PlanStoreError
from taskweavn.task.stores import VersionConflictError

_EDITABLE_PLAN_STATUSES: set[PlanStatus] = {"draft", "reviewing", "approved"}


@dataclass(frozen=True)
class ContractTaskNodeCommandOutcome:
    accepted: bool
    message: str
    status: ContractCommandStatus = "accepted"
    command_response: CommandResponse | None = None
    reason_code: str | None = None
    plan_id: str | None = None
    task_node: PlanTaskNode | None = None


class ContractTaskNodeCommandHandler(Protocol):
    def patch_task_node(
        self,
        request: ContractCommandRequest,
        payload: PatchTaskNodePayload,
    ) -> ContractTaskNodeCommandOutcome: ...

    def create_task_node(
        self,
        request: ContractCommandRequest,
        payload: CreateTaskNodePayload,
    ) -> ContractTaskNodeCommandOutcome: ...

    def delete_task_node(
        self,
        request: ContractCommandRequest,
        payload: DeleteTaskNodePayload,
    ) -> ContractTaskNodeCommandOutcome: ...

    def create_execution_task(
        self,
        request: ContractCommandRequest,
        payload: CreateExecutionTaskPayload,
    ) -> ContractTaskNodeCommandOutcome: ...


class UiGatewayContractTaskNodeCommandHandler:
    """Delegate versioned TaskNode patches to the existing UI command gateway."""

    def __init__(
        self,
        command_gateway: UiCommandGateway,
        *,
        plan_store: PlanStore,
    ) -> None:
        self._command_gateway = command_gateway
        self._plan_store = plan_store

    def patch_task_node(
        self,
        request: ContractCommandRequest,
        payload: PatchTaskNodePayload,
    ) -> ContractTaskNodeCommandOutcome:
        if request.task_node_id is None:
            return ContractTaskNodeCommandOutcome(
                accepted=False,
                message="TaskNode target is missing.",
                reason_code="target_not_found",
            )
        command_response = self._command_gateway.update_task_node(
            request.task_node_id,
            CommandRequest[UpdateTaskNodePayload](
                command_id=request.command_id,
                session_id=request.session_id,
                idempotency_key=request.idempotency_key,
                expected_version=request.expected_version,
                payload=UpdateTaskNodePayload(
                    title=payload.title,
                    summary=payload.summary,
                    full_intent=payload.full_intent or payload.intent,
                    constraints=payload.constraints,
                    update_mode=payload.update_mode,
                    preserve_root_id=payload.preserve_root_id,
                ),
            ),
        )
        return _outcome_from_command_response(command_response)

    def create_task_node(
        self,
        request: ContractCommandRequest,
        payload: CreateTaskNodePayload,
    ) -> ContractTaskNodeCommandOutcome:
        plan = self._target_editable_plan(request, allow_new_plan=False)
        if isinstance(plan, ContractTaskNodeCommandOutcome):
            return plan
        try:
            node = _node_for_create_payload(
                request,
                payload,
                plan=plan,
                existing_nodes=self._plan_store.list_task_nodes(
                    request.session_id,
                    plan.plan_id,
                ),
                readiness="draft",
            )
            saved = self._plan_store.add_task_node(
                node,
                expected_plan_version=request.expected_version,
            )
        except (LookupError, PlanStoreError, ValueError, VersionConflictError) as exc:
            return _failure_from_exception(exc)
        return ContractTaskNodeCommandOutcome(
            accepted=True,
            message="TaskNode was created.",
            plan_id=plan.plan_id,
            task_node=saved,
        )

    def delete_task_node(
        self,
        request: ContractCommandRequest,
        payload: DeleteTaskNodePayload,
    ) -> ContractTaskNodeCommandOutcome:
        del payload
        if request.task_node_id is None:
            return ContractTaskNodeCommandOutcome(
                accepted=False,
                status="rejected",
                message="TaskNode target is missing.",
                reason_code="target_not_found",
            )
        node = self._plan_store.get_task_node(request.session_id, request.task_node_id)
        if node is None:
            return ContractTaskNodeCommandOutcome(
                accepted=False,
                status="rejected",
                message="TaskNode target was not found.",
                reason_code="target_not_found",
            )
        if node.readiness == "cancelled" or node.execution == "cancelled":
            return ContractTaskNodeCommandOutcome(
                accepted=True,
                status="noop",
                message="TaskNode is already cancelled.",
                plan_id=node.plan_id,
                task_node=node,
            )
        blocked_reason = _delete_block_reason(node)
        if blocked_reason is not None:
            return ContractTaskNodeCommandOutcome(
                accepted=False,
                status="rejected",
                message="TaskNode has execution evidence and cannot be removed.",
                reason_code=blocked_reason,
                plan_id=node.plan_id,
                task_node=node,
            )
        try:
            saved = self._plan_store.save_task_node(
                node.model_copy(
                    update={
                        "readiness": "cancelled",
                        "execution": "cancelled",
                    }
                ),
                expected_version=request.expected_version or node.version,
            )
        except (LookupError, PlanStoreError, ValueError, VersionConflictError) as exc:
            return _failure_from_exception(exc)
        return ContractTaskNodeCommandOutcome(
            accepted=True,
            message="TaskNode was cancelled.",
            plan_id=saved.plan_id,
            task_node=saved,
        )

    def create_execution_task(
        self,
        request: ContractCommandRequest,
        payload: CreateExecutionTaskPayload,
    ) -> ContractTaskNodeCommandOutcome:
        plan = self._target_editable_plan(request, allow_new_plan=True, payload=payload)
        if isinstance(plan, ContractTaskNodeCommandOutcome):
            return plan
        stored_plan = self._plan_store.get_plan(request.session_id, plan.plan_id)
        existing_nodes = (
            self._plan_store.list_task_nodes(request.session_id, plan.plan_id)
            if stored_plan is not None
            else []
        )
        node = _node_for_execution_payload(
            request,
            payload,
            plan=plan,
            existing_nodes=existing_nodes,
        )
        try:
            if stored_plan is not None:
                saved = self._plan_store.add_task_node(
                    node,
                    expected_plan_version=request.expected_version,
                )
                plan_id = plan.plan_id
            else:
                self._plan_store.create_plan(plan, (node,))
                saved = node
                plan_id = plan.plan_id
        except (LookupError, PlanStoreError, ValueError, VersionConflictError) as exc:
            return _failure_from_exception(exc)
        return ContractTaskNodeCommandOutcome(
            accepted=True,
            message="Execution TaskNode was created.",
            plan_id=plan_id,
            task_node=saved,
        )

    def _target_editable_plan(
        self,
        request: ContractCommandRequest,
        *,
        allow_new_plan: bool,
        payload: CreateExecutionTaskPayload | None = None,
    ) -> Plan | ContractTaskNodeCommandOutcome:
        if request.plan_id is not None:
            plan = self._plan_store.get_plan(request.session_id, request.plan_id)
            if plan is None:
                return ContractTaskNodeCommandOutcome(
                    accepted=False,
                    status="rejected",
                    message="Plan target was not found.",
                    reason_code="target_not_found",
                )
            if plan.status not in _EDITABLE_PLAN_STATUSES:
                return ContractTaskNodeCommandOutcome(
                    accepted=False,
                    status="rejected",
                    message=f"Plan status {plan.status!r} cannot be edited.",
                    reason_code="invalid_plan_state",
                    plan_id=plan.plan_id,
                )
            return plan

        plan = self._plan_store.get_active_plan(request.session_id)
        if plan is not None and plan.status in _EDITABLE_PLAN_STATUSES:
            return plan
        if allow_new_plan and payload is not None:
            return _new_execution_plan(request, payload)
        return ContractTaskNodeCommandOutcome(
            accepted=False,
            status="rejected",
            message="No editable Plan is available.",
            reason_code="target_not_found" if plan is None else "invalid_plan_state",
            plan_id=None if plan is None else plan.plan_id,
        )


def _outcome_from_command_response(
    command_response: CommandResponse,
) -> ContractTaskNodeCommandOutcome:
    if command_response.ok and command_response.result is not None:
        return ContractTaskNodeCommandOutcome(
            accepted=True,
            message=command_response.result.message,
            status="accepted",
            command_response=command_response,
        )
    return ContractTaskNodeCommandOutcome(
        accepted=False,
        message=command_response.error.message
        if command_response.error is not None
        else "Command was rejected.",
        status="rejected",
        command_response=command_response,
        reason_code=command_response.error.code
        if command_response.error is not None
        else "command_rejected",
    )


def _node_for_create_payload(
    request: ContractCommandRequest,
    payload: CreateTaskNodePayload,
    *,
    plan: Plan,
    existing_nodes: list[PlanTaskNode],
    readiness: PlanTaskNodeReadiness,
) -> PlanTaskNode:
    order_index = _next_order_index(
        existing_nodes,
        after_task_node_id=payload.after_task_node_id,
    )
    return PlanTaskNode(
        plan_id=plan.plan_id,
        session_id=request.session_id,
        task_index=_next_task_index(existing_nodes),
        order_index=order_index,
        title=payload.title,
        intent=payload.intent,
        summary=payload.summary or payload.intent,
        instructions=payload.instructions,
        required_capability=payload.required_capability or "general",
        depends_on=payload.depends_on,
        constraints=payload.constraints,
        acceptance_criteria=payload.acceptance_criteria,
        readiness=readiness,
    )


def _node_for_execution_payload(
    request: ContractCommandRequest,
    payload: CreateExecutionTaskPayload,
    *,
    plan: Plan,
    existing_nodes: list[PlanTaskNode],
) -> PlanTaskNode:
    title = payload.title or _title_from_intent(payload.intent)
    create_payload = CreateTaskNodePayload(
        title=title,
        intent=payload.intent,
        summary=payload.summary or payload.intent,
        instructions=payload.instructions,
        required_capability=payload.required_capability or "general",
        constraints=payload.constraints,
        acceptance_criteria=payload.acceptance_criteria
        or ("Complete the requested workspace change.",),
    )
    return _node_for_create_payload(
        request,
        create_payload,
        plan=plan,
        existing_nodes=existing_nodes,
        readiness="approved",
    )


def _new_execution_plan(
    request: ContractCommandRequest,
    payload: CreateExecutionTaskPayload,
) -> Plan:
    title = payload.title or _title_from_intent(payload.intent)
    return Plan(
        session_id=request.session_id,
        title=title,
        objective=payload.intent,
        summary=payload.summary or payload.intent,
        status="approved",
        created_by="runtime_input_router",
    )


def _next_task_index(nodes: list[PlanTaskNode]) -> str:
    used = {node.task_index for node in nodes}
    candidate = 1
    while str(candidate) in used:
        candidate += 1
    return str(candidate)


def _next_order_index(
    nodes: list[PlanTaskNode],
    *,
    after_task_node_id: str | None,
) -> int:
    if after_task_node_id is not None:
        for node in nodes:
            if node.task_node_id == after_task_node_id:
                return node.order_index + 1
        raise ValueError(f"after TaskNode {after_task_node_id!r} was not found")
    if not nodes:
        return 0
    return max(node.order_index for node in nodes) + 1


def _title_from_intent(intent: str) -> str:
    normalized = " ".join(intent.split())
    if len(normalized) <= 80:
        return normalized
    return normalized[:79] + "..."


def _delete_block_reason(node: PlanTaskNode) -> str | None:
    if node.readiness == "published" or node.published_ref is not None:
        return "task_already_published"
    if node.execution not in {"not_started", "unknown"}:
        return "task_has_execution_evidence"
    if any(
        ref is not None
        for ref in (
            node.result_ref,
            node.error_ref,
            node.file_summary_ref,
            node.audit_ref,
        )
    ):
        return "task_has_execution_evidence"
    return None


def _failure_from_exception(exc: Exception) -> ContractTaskNodeCommandOutcome:
    if isinstance(exc, VersionConflictError):
        reason_code = "version_conflict"
        status: ContractCommandStatus = "conflict"
    elif isinstance(exc, LookupError):
        reason_code = "target_not_found"
        status = "rejected"
    elif isinstance(exc, ValueError):
        reason_code = "invalid_payload"
        status = "rejected"
    else:
        reason_code = "command_rejected"
        status = "rejected"
    return ContractTaskNodeCommandOutcome(
        accepted=False,
        status=status,
        message=str(exc),
        reason_code=reason_code,
    )


__all__ = [
    "ContractTaskNodeCommandHandler",
    "ContractTaskNodeCommandOutcome",
    "UiGatewayContractTaskNodeCommandHandler",
]
