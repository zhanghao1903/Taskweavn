"""UI/API adapter for Collaborator authoring flows.

The adapter is deliberately thin: it turns UI-shaped calls into Collaborator
service or AuthoringCommandService calls, then returns the stable CommandResult
surface. It does not expose raw LLM proposal shapes to callers.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from taskweavn.interaction import AgentMessage, MessageBus
from taskweavn.task.authoring import (
    ActorRef,
    AuthoringCommandBatch,
    AuthoringCommandError,
    AuthoringCommandResult,
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


def _new_id() -> str:
    return uuid4().hex


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

    def generate_task_tree(
        self,
        *,
        session_id: str,
        raw_task_id: str,
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
        template: CollaboratorAgentTemplate | None = None,
        user_actor: ActorRef | None = None,
    ) -> None:
        self._collaborator_service = collaborator_service
        self._command_service = command_service
        self._template_registry = template_registry
        self._message_bus = message_bus
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
    ) -> CommandResult:
        if not content.strip():
            return _rejected("session message content must not be empty")
        message_id = source_message_id or self._publish_user_message(
            session_id=session_id,
            content=content,
            context={"surface": "session", "operation": "appendSessionMessage"},
        )
        result = self._collaborator_service.create_raw_task_from_message(
            session_id=session_id,
            source_message_id=message_id,
            user_input=content,
        )
        return _command_result(
            result,
            accepted_message="session message processed",
            rejected_message="session message rejected",
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
        if not value.strip():
            return _rejected("RawTask answer value must not be empty")
        message_id = source_message_id or self._publish_user_message(
            session_id=session_id,
            content=value,
            context={
                "surface": "raw_task_ask",
                "operation": "answerRawTaskAsk",
                "raw_task_id": raw_task_id,
                "ask_id": ask_id,
            },
        )
        command = MutateRawTaskCommand(
            session_id=session_id,
            raw_task_id=raw_task_id,
            actor=self._user_actor,
            causation_message_id=message_id,
            idempotency_key=idempotency_key,
            operations=(
                RawTaskOperation(
                    op="apply_answer",
                    payload={
                        "ask_id": ask_id,
                        "value": value,
                        "source_message_id": message_id,
                    },
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
            accepted_message="RawTask answer recorded",
            rejected_message="RawTask answer rejected",
        )

    def generate_task_tree(
        self,
        *,
        session_id: str,
        raw_task_id: str,
    ) -> CommandResult:
        result = self._collaborator_service.generate_task_tree(
            session_id=session_id,
            raw_task_id=raw_task_id,
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
        self._publish_user_message(
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
        command = PublishDraftTaskTreeCommand(
            session_id=session_id,
            draft_tree_id=draft_tree_id,
            actor=self._user_actor,
            expected_version=expected_version,
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


def _command_result(
    result: AuthoringCommandResult,
    *,
    accepted_message: str,
    rejected_message: str,
) -> CommandResult:
    if result.ok:
        return CommandResult(
            command_id=result.batch_id or _new_id(),
            status="accepted",
            message=accepted_message,
            affected_task_refs=result.object_refs,
            emitted_message_ids=result.emitted_message_ids,
            published_task_ids=tuple(
                ref.id for ref in result.object_refs if ref.kind == "published"
            ),
        )
    return CommandResult(
        command_id=result.batch_id or _new_id(),
        status="rejected",
        message=f"{rejected_message}: {_error_summary(result.errors)}",
        affected_task_refs=result.object_refs,
        emitted_message_ids=result.emitted_message_ids,
    )


def _rejected(message: str) -> CommandResult:
    return CommandResult(status="rejected", message=message)


def _error_summary(errors: tuple[AuthoringCommandError, ...]) -> str:
    if not errors:
        return "unknown error"
    return "; ".join(error.message for error in errors)


__all__ = [
    "CollaboratorApiAdapter",
    "DefaultCollaboratorApiAdapter",
    "COLLABORATOR_TEMPLATE_ID",
]
