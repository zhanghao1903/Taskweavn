"""Command gateway response and task-command mapping helpers."""

from __future__ import annotations

from taskweavn.server.ui_contract.commands import UpdateTaskNodePayload
from taskweavn.server.ui_contract.envelopes import (
    CommandRequest,
    CommandResponse,
    CommandResult,
    RefreshHint,
)
from taskweavn.server.ui_contract.errors import (
    bad_request,
    command_rejected,
    internal_error,
    not_found,
)
from taskweavn.server.ui_contract.refs import AffectedObjectRef, AffectedScope, ObjectRef
from taskweavn.task.commands import CommandResult as CoreCommandResult
from taskweavn.task.commands import TaskGuidanceMode
from taskweavn.task.models import TaskNodePatch, TaskRef
from taskweavn.task.plan_publisher import PublishPlanResult


def _child_idempotency_key(idempotency_key: str | None, suffix: str) -> str | None:
    if idempotency_key is None:
        return None
    return f"{idempotency_key}:{suffix}"


class _TaskTreeIdentityError(ValueError):
    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.details = details


def _synthetic_task_tree_id(session_id: str) -> str:
    return f"session:{session_id}:task-tree"


def _command_response[T](
    request: CommandRequest[T],
    result: CoreCommandResult,
    *,
    object_refs: tuple[ObjectRef, ...] = (),
    affected_objects: tuple[AffectedObjectRef, ...] = (),
    suggested_queries: tuple[str, ...] = (),
    affected_scopes: tuple[AffectedScope, ...] = (),
) -> CommandResponse:
    contract_result = CommandResult(
        command_id=request.command_id,
        status=result.status,
        message=result.message,
        affected_task_refs=result.affected_task_refs,
        object_refs=_object_refs_for_result(result, extra=object_refs),
        affected_objects=_affected_objects_for_result(result, extra=affected_objects),
        emitted_message_ids=result.emitted_message_ids,
        published_task_ids=result.published_task_ids,
        debug_refs=_debug_refs(request, result),
    )
    refresh = RefreshHint(
        wait_for_events=result.accepted,
        suggested_queries=suggested_queries,
        affected_task_refs=result.affected_task_refs,
        affected_scopes=affected_scopes,
    )
    if result.accepted:
        return CommandResponse(
            request_id=request.command_id,
            ok=True,
            result=contract_result,
            error=None,
            refresh=refresh,
        )
    return CommandResponse(
        request_id=request.command_id,
        ok=False,
        result=contract_result,
        error=command_rejected(result.message),
        refresh=refresh.model_copy(update={"wait_for_events": False}),
    )


def _merge_prompt_task_tree_results(
    raw_result: CoreCommandResult,
    tree_result: CoreCommandResult,
) -> CoreCommandResult:
    return CoreCommandResult(
        command_id=tree_result.command_id,
        status=tree_result.status,
        message=tree_result.message,
        affected_task_refs=tree_result.affected_task_refs,
        emitted_message_ids=_dedupe_ids(
            (*raw_result.emitted_message_ids, *tree_result.emitted_message_ids)
        ),
        published_task_ids=tree_result.published_task_ids,
    )


def _plan_publish_command_result(result: PublishPlanResult) -> CoreCommandResult:
    return CoreCommandResult(
        command_id=result.command_id,
        status="rejected" if result.skipped else "accepted",
        message=result.reason or "plan published",
        affected_task_refs=tuple(
            TaskRef.published(task_id) for task_id in result.published_task_ids
        ),
        published_task_ids=result.published_task_ids,
    )


def _command_not_found_response[T](
    request: CommandRequest[T],
    message: str,
) -> CommandResponse:
    return CommandResponse(
        request_id=request.command_id,
        ok=False,
        result=None,
        error=not_found(message),
        refresh=RefreshHint(wait_for_events=False),
    )


def _command_bad_request_response[T](
    request: CommandRequest[T],
    message: str,
    **details: object,
) -> CommandResponse:
    return CommandResponse(
        request_id=request.command_id,
        ok=False,
        result=None,
        error=bad_request(message, **details),
        refresh=RefreshHint(wait_for_events=False),
    )


def _command_exception_response[T](
    request: CommandRequest[T],
    exc: Exception,
) -> CommandResponse:
    return CommandResponse(
        request_id=request.command_id,
        ok=False,
        result=None,
        error=internal_error(
            "Unable to process command",
            error_type=type(exc).__name__,
        ),
        refresh=RefreshHint(wait_for_events=False),
    )


def _object_refs_for_result(
    result: CoreCommandResult,
    *,
    extra: tuple[ObjectRef, ...],
) -> tuple[ObjectRef, ...]:
    refs = [ObjectRef(kind="command", id=result.command_id), *extra]
    refs.extend(_object_ref_for_task_ref(ref) for ref in result.affected_task_refs)
    refs.extend(
        ObjectRef(kind="published_task", id=task_id) for task_id in result.published_task_ids
    )
    return _dedupe_object_refs(refs)


def _affected_objects_for_result(
    result: CoreCommandResult,
    *,
    extra: tuple[AffectedObjectRef, ...],
) -> tuple[AffectedObjectRef, ...]:
    affected = [*extra]
    affected.extend(
        AffectedObjectRef(
            ref=_object_ref_for_task_ref(ref),
            impact="changed",
        )
        for ref in result.affected_task_refs
    )
    affected.extend(
        AffectedObjectRef(
            ref=ObjectRef(kind="published_task", id=task_id),
            impact="created",
        )
        for task_id in result.published_task_ids
    )
    return tuple(affected)


def _object_ref_for_task_ref(task_ref: TaskRef) -> ObjectRef:
    if task_ref.kind == "draft":
        return ObjectRef(kind="draft_task", id=task_ref.id)
    return ObjectRef(kind="published_task", id=task_ref.id)


def _dedupe_object_refs(refs: list[ObjectRef]) -> tuple[ObjectRef, ...]:
    seen: set[tuple[str, str]] = set()
    result: list[ObjectRef] = []
    for ref in refs:
        key = (ref.kind, ref.id)
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return tuple(result)


def _dedupe_ids(ids: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return tuple(result)


def _debug_refs[T](request: CommandRequest[T], result: CoreCommandResult) -> dict[str, str]:
    refs: dict[str, str] = {}
    if result.command_id != request.command_id:
        refs["backendCommandId"] = result.command_id
    if request.idempotency_key is not None:
        refs["idempotencyKey"] = request.idempotency_key
    return refs


def _task_node_patch(payload: UpdateTaskNodePayload) -> TaskNodePatch:
    children_ops: tuple[dict[str, object], ...] = ()
    if payload.update_mode != "node_fields":
        children_ops = (
            {
                "op": payload.update_mode,
                "preserve_root_id": payload.preserve_root_id,
            },
        )
    return TaskNodePatch(
        title=payload.title,
        intent=payload.full_intent or payload.summary,
        constraints_add=payload.constraints or (),
        children_ops=children_ops,
    )


def _update_suggested_queries(payload: UpdateTaskNodePayload) -> tuple[str, ...]:
    if payload.update_mode == "node_fields":
        return ("session.snapshot", "task.detail")
    return ("session.snapshot", "task.tree", "task.detail")


def _update_affected_scopes(
    task_ref: TaskRef,
    payload: UpdateTaskNodePayload,
) -> tuple[AffectedScope, ...]:
    if payload.update_mode in {"replace_children", "replace_subtree"}:
        return (
            AffectedScope(kind="task_subtree", task_ref=task_ref),
            AffectedScope(kind="task_detail", task_ref=task_ref),
        )
    return (AffectedScope(kind="task_detail", task_ref=task_ref),)


def _guidance_mode(mode: str) -> TaskGuidanceMode:
    if mode == "clarification_answer":
        return "clarification"
    if mode == "revision_request":
        return "correction"
    return "guidance"
