"""Projection helpers for execution ASK UI facts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from taskweavn.interaction import AskRequest, AskStatus, AskStore
from taskweavn.server.ui_contract.view_models import (
    AskListResult,
    AskOptionView,
    AskQuestionView,
    AskRequestView,
    TaskTreeView,
)
from taskweavn.task.models import TaskRef


@runtime_checkable
class AskProjectionService(Protocol):
    def list_asks(
        self,
        session_id: str,
        *,
        statuses: Iterable[AskStatus] | None = None,
        task_id: str | None = None,
        task_tree: TaskTreeView | None = None,
    ) -> AskListResult: ...

    def get_ask(self, session_id: str, ask_id: str) -> AskRequestView | None: ...

    def pending_asks(self, session_id: str) -> tuple[AskRequestView, ...]: ...

    def active_ask(
        self,
        session_id: str,
        *,
        task_tree: TaskTreeView | None = None,
    ) -> AskRequestView | None: ...


class DefaultAskProjectionService:
    """Default read-side projection from durable ASK facts to UI contract facts."""

    def __init__(self, ask_store: AskStore) -> None:
        self._ask_store = ask_store

    def list_asks(
        self,
        session_id: str,
        *,
        statuses: Iterable[AskStatus] | None = None,
        task_id: str | None = None,
        task_tree: TaskTreeView | None = None,
    ) -> AskListResult:
        asks = tuple(
            map_ask_request_view(request)
            for request in self._ask_store.list_for_session(
                session_id,
                statuses=statuses,
                task_id=task_id,
            )
        )
        return AskListResult(
            session_id=session_id,
            asks=asks,
            active_ask=select_active_ask(asks, task_tree=task_tree),
        )

    def get_ask(self, session_id: str, ask_id: str) -> AskRequestView | None:
        request = self._ask_store.get(session_id, ask_id)
        return None if request is None else map_ask_request_view(request)

    def pending_asks(self, session_id: str) -> tuple[AskRequestView, ...]:
        return self.list_asks(session_id, statuses=("pending",)).asks

    def active_ask(
        self,
        session_id: str,
        *,
        task_tree: TaskTreeView | None = None,
    ) -> AskRequestView | None:
        pending = self.pending_asks(session_id)
        return select_active_ask(pending, task_tree=task_tree)


def map_ask_request_view(request: AskRequest) -> AskRequestView:
    task_ref = None if request.task_id is None else TaskRef.published(request.task_id)
    return AskRequestView(
        id=request.ask_id,
        session_id=request.session_id,
        task_node_id=request.task_id,
        task_ref=task_ref,
        question=request.question,
        reason=request.reason,
        questions=tuple(
            AskQuestionView(
                id=question.question_id,
                question=question.question,
                input_hint=question.input_hint,
                required=question.required,
            )
            for question in request.questions
        ),
        suggested_options=tuple(
            AskOptionView(
                id=option.option_id,
                label=option.label,
                description=option.description,
            )
            for option in request.suggested_options
        ),
        answer_type=request.answer_type,
        allow_free_text=request.allow_free_text,
        allow_no_option_with_text=request.allow_no_option_with_text,
        blocking=request.blocking,
        attachments_supported=request.attachments_supported,
        status=request.status,
        answer_id=request.answer_id,
        resume_hint=request.resume_hint,
        created_at=request.created_at,
        answered_at=request.answered_at,
        deferred_at=request.deferred_at,
        cancelled_at=request.cancelled_at,
        expired_at=request.expired_at,
    )


def select_active_ask(
    asks: Iterable[AskRequestView],
    *,
    task_tree: TaskTreeView | None = None,
) -> AskRequestView | None:
    pending = tuple(ask for ask in asks if ask.status == "pending")
    if not pending:
        return None
    if task_tree is not None:
        waiting_task_ids = tuple(
            node.id for node in task_tree.nodes if node.execution == "waiting_for_user"
        )
        for task_id in waiting_task_ids:
            task_candidates = [
                ask for ask in pending if ask.task_node_id == task_id and ask.blocking
            ]
            if task_candidates:
                return sorted(task_candidates, key=lambda ask: (ask.created_at, ask.id))[0]
        return None
    blocking = [ask for ask in pending if ask.blocking]
    candidates = blocking or list(pending)
    return sorted(candidates, key=lambda ask: (ask.created_at, ask.id))[0]


__all__ = [
    "AskProjectionService",
    "DefaultAskProjectionService",
    "map_ask_request_view",
    "select_active_ask",
]
