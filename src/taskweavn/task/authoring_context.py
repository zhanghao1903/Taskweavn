"""Read-only authoring context builder for Collaborator calls."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from taskweavn.interaction import AgentMessage, MessageStream
from taskweavn.task.authoring import (
    AuthoringContext,
    CapabilityCatalog,
    CapabilityDescriptor,
    RawTask,
    RawTaskAsk,
)
from taskweavn.task.models import DraftTaskNode, TaskRef
from taskweavn.task.stores import DraftTaskStore, RawTaskStore


@runtime_checkable
class AuthoringContextBuilder(Protocol):
    """Builds read-only context for Collaborator authoring invocations."""

    def build_session_context(
        self,
        session_id: str,
        *,
        raw_task_id: str | None = None,
        message_limit: int | None = None,
    ) -> AuthoringContext: ...

    def build_task_context(
        self,
        session_id: str,
        selected_task_ref: TaskRef,
        *,
        message_limit: int | None = None,
    ) -> AuthoringContext: ...


class DefaultAuthoringContextBuilder:
    """Default deterministic context assembler.

    The builder reads RawTaskStore, DraftTaskStore, MessageStream, and
    CapabilityCatalog. It never writes back to any of them.
    """

    def __init__(
        self,
        *,
        raw_task_store: RawTaskStore,
        draft_store: DraftTaskStore,
        capability_catalog: CapabilityCatalog,
        message_stream: MessageStream | None = None,
        recent_message_limit: int = 50,
        constraints: dict[str, Any] | None = None,
    ) -> None:
        if recent_message_limit < 1:
            raise ValueError("recent_message_limit must be >= 1")
        self._raw_task_store = raw_task_store
        self._draft_store = draft_store
        self._capability_catalog = capability_catalog
        self._message_stream = message_stream
        self._recent_message_limit = recent_message_limit
        self._constraints = dict(constraints or {})

    def build_session_context(
        self,
        session_id: str,
        *,
        raw_task_id: str | None = None,
        message_limit: int | None = None,
    ) -> AuthoringContext:
        raw_tasks = tuple(self._raw_task_store.list_for_session(session_id))
        selected_raw = self._select_raw_task(session_id, raw_task_id, raw_tasks)
        intent = _raw_task_intent(selected_raw)
        return AuthoringContext(
            session_id=session_id,
            mode="session",
            raw_task_id=None if selected_raw is None else selected_raw.raw_task_id,
            feasibility_status=(
                None
                if selected_raw is None or selected_raw.feasibility is None
                else selected_raw.feasibility.status
            ),
            unresolved_asks=(
                () if selected_raw is None else _unresolved_asks(selected_raw)
            ),
            raw_tasks=raw_tasks,
            draft_trees=tuple(self._draft_store.list_trees(session_id)),
            recent_messages=self._session_messages(session_id, message_limit),
            capabilities=self._capabilities_for_intent(intent),
            constraints=self._constraints,
        )

    def build_task_context(
        self,
        session_id: str,
        selected_task_ref: TaskRef,
        *,
        message_limit: int | None = None,
    ) -> AuthoringContext:
        if selected_task_ref.kind != "draft":
            raise ValueError("authoring task context currently supports draft TaskRef only")
        selected_node = self._draft_store.get_node(session_id, selected_task_ref.id)
        if selected_node is None:
            raise LookupError(f"DraftTaskNode {selected_task_ref.id!r} not found")

        raw_tasks = tuple(self._raw_task_store.list_for_session(session_id))
        return AuthoringContext(
            session_id=session_id,
            mode="task",
            raw_tasks=raw_tasks,
            selected_task_ref=selected_task_ref,
            draft_trees=tuple(self._draft_store.list_trees(session_id)),
            selected_node=selected_node,
            ancestors=self._ancestors(session_id, selected_node),
            children=tuple(
                self._draft_store.list_children(
                    session_id,
                    selected_node.draft_tree_id,
                    selected_node.draft_task_id,
                )
            ),
            recent_messages=self._task_messages(session_id, selected_task_ref.id, message_limit),
            capabilities=self._capabilities_for_node(selected_node),
            constraints=self._constraints,
        )

    def _select_raw_task(
        self,
        session_id: str,
        raw_task_id: str | None,
        raw_tasks: tuple[RawTask, ...],
    ) -> RawTask | None:
        if raw_task_id is None:
            return raw_tasks[-1] if raw_tasks else None
        raw_task = self._raw_task_store.get(session_id, raw_task_id)
        if raw_task is None:
            raise LookupError(f"RawTask {raw_task_id!r} not found")
        return raw_task

    def _session_messages(
        self,
        session_id: str,
        limit: int | None,
    ) -> tuple[AgentMessage, ...]:
        if self._message_stream is None:
            return ()
        return tuple(
            self._message_stream.list_for_session(
                session_id,
                limit=limit or self._recent_message_limit,
            )
        )

    def _task_messages(
        self,
        session_id: str,
        task_id: str,
        limit: int | None,
    ) -> tuple[AgentMessage, ...]:
        if self._message_stream is None:
            return ()
        messages = [
            message
            for message in self._message_stream.list_for_task(
                task_id,
                limit=limit or self._recent_message_limit,
            )
            if message.session_id == session_id
        ]
        return tuple(messages)

    def _ancestors(
        self,
        session_id: str,
        selected_node: DraftTaskNode,
    ) -> tuple[DraftTaskNode, ...]:
        ancestors: list[DraftTaskNode] = []
        parent_id = selected_node.parent_draft_task_id
        while parent_id is not None:
            parent = self._draft_store.get_node(session_id, parent_id)
            if parent is None:
                break
            ancestors.append(parent)
            parent_id = parent.parent_draft_task_id
        ancestors.reverse()
        return tuple(ancestors)

    def _capabilities_for_intent(self, intent: str) -> tuple[CapabilityDescriptor, ...]:
        if not intent.strip():
            return self._capability_catalog.all()
        return self._capability_catalog.query(intent, limit=20)

    def _capabilities_for_node(
        self,
        node: DraftTaskNode,
    ) -> tuple[CapabilityDescriptor, ...]:
        descriptors = list(self._capability_catalog.query(node.intent, limit=20))
        required = self._capability_catalog.get(node.required_capability)
        if required is not None and required not in descriptors:
            descriptors.insert(0, required)
        return tuple(descriptors)


def _raw_task_intent(raw_task: RawTask | None) -> str:
    if raw_task is None:
        return ""
    return raw_task.intent_summary or raw_task.user_input


def _unresolved_asks(raw_task: RawTask) -> tuple[RawTaskAsk, ...]:
    unanswered = set(raw_task.unanswered_ask_ids)
    return tuple(ask for ask in raw_task.asks if ask.ask_id in unanswered)
