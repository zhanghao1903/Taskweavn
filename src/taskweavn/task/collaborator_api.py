"""UI/API adapter for Collaborator authoring flows.

The adapter is deliberately thin: it turns UI-shaped calls into Collaborator
service or AuthoringCommandService calls, then returns the stable CommandResult
surface. It does not expose raw LLM proposal shapes to callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from taskweavn.interaction import AgentMessage, MessageBus
from taskweavn.task.authoring import (
    ActorRef,
    AuthoringCommandBatch,
    AuthoringCommandError,
    AuthoringCommandResult,
    DraftTaskTreeOperation,
    MutateDraftTaskTreeCommand,
    MutateRawTaskCommand,
    PublishDraftTaskTreeCommand,
    PublishOptions,
    RawTaskOperation,
)
from taskweavn.task.authoring_service import AuthoringCommandService
from taskweavn.task.collaborator import (
    COLLABORATOR_TEMPLATE_ID,
    CollaboratorAgentTemplate,
    CollaboratorAuthoringService,
    CollaboratorTemplateRegistry,
    default_collaborator_template,
    register_system_collaborator,
)
from taskweavn.task.commands import CommandResult
from taskweavn.task.models import TaskRef
from taskweavn.task.stores import RawTaskStore


def _new_id() -> str:
    return uuid4().hex


@dataclass(frozen=True)
class RawTaskAskAnswerSubmission:
    """One user-submitted answer for a RawTask clarification ask."""

    ask_id: str
    value: str


@runtime_checkable
class CollaboratorApiAdapter(Protocol):
    """Stable UI/server entrypoint for Collaborator authoring operations."""

    def start_session(self, session_id: str) -> CommandResult: ...

    def append_session_message(
        self,
        *,
        session_id: str,
        content: str,
        source_message_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CommandResult: ...

    def answer_raw_task_ask(
        self,
        *,
        session_id: str,
        raw_task_id: str,
        ask_id: str,
        value: str,
        source_message_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CommandResult: ...

    def answer_raw_task_asks(
        self,
        *,
        session_id: str,
        raw_task_id: str,
        answers: tuple[RawTaskAskAnswerSubmission, ...],
        source_message_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CommandResult: ...

    def generate_task_tree(
        self,
        *,
        session_id: str,
        raw_task_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CommandResult: ...

    def append_task_message(
        self,
        *,
        session_id: str,
        task_ref: TaskRef,
        content: str,
    ) -> CommandResult: ...

    def publish_task_tree(
        self,
        *,
        session_id: str,
        draft_tree_id: str,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
        start_immediately: bool = True,
    ) -> CommandResult: ...


class DefaultCollaboratorApiAdapter:
    """Default Collaborator adapter for future HTTP/RPC/UI surfaces."""

    def __init__(
        self,
        *,
        collaborator_service: CollaboratorAuthoringService,
        command_service: AuthoringCommandService,
        template_registry: CollaboratorTemplateRegistry,
        message_bus: MessageBus | None = None,
        raw_task_store: RawTaskStore | None = None,
        template: CollaboratorAgentTemplate | None = None,
        user_actor: ActorRef | None = None,
    ) -> None:
        self._collaborator_service = collaborator_service
        self._command_service = command_service
        self._template_registry = template_registry
        self._message_bus = message_bus
        self._raw_task_store = raw_task_store
        self._template = template or default_collaborator_template()
        self._user_actor = user_actor or ActorRef(
            actor_id="user",
            kind="user",
            display_name="User",
        )

    def start_session(self, session_id: str) -> CommandResult:
        template = register_system_collaborator(
            session_id,
            self._template_registry,
            template=self._template,
        )
        emitted: tuple[str, ...] = ()
        if self._message_bus is not None:
            ready = AgentMessage(
                session_id=session_id,
                agent_id="system",
                message_type="informational",
                content="Collaborator is ready.",
                context={
                    "template_id": template.template_id,
                    "capability": template.capability,
                    "command_protocol": template.command_protocol,
                },
            )
            self._message_bus.publish(ready)
            emitted = (ready.message_id,)
        return CommandResult(
            status="accepted",
            message="collaborator registered",
            emitted_message_ids=emitted,
        )

    def append_session_message(
        self,
        *,
        session_id: str,
        content: str,
        source_message_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CommandResult:
        if not content.strip():
            return _rejected("session message content must not be empty")
        emitted: tuple[str, ...] = ()
        if source_message_id is None:
            message_id = self._publish_user_message(
                session_id=session_id,
                content=content,
                context={"surface": "session", "operation": "appendSessionMessage"},
            )
            emitted = (message_id,)
        else:
            message_id = source_message_id
        result = self._collaborator_service.create_raw_task_from_message(
            session_id=session_id,
            source_message_id=message_id,
            user_input=content,
            idempotency_key=idempotency_key,
        )
        return _command_result(
            result,
            accepted_message="session message processed",
            rejected_message="session message rejected",
            emitted_message_ids=emitted,
        )

    def answer_raw_task_ask(
        self,
        *,
        session_id: str,
        raw_task_id: str,
        ask_id: str,
        value: str,
        source_message_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CommandResult:
        normalized = _validated_answer_submissions(
            (RawTaskAskAnswerSubmission(ask_id=ask_id, value=value),)
        )
        if isinstance(normalized, CommandResult):
            return normalized
        emitted: tuple[str, ...] = ()
        if source_message_id is None:
            raw_task = self._raw_task(session_id, raw_task_id)
            message_id = self._publish_user_message(
                session_id=session_id,
                content=_answer_content_for_display(raw_task, normalized),
                context={
                    "title": "User answer",
                    "surface": "raw_task_ask",
                    "operation": "answerRawTaskAsk",
                    "raw_task_id": raw_task_id,
                    "ask_id": ask_id,
                },
            )
            emitted = (message_id,)
        else:
            message_id = source_message_id
        return self._submit_raw_task_answers(
            session_id=session_id,
            raw_task_id=raw_task_id,
            answers=normalized,
            message_id=message_id,
            idempotency_key=idempotency_key,
            emitted_message_ids=emitted,
            accepted_message="RawTask answer recorded",
            rejected_message="RawTask answer rejected",
        )

    def answer_raw_task_asks(
        self,
        *,
        session_id: str,
        raw_task_id: str,
        answers: tuple[RawTaskAskAnswerSubmission, ...],
        source_message_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CommandResult:
        normalized = _validated_answer_submissions(answers)
        if isinstance(normalized, CommandResult):
            return normalized
        emitted: tuple[str, ...] = ()
        if source_message_id is None:
            raw_task = self._raw_task(session_id, raw_task_id)
            message_id = self._publish_user_message(
                session_id=session_id,
                content=_answer_content_for_display(raw_task, normalized),
                context={
                    "title": "User answer",
                    "surface": "raw_task_ask",
                    "operation": "answerRawTaskAskBatch",
                    "raw_task_id": raw_task_id,
                    "ask_ids": tuple(answer.ask_id for answer in normalized),
                },
            )
            emitted = (message_id,)
        else:
            message_id = source_message_id
        return self._submit_raw_task_answers(
            session_id=session_id,
            raw_task_id=raw_task_id,
            answers=normalized,
            message_id=message_id,
            idempotency_key=idempotency_key,
            emitted_message_ids=emitted,
            accepted_message="RawTask answers recorded",
            rejected_message="RawTask answers rejected",
        )

    def _submit_raw_task_answers(
        self,
        *,
        session_id: str,
        raw_task_id: str,
        answers: tuple[RawTaskAskAnswerSubmission, ...],
        message_id: str,
        idempotency_key: str | None,
        emitted_message_ids: tuple[str, ...],
        accepted_message: str,
        rejected_message: str,
    ) -> CommandResult:
        command = MutateRawTaskCommand(
            session_id=session_id,
            raw_task_id=raw_task_id,
            actor=self._user_actor,
            causation_message_id=message_id,
            idempotency_key=idempotency_key,
            operations=(
                *(
                    RawTaskOperation(
                        op="apply_answer",
                        payload={
                            "ask_id": answer.ask_id,
                            "value": answer.value,
                            "source_message_id": message_id,
                        },
                    )
                    for answer in answers
                ),
            ),
        )
        result = self._command_service.submit(
            AuthoringCommandBatch(
                session_id=session_id,
                actor=self._user_actor,
                causation_message_id=message_id,
                idempotency_key=idempotency_key,
                commands=(command,),
            )
        )
        return _command_result(
            result,
            accepted_message=accepted_message,
            rejected_message=rejected_message,
            emitted_message_ids=emitted_message_ids,
        )

    def generate_task_tree(
        self,
        *,
        session_id: str,
        raw_task_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CommandResult:
        result = self._collaborator_service.generate_task_tree(
            session_id=session_id,
            raw_task_id=raw_task_id,
            idempotency_key=idempotency_key,
        )
        return _command_result(
            result,
            accepted_message="draft task tree generated",
            rejected_message="draft task tree rejected",
        )

    def append_task_message(
        self,
        *,
        session_id: str,
        task_ref: TaskRef,
        content: str,
    ) -> CommandResult:
        if task_ref.kind != "draft":
            return _rejected("Collaborator authoring currently supports draft tasks only")
        if not content.strip():
            return _rejected("task message content must not be empty")
        message_id = self._publish_user_message(
            session_id=session_id,
            content=content,
            task_ref=task_ref,
            context={
                "surface": "task",
                "operation": "appendTaskMessage",
                "task_ref_kind": task_ref.kind,
            },
        )
        result = self._collaborator_service.refine_task_node(
            session_id=session_id,
            selected_task_ref=task_ref,
            instruction=content,
        )
        return _command_result(
            result,
            accepted_message="task message processed",
            rejected_message="task message rejected",
            emitted_message_ids=(message_id,),
        )

    def publish_task_tree(
        self,
        *,
        session_id: str,
        draft_tree_id: str,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
        start_immediately: bool = True,
    ) -> CommandResult:
        key = idempotency_key or _new_id()
        accept_key = f"{key}:accept"
        accept_command = MutateDraftTaskTreeCommand(
            session_id=session_id,
            draft_tree_id=draft_tree_id,
            actor=self._user_actor,
            expected_version=expected_version,
            idempotency_key=accept_key,
            operations=(DraftTaskTreeOperation(op="mark_accepted"),),
        )
        accept_result = self._command_service.submit(
            AuthoringCommandBatch(
                session_id=session_id,
                actor=self._user_actor,
                idempotency_key=accept_key,
                commands=(accept_command,),
            )
        )
        if not accept_result.accepted:
            return _command_result(
                accept_result,
                accepted_message="draft task tree accepted",
                rejected_message="draft task tree accept rejected",
            )

        command = PublishDraftTaskTreeCommand(
            session_id=session_id,
            draft_tree_id=draft_tree_id,
            actor=self._user_actor,
            idempotency_key=key,
            publish_options=PublishOptions(start_immediately=start_immediately),
        )
        result = self._command_service.submit(
            AuthoringCommandBatch(
                session_id=session_id,
                actor=self._user_actor,
                idempotency_key=key,
                commands=(command,),
            )
        )
        return _command_result(
            result,
            accepted_message="draft task tree published",
            rejected_message="draft task tree publish rejected",
        )

    def _publish_user_message(
        self,
        *,
        session_id: str,
        content: str,
        task_ref: TaskRef | None = None,
        context: dict[str, Any],
    ) -> str:
        message = AgentMessage(
            session_id=session_id,
            task_id=None if task_ref is None else task_ref.id,
            agent_id="user",
            message_type="informational",
            content=content,
            context=context,
        )
        if self._message_bus is not None:
            self._message_bus.publish(message)
        return message.message_id

    def _raw_task(self, session_id: str, raw_task_id: str) -> Any | None:
        if self._raw_task_store is None:
            return None
        return self._raw_task_store.get(session_id, raw_task_id)


def _command_result(
    result: AuthoringCommandResult,
    *,
    accepted_message: str,
    rejected_message: str,
    emitted_message_ids: tuple[str, ...] = (),
) -> CommandResult:
    if result.ok:
        return CommandResult(
            command_id=result.batch_id or _new_id(),
            status="accepted",
            message=accepted_message,
            affected_task_refs=result.object_refs,
            emitted_message_ids=_dedupe_ids((*emitted_message_ids, *result.emitted_message_ids)),
            published_task_ids=tuple(
                ref.id for ref in result.object_refs if ref.kind == "published"
            ),
        )
    return CommandResult(
        command_id=result.batch_id or _new_id(),
        status="rejected",
        message=f"{rejected_message}: {_error_summary(result.errors)}",
        affected_task_refs=result.object_refs,
        emitted_message_ids=_dedupe_ids((*emitted_message_ids, *result.emitted_message_ids)),
    )


def _rejected(message: str) -> CommandResult:
    return CommandResult(status="rejected", message=message)


def _validated_answer_submissions(
    answers: tuple[RawTaskAskAnswerSubmission, ...],
) -> tuple[RawTaskAskAnswerSubmission, ...] | CommandResult:
    if not answers:
        return _rejected("RawTask answer batch must include at least one answer")
    normalized: list[RawTaskAskAnswerSubmission] = []
    seen: set[str] = set()
    for answer in answers:
        ask_id = answer.ask_id.strip()
        value = answer.value.strip()
        if not ask_id:
            return _rejected("RawTask answer ask_id must not be empty")
        if not value:
            return _rejected("RawTask answer value must not be empty")
        if ask_id in seen:
            return _rejected(f"RawTask answer batch contains duplicate ask_id {ask_id!r}")
        seen.add(ask_id)
        normalized.append(RawTaskAskAnswerSubmission(ask_id=ask_id, value=value))
    return tuple(normalized)


def _batch_answer_content(answers: tuple[RawTaskAskAnswerSubmission, ...]) -> str:
    if len(answers) == 1:
        return answers[0].value
    return "\n".join(f"{index}. {answer.value}" for index, answer in enumerate(answers, 1))


def _answer_content_for_display(
    raw_task: Any | None,
    answers: tuple[RawTaskAskAnswerSubmission, ...],
) -> str:
    display_answers = tuple(
        RawTaskAskAnswerSubmission(
            ask_id=answer.ask_id,
            value=_answer_value_for_display(raw_task, answer),
        )
        for answer in answers
    )
    return _batch_answer_content(display_answers)


def _answer_value_for_display(
    raw_task: Any | None,
    answer: RawTaskAskAnswerSubmission,
) -> str:
    if raw_task is None:
        return answer.value
    ask = next(
        (candidate for candidate in raw_task.asks if candidate.ask_id == answer.ask_id),
        None,
    )
    if ask is None:
        return answer.value
    for option in ask.options:
        if answer.value in {option.option_id, option.value, option.label}:
            return option.label
    return answer.value


def _error_summary(errors: tuple[AuthoringCommandError, ...]) -> str:
    if not errors:
        return "unknown error"
    return "; ".join(error.message for error in errors)


def _dedupe_ids(ids: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(ids))


__all__ = [
    "CollaboratorApiAdapter",
    "DefaultCollaboratorApiAdapter",
    "RawTaskAskAnswerSubmission",
    "COLLABORATOR_TEMPLATE_ID",
]
