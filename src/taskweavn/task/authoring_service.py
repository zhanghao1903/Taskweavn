"""Authoring command service and deterministic handlers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from threading import RLock
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import ValidationError

from taskweavn.interaction import AgentMessage, MessageBus
from taskweavn.task.authoring import (
    AuthoringCommand,
    AuthoringCommandBatch,
    AuthoringCommandError,
    AuthoringCommandResult,
    AuthoringCommandWarning,
    AuthoringMessageEffect,
    DraftTaskTreeOperation,
    DraftTaskTreeValidator,
    FeasibilityReport,
    MutateDraftTaskTreeCommand,
    MutateRawTaskCommand,
    PublishDraftTaskTreeCommand,
    RawTask,
    RawTaskAnswer,
    RawTaskAnswerOption,
    RawTaskAsk,
    RawTaskOperation,
)
from taskweavn.task.models import DraftTaskNode, TaskNodePatch, TaskRef
from taskweavn.task.publisher import TaskPublisher, TaskPublishResult
from taskweavn.task.stores import (
    AuthoringStateStore,
    DraftTaskStore,
    RawTaskStore,
    TaskStoreError,
)


def _new_id() -> str:
    return uuid4().hex


@runtime_checkable
class AuthoringCommandService(Protocol):
    """Executes validated authoring commands against authoring stores."""

    def submit(self, batch: AuthoringCommandBatch) -> AuthoringCommandResult: ...


@dataclass(frozen=True)
class _CommandOutput:
    command_id: str
    object_refs: tuple[TaskRef, ...] = ()
    message_effects: tuple[AuthoringMessageEffect, ...] = ()
    warnings: tuple[AuthoringCommandWarning, ...] = ()


class DefaultAuthoringCommandService:
    """Default deterministic command handler for the authoring domain.

    This service is deliberately below the Collaborator LLM layer. It accepts
    already-structured commands, applies them to RawTaskStore/DraftTaskStore,
    and publishes requested message effects through MessageBus when present.
    """

    def __init__(
        self,
        *,
        raw_task_store: RawTaskStore,
        draft_store: DraftTaskStore,
        message_bus: MessageBus | None = None,
        task_publisher: TaskPublisher | None = None,
        draft_validator: DraftTaskTreeValidator | None = None,
        authoring_state_store: AuthoringStateStore | None = None,
    ) -> None:
        self._raw_task_store = raw_task_store
        self._draft_store = draft_store
        self._message_bus = message_bus
        self._task_publisher = task_publisher
        self._draft_validator = draft_validator
        self._authoring_state_store = authoring_state_store
        self._lock = RLock()
        self._idempotency_results: dict[str, AuthoringCommandResult] = {}

    def submit(self, batch: AuthoringCommandBatch) -> AuthoringCommandResult:
        with self._lock:
            idempotency_key = _idempotency_key(batch)
            if idempotency_key is not None:
                cached = self._idempotency_results.get(idempotency_key)
                if cached is not None:
                    return cached

            try:
                snapshot = self._snapshot(batch)
            except Exception as exc:  # noqa: BLE001 - returned as structured error
                result = AuthoringCommandResult(
                    ok=False,
                    batch_id=batch.batch_id,
                    errors=(
                        AuthoringCommandError(
                            code="transaction_unavailable",
                            message=str(exc),
                        ),
                    ),
                )
                self._remember(idempotency_key, result)
                return result
            outputs: list[_CommandOutput] = []
            errors: list[AuthoringCommandError] = []

            for command in batch.commands:
                try:
                    outputs.append(self._apply_command(command))
                except Exception as exc:  # noqa: BLE001 - converted to structured result
                    error = _command_error(command, exc)
                    errors.append(error)
                    if batch.mode == "all_or_nothing":
                        self._restore(snapshot)
                        result = AuthoringCommandResult(
                            ok=False,
                            batch_id=batch.batch_id,
                            errors=(error,),
                        )
                        self._remember(idempotency_key, result)
                        return result

            message_effects = tuple(
                effect for output in outputs for effect in output.message_effects
            )
            emitted_message_ids = self._publish_effects(batch, message_effects)
            result = AuthoringCommandResult(
                ok=not errors,
                batch_id=batch.batch_id,
                applied_command_ids=tuple(output.command_id for output in outputs),
                object_refs=tuple(ref for output in outputs for ref in output.object_refs),
                message_effects=message_effects,
                emitted_message_ids=emitted_message_ids,
                errors=tuple(errors),
                warnings=tuple(
                    warning for output in outputs for warning in output.warnings
                ),
            )
            self._remember(idempotency_key, result)
            return result

    def _apply_command(self, command: AuthoringCommand) -> _CommandOutput:
        if isinstance(command, MutateRawTaskCommand):
            return self._mutate_raw_task(command)
        if isinstance(command, MutateDraftTaskTreeCommand):
            return self._mutate_draft_tree(command)
        if isinstance(command, PublishDraftTaskTreeCommand):
            return self._publish_draft_tree(command)
        raise TypeError(f"unsupported authoring command {type(command).__name__}")

    def _mutate_raw_task(self, command: MutateRawTaskCommand) -> _CommandOutput:
        creating = any(operation.op == "create" for operation in command.operations)
        raw_task: RawTask | None = None
        if not creating:
            raw_task = self._require_raw_task(command.session_id, command.raw_task_id)

        for operation in command.operations:
            raw_task = self._apply_raw_operation(command, operation, raw_task)

        if raw_task is None:
            raise ValueError("RawTask command did not produce a RawTask")
        if creating:
            raw_task = self._raw_task_store.create(raw_task)
            if self._authoring_state_store is not None:
                self._authoring_state_store.set_active_raw_task(
                    raw_task.session_id,
                    raw_task.raw_task_id,
                )
        else:
            expected = command.expected_version or self._require_raw_version(raw_task)
            raw_task = self._raw_task_store.save(raw_task, expected_version=expected)
        return _CommandOutput(command_id=command.command_id)

    def _apply_raw_operation(
        self,
        command: MutateRawTaskCommand,
        operation: RawTaskOperation,
        current: RawTask | None,
    ) -> RawTask:
        if operation.op == "create":
            if current is not None:
                raise ValueError("RawTask create operation must be first")
            return _raw_task_from_payload(command, operation.payload)
        raw_task = _require_current_raw_task(current, operation)
        if operation.op == "set_intent_summary":
            return _copy_raw_task(
                raw_task,
                intent_summary=_require_str(operation.payload, "intent_summary"),
            )
        if operation.op == "record_feasibility":
            report = _feasibility_from_payload(operation.payload)
            return _copy_raw_task(
                raw_task,
                feasibility=report,
                status=_status_for_feasibility(report, operation.payload, raw_task.status),
            )
        if operation.op == "add_clarification_ask":
            ask = _ask_from_payload(raw_task.raw_task_id, operation.payload)
            return _copy_raw_task(
                raw_task,
                asks=(*raw_task.asks, ask),
                status="awaiting_user",
            )
        if operation.op == "apply_answer":
            answer = _answer_from_payload(raw_task, operation.payload)
            answers = (*raw_task.answers, answer)
            return _copy_raw_task(
                raw_task,
                answers=answers,
                status=operation.payload.get("status")
                or _status_after_answers(raw_task, answers),
            )
        if operation.op == "update_constraints":
            return _copy_raw_task(
                raw_task,
                constraints=_patched_values(
                    raw_task.constraints,
                    add=_tuple_payload(operation.payload, "add"),
                    remove=_tuple_payload(operation.payload, "remove"),
                ),
            )
        if operation.op == "update_assumptions":
            return _copy_raw_task(
                raw_task,
                assumptions=_patched_values(
                    raw_task.assumptions,
                    add=_tuple_payload(operation.payload, "add"),
                    remove=_tuple_payload(operation.payload, "remove"),
                ),
            )
        if operation.op == "set_status":
            return _copy_raw_task(raw_task, status=_require_str(operation.payload, "status"))
        raise ValueError(f"unsupported RawTask operation {operation.op!r}")

    def _mutate_draft_tree(self, command: MutateDraftTaskTreeCommand) -> _CommandOutput:
        object_refs: list[TaskRef] = []
        effects: list[AuthoringMessageEffect] = []
        warnings: list[AuthoringCommandWarning] = []

        for operation in command.operations:
            output = self._apply_draft_operation(command, operation)
            object_refs.extend(output.object_refs)
            effects.extend(output.message_effects)
            warnings.extend(output.warnings)

        return _CommandOutput(
            command_id=command.command_id,
            object_refs=tuple(object_refs),
            message_effects=tuple(effects),
            warnings=tuple(warnings),
        )

    def _apply_draft_operation(
        self,
        command: MutateDraftTaskTreeCommand,
        operation: DraftTaskTreeOperation,
    ) -> _CommandOutput:
        if operation.op == "create_tree":
            root_payloads = _required_sequence(operation.payload, "roots")
            roots = _root_nodes_from_payload(command.session_id, operation.payload)
            tree = self._draft_store.create_tree(command.session_id, roots)
            refs = [TaskRef.draft(node.draft_task_id) for node in tree.root_nodes]
            for root_payload, root_node in zip(root_payloads, tree.root_nodes, strict=True):
                refs.extend(
                    self._add_descendants(
                        command.session_id,
                        tree.draft_tree_id,
                        root_node.draft_task_id,
                        root_payload,
                    )
                )
            if self._authoring_state_store is not None:
                self._authoring_state_store.set_active_draft_tree(
                    command.session_id,
                    command.raw_task_id,
                    tree.draft_tree_id,
                )
            return _CommandOutput(command_id=command.command_id, object_refs=tuple(refs))

        draft_tree_id = _require_draft_tree_id(command)
        if operation.op == "patch_node":
            draft_task_id = _require_str(operation.payload, "draft_task_id")
            node = self._require_draft_node(command.session_id, draft_task_id)
            patch = TaskNodePatch.model_validate(operation.payload.get("patch", {}))
            updated = self._draft_store.update_node(
                command.session_id,
                draft_task_id,
                patch,
                expected_version=command.expected_version or node.version,
            )
            return _CommandOutput(
                command_id=command.command_id,
                object_refs=(TaskRef.draft(updated.draft_task_id),),
            )
        if operation.op == "add_node":
            tree = self._draft_store.get_tree(command.session_id, draft_tree_id)
            node = _draft_node_from_payload(
                command.session_id,
                draft_tree_id,
                operation.payload.get("node", operation.payload),
            )
            created = self._draft_store.add_node(
                command.session_id,
                draft_tree_id,
                node,
                expected_tree_version=command.expected_version or tree.version,
            )
            return _CommandOutput(
                command_id=command.command_id,
                object_refs=(TaskRef.draft(created.draft_task_id),),
            )
        if operation.op == "attach_options":
            return _CommandOutput(
                command_id=command.command_id,
                message_effects=(_message_effect_from_options(draft_tree_id, operation.payload),),
            )
        if operation.op == "mark_accepted":
            tree = self._draft_store.get_tree(command.session_id, draft_tree_id)
            accepted = self._draft_store.mark_accepted(
                command.session_id,
                draft_tree_id,
                expected_version=command.expected_version or tree.version,
            )
            accepted_refs = tuple(
                TaskRef.draft(node.draft_task_id) for node in accepted.root_nodes
            )
            return _CommandOutput(command_id=command.command_id, object_refs=accepted_refs)
        if operation.op == "mark_ready":
            return _CommandOutput(
                command_id=command.command_id,
                warnings=(
                    AuthoringCommandWarning(
                        code="mark_ready_noop",
                        message="mark_ready is recorded as a no-op until readiness is modeled",
                        command_id=command.command_id,
                    ),
                ),
            )
        raise ValueError(f"unsupported DraftTaskTree operation {operation.op!r}")

    def _add_descendants(
        self,
        session_id: str,
        draft_tree_id: str,
        parent_draft_task_id: str,
        parent_payload: object,
    ) -> list[TaskRef]:
        if not isinstance(parent_payload, dict):
            return []
        refs: list[TaskRef] = []
        for index, child_payload in enumerate(parent_payload.get("children", ())):
            tree = self._draft_store.get_tree(session_id, draft_tree_id)
            child = _draft_node_from_payload(
                session_id,
                draft_tree_id,
                child_payload,
                order_index=index,
                parent_draft_task_id=parent_draft_task_id,
            )
            created = self._draft_store.add_node(
                session_id,
                draft_tree_id,
                child,
                expected_tree_version=tree.version,
            )
            refs.append(TaskRef.draft(created.draft_task_id))
            refs.extend(
                self._add_descendants(
                    session_id,
                    draft_tree_id,
                    created.draft_task_id,
                    child_payload,
                )
            )
        return refs

    def _publish_draft_tree(self, command: PublishDraftTaskTreeCommand) -> _CommandOutput:
        if self._task_publisher is None:
            raise ValueError("task publisher is not configured")
        tree = self._draft_store.get_tree(command.session_id, command.draft_tree_id)
        nodes = self._draft_store.list_nodes(command.session_id, command.draft_tree_id)
        _validate_publish_request(command, nodes)
        if command.expected_version is not None and tree.version != command.expected_version:
            raise ValueError(
                f"stale version for {command.draft_tree_id!r}: "
                f"expected {command.expected_version}, current {tree.version}"
            )
        if self._draft_validator is not None:
            validation = self._draft_validator.validate_tree(tree)
            if not validation.valid:
                details = "; ".join(issue.message for issue in validation.errors)
                raise ValueError(f"draft task tree validation failed: {details}")

        publish_result = self._task_publisher.publish_draft_tree(
            command.session_id,
            command.draft_tree_id,
        )
        _validate_publish_result(command, nodes, publish_result)
        self._draft_store.mark_published(
            command.session_id,
            command.draft_tree_id,
            list(publish_result.mappings),
            expected_version=command.expected_version or tree.version,
        )
        if self._authoring_state_store is not None:
            self._authoring_state_store.mark_published(
                command.session_id,
                command.draft_tree_id,
            )
        root_ids = publish_result.root_task_ids
        return _CommandOutput(
            command_id=command.command_id,
            object_refs=tuple(TaskRef.published(task_id) for task_id in root_ids),
            message_effects=(
                AuthoringMessageEffect(
                    message_type="informational",
                    content="Draft task tree published.",
                    context={
                        "draft_tree_id": command.draft_tree_id,
                        "root_task_ids": list(root_ids),
                        "mapping_count": len(publish_result.mappings),
                        "start_immediately": command.publish_options.start_immediately,
                    },
                ),
            ),
        )

    def _publish_effects(
        self,
        batch: AuthoringCommandBatch,
        effects: tuple[AuthoringMessageEffect, ...],
    ) -> tuple[str, ...]:
        if self._message_bus is None:
            return ()
        emitted: list[str] = []
        for effect in effects:
            message = AgentMessage(
                session_id=batch.session_id,
                task_id=effect.task_id,
                agent_id=batch.actor.actor_id,
                message_type=effect.message_type,
                content=effect.content,
                context=effect.context,
                action_options=list(effect.action_options),
                requires_response=effect.requires_response,
            )
            self._message_bus.publish(message)
            emitted.append(message.message_id)
        return tuple(emitted)

    def _require_raw_task(self, session_id: str, raw_task_id: str | None) -> RawTask:
        if raw_task_id is None:
            raise ValueError("raw_task_id is required")
        raw_task = self._raw_task_store.get(session_id, raw_task_id)
        if raw_task is None:
            raise LookupError(f"RawTask {raw_task_id!r} not found")
        return raw_task

    def _require_raw_version(self, raw_task: RawTask) -> int:
        current = self._raw_task_store.get(raw_task.session_id, raw_task.raw_task_id)
        if current is None:
            raise LookupError(f"RawTask {raw_task.raw_task_id!r} not found")
        return current.version

    def _require_draft_node(self, session_id: str, draft_task_id: str) -> DraftTaskNode:
        node = self._draft_store.get_node(session_id, draft_task_id)
        if node is None:
            raise LookupError(f"DraftTaskNode {draft_task_id!r} not found")
        return node

    def _snapshot(self, batch: AuthoringCommandBatch) -> tuple[object, object] | None:
        if batch.mode != "all_or_nothing":
            return None
        raw_snapshot = _call_snapshot(self._raw_task_store)
        draft_snapshot = _call_snapshot(self._draft_store)
        if (raw_snapshot is None or draft_snapshot is None) and len(batch.commands) > 1:
            raise TaskStoreError(
                "all_or_nothing multi-command batches require snapshot-capable stores"
            )
        return raw_snapshot, draft_snapshot

    def _restore(self, snapshot: tuple[object, object] | None) -> None:
        if snapshot is None:
            return
        raw_snapshot, draft_snapshot = snapshot
        _call_restore(self._raw_task_store, raw_snapshot)
        _call_restore(self._draft_store, draft_snapshot)

    def _remember(
        self,
        idempotency_key: str | None,
        result: AuthoringCommandResult,
    ) -> None:
        if idempotency_key is not None:
            self._idempotency_results[idempotency_key] = result


def _raw_task_from_payload(
    command: MutateRawTaskCommand,
    payload: dict[str, Any],
) -> RawTask:
    return RawTask(
        raw_task_id=payload.get("raw_task_id") or command.raw_task_id or _new_id(),
        session_id=command.session_id,
        source_message_id=_require_str(payload, "source_message_id"),
        user_input=_require_str(payload, "user_input"),
        created_by=payload.get("created_by") or command.actor.actor_id,
        intent_summary=payload.get("intent_summary"),
        constraints=_tuple_payload(payload, "constraints"),
        assumptions=_tuple_payload(payload, "assumptions"),
    )


def _idempotency_key(batch: AuthoringCommandBatch) -> str | None:
    if batch.idempotency_key is not None:
        return batch.idempotency_key
    if len(batch.commands) != 1:
        return None
    command = batch.commands[0]
    return getattr(command, "idempotency_key", None)


def _feasibility_from_payload(payload: dict[str, Any]) -> FeasibilityReport:
    data = payload.get("feasibility", payload)
    return FeasibilityReport.model_validate(data)


def _status_for_feasibility(
    report: FeasibilityReport,
    payload: dict[str, Any],
    current_status: str,
) -> str:
    if "status" in payload:
        return _require_str(payload, "status")
    if report.status in {"ready", "partially_feasible"}:
        return "ready_to_plan"
    if report.status in {"not_supported", "unsafe"}:
        return "rejected"
    return current_status


def _ask_from_payload(raw_task_id: str, payload: dict[str, Any]) -> RawTaskAsk:
    options = tuple(
        RawTaskAnswerOption.model_validate(option)
        for option in payload.get("options", ())
    )
    return RawTaskAsk(
        ask_id=payload.get("ask_id") or _new_id(),
        raw_task_id=raw_task_id,
        question=_require_str(payload, "question"),
        options=options,
        required=bool(payload.get("required", True)),
        reason=_require_str(payload, "reason"),
        created_by=payload.get("created_by") or "collaborator_agent",
    )


def _answer_from_payload(raw_task: RawTask, payload: dict[str, Any]) -> RawTaskAnswer:
    ask_id = _require_str(payload, "ask_id")
    if ask_id not in {ask.ask_id for ask in raw_task.asks}:
        raise ValueError(f"RawTaskAsk {ask_id!r} not found")
    return RawTaskAnswer(
        answer_id=payload.get("answer_id") or _new_id(),
        raw_task_id=raw_task.raw_task_id,
        ask_id=ask_id,
        value=_require_str(payload, "value"),
        source_message_id=_require_str(payload, "source_message_id"),
    )


def _status_after_answers(
    raw_task: RawTask,
    answers: tuple[RawTaskAnswer, ...],
) -> str:
    answered = {answer.ask_id for answer in answers}
    has_unanswered = any(
        ask.required and ask.ask_id not in answered for ask in raw_task.asks
    )
    return "awaiting_user" if has_unanswered else "assessing"


def _root_nodes_from_payload(
    session_id: str,
    payload: dict[str, Any],
) -> list[DraftTaskNode]:
    roots = _required_sequence(payload, "roots")
    return [
        _draft_node_from_payload(session_id, "placeholder", root, order_index=index)
        for index, root in enumerate(roots)
    ]


def _draft_node_from_payload(
    session_id: str,
    draft_tree_id: str,
    payload: object,
    *,
    order_index: int | None = None,
    parent_draft_task_id: str | None = None,
) -> DraftTaskNode:
    if not isinstance(payload, dict):
        raise TypeError("draft node payload must be an object")
    return DraftTaskNode(
        draft_task_id=payload.get("draft_task_id") or _new_id(),
        session_id=session_id,
        draft_tree_id=draft_tree_id,
        parent_draft_task_id=parent_draft_task_id or payload.get("parent_draft_task_id"),
        order_index=(
            order_index
            if order_index is not None
            else int(payload.get("order_index", 0))
        ),
        title=_require_str(payload, "title"),
        intent=_require_str(payload, "intent"),
        required_capability=_require_str(payload, "required_capability"),
        constraints=_tuple_payload(payload, "constraints"),
        rationale=payload.get("rationale"),
        created_by=payload.get("created_by") or "collaborator_agent",
    )


def _message_effect_from_options(
    draft_tree_id: str,
    payload: dict[str, Any],
) -> AuthoringMessageEffect:
    draft_task_id = _require_str(payload, "draft_task_id")
    options = _tuple_payload(payload, "options")
    if not options:
        raise ValueError("attach_options operation requires options")
    return AuthoringMessageEffect(
        message_type="actionable",
        content=payload.get("content") or payload.get("prompt") or "Please choose an option.",
        task_id=draft_task_id,
        context={"draft_tree_id": draft_tree_id, **payload.get("context", {})},
        action_options=options,
        requires_response=True,
    )


def _require_draft_tree_id(command: MutateDraftTaskTreeCommand) -> str:
    if command.draft_tree_id is None:
        raise ValueError("draft_tree_id is required")
    return command.draft_tree_id


def _validate_publish_request(
    command: PublishDraftTaskTreeCommand,
    nodes: list[DraftTaskNode],
) -> None:
    if not nodes:
        raise ValueError("draft task tree has no nodes to publish")
    root_ids = {
        node.draft_task_id for node in nodes if node.parent_draft_task_id is None
    }
    requested_roots = set(command.publish_options.root_draft_task_ids)
    if requested_roots and requested_roots != root_ids:
        raise ValueError("partial root publish is not supported by this boundary")
    for node in nodes:
        if node.status == "published":
            raise ValueError("draft task tree is already published")
        if node.status == "cancelled":
            raise ValueError(f"cannot publish cancelled draft task {node.draft_task_id!r}")
        if node.status != "accepted":
            raise ValueError("draft task tree must be accepted before publish")


def _validate_publish_result(
    command: PublishDraftTaskTreeCommand,
    nodes: list[DraftTaskNode],
    result: TaskPublishResult,
) -> None:
    if result.rejected_task_ids:
        rejected = ", ".join(result.rejected_task_ids)
        raise ValueError(f"task publisher rejected draft tasks: {rejected}")
    if not result.root_task_ids:
        raise ValueError("task publisher returned no root task ids")
    if not result.mappings:
        raise ValueError("task publisher returned no draft-to-published mappings")

    expected_draft_ids = {node.draft_task_id for node in nodes}
    root_draft_ids = {
        node.draft_task_id for node in nodes if node.parent_draft_task_id is None
    }
    seen_draft_ids: set[str] = set()
    mapped_root_task_ids: set[str] = set()
    for mapping in result.mappings:
        if mapping.session_id != command.session_id:
            raise ValueError("publisher mapping session_id does not match command")
        if mapping.draft_tree_id != command.draft_tree_id:
            raise ValueError("publisher mapping draft_tree_id does not match command")
        if mapping.draft_task_id in seen_draft_ids:
            raise ValueError(f"duplicate mapping for draft task {mapping.draft_task_id!r}")
        seen_draft_ids.add(mapping.draft_task_id)
        if mapping.draft_task_id in root_draft_ids:
            mapped_root_task_ids.add(mapping.task_id)
    missing = expected_draft_ids - seen_draft_ids
    extra = seen_draft_ids - expected_draft_ids
    if missing:
        raise ValueError(f"publisher mapping missing draft tasks: {sorted(missing)!r}")
    if extra:
        raise ValueError(f"publisher mapping has unknown draft tasks: {sorted(extra)!r}")
    if mapped_root_task_ids != set(result.root_task_ids):
        raise ValueError("publisher root_task_ids must match mapped root draft tasks")


def _require_current_raw_task(
    raw_task: RawTask | None,
    operation: RawTaskOperation,
) -> RawTask:
    if raw_task is None:
        raise ValueError(f"{operation.op} requires an existing RawTask")
    return raw_task


def _copy_raw_task(raw_task: RawTask, **updates: object) -> RawTask:
    return RawTask.model_validate({**raw_task.model_dump(), **updates})


def _patched_values(
    current: tuple[str, ...],
    *,
    add: tuple[str, ...],
    remove: tuple[str, ...],
) -> tuple[str, ...]:
    removed = set(remove)
    values = [value for value in current if value not in removed]
    for value in add:
        if value not in values:
            values.append(value)
    return tuple(values)


def _tuple_payload(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    values = payload.get(key, ())
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,)
    if not isinstance(values, Iterable):
        raise TypeError(f"{key} must be a string or iterable of strings")
    return tuple(str(value) for value in values if str(value).strip())


def _required_sequence(payload: dict[str, Any], key: str) -> tuple[object, ...]:
    values = payload.get(key)
    if not isinstance(values, list | tuple) or not values:
        raise ValueError(f"{key} must be a non-empty sequence")
    return tuple(values)


def _require_str(payload: dict[str, Any], key: str, *, required: bool = True) -> str:
    value = payload.get(key)
    if value is None:
        if required:
            raise ValueError(f"{key} is required")
        return ""
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    if not value.strip():
        if required:
            raise ValueError(f"{key} must not be blank")
        return ""
    return value


def _command_error(
    command: AuthoringCommand,
    exc: Exception,
) -> AuthoringCommandError:
    if isinstance(exc, LookupError):
        code = "not_found"
    elif isinstance(exc, ValidationError | ValueError | TypeError):
        code = "invalid_command"
    elif isinstance(exc, NotImplementedError):
        code = "not_implemented"
    elif isinstance(exc, TaskStoreError):
        code = "store_error"
    else:
        code = "authoring_error"
    return AuthoringCommandError(
        code=code,
        message=str(exc),
        command_id=command.command_id,
    )


def _call_snapshot(store: object) -> object:
    snapshot = getattr(store, "_snapshot", None)
    if snapshot is None:
        return None
    return snapshot()


def _call_restore(store: object, snapshot: object) -> None:
    restore = getattr(store, "_restore", None)
    if restore is not None:
        restore(snapshot)
