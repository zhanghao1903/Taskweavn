"""Tests for framework-neutral UI query gateway."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from taskweavn.core import Session
from taskweavn.interaction import AgentMessage
from taskweavn.server.ui_contract import (
    DefaultUiQueryGateway,
    SessionMessageProvider,
    UiQueryGateway,
)
from taskweavn.task import (
    ActiveAuthoringState,
    ConfirmationActionView,
    ConfirmationOptionView,
    SessionMessageView,
    TaskCardView,
    TaskDetailView,
    TaskRef,
    TaskTreeView,
)

NOW = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)


class _SessionReader:
    def __init__(self, sessions: list[Session]) -> None:
        self._sessions = {session.id: session for session in sessions}

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def list(self) -> list[Session]:
        return list(self._sessions.values())


class _Projection:
    def __init__(self, tree: TaskTreeView | Exception) -> None:
        self._tree = tree

    def list_task_tree(
        self,
        session_id: str,
        *,
        root_ref: TaskRef | None = None,
        include_drafts: bool = True,
        include_published: bool = True,
    ) -> TaskTreeView:
        if isinstance(self._tree, Exception):
            raise self._tree
        return self._tree

    def get_task_card(self, session_id: str, task_ref: TaskRef) -> TaskCardView:
        if isinstance(self._tree, Exception):
            raise self._tree
        return self._tree.nodes[0]

    def get_task_detail(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        message_limit: int = 100,
    ) -> TaskDetailView:
        card = self.get_task_card(session_id, task_ref)
        return TaskDetailView(card=card, full_intent=card.intent_preview)


class _SessionMessageProvider:
    def __init__(self, messages: list[AgentMessage]) -> None:
        self._messages = messages

    def list_for_session(
        self,
        session_id: str,
        *,
        limit: int | None = None,
    ) -> list[AgentMessage]:
        messages = [message for message in self._messages if message.session_id == session_id]
        if limit is not None:
            return messages[-limit:]
        return messages


class _AuthoringStateStore:
    def __init__(self, state: ActiveAuthoringState) -> None:
        self._state = state

    def get_active(self, session_id: str) -> ActiveAuthoringState:
        return self._state

    def set_active_raw_task(self, session_id: str, raw_task_id: str) -> None:
        raise NotImplementedError

    def set_active_draft_tree(
        self,
        session_id: str,
        raw_task_id: str | None,
        draft_tree_id: str,
    ) -> None:
        raise NotImplementedError

    def mark_published(self, session_id: str, draft_tree_id: str) -> None:
        raise NotImplementedError


def _session(session_id: str = "session-1", *, status: str = "active") -> Session:
    return Session(
        id=session_id,
        name="Website session",
        workspace_root=Path("/workspace"),
        created_at=NOW,
        last_active_at=NOW,
        status=status,  # type: ignore[arg-type]
    )


def _card(
    task_id: str = "root",
    *,
    message: SessionMessageView | None = None,
    confirmation: ConfirmationActionView | None = None,
) -> TaskCardView:
    ref = TaskRef.published(task_id)
    return TaskCardView(
        task_ref=ref,
        root_ref=ref,
        title="Build website",
        intent_preview="Build a personal website",
        status="pending",
        latest_message=message,
        confirmation=confirmation,
    )


def _draft_card(task_id: str = "draft-1") -> TaskCardView:
    ref = TaskRef.draft(task_id)
    return TaskCardView(
        task_ref=ref,
        root_ref=ref,
        title="Draft website plan",
        intent_preview="Draft a personal website",
        status="draft",
    )


def test_query_gateway_protocol_conformance() -> None:
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(TaskTreeView(session_id="session-1")),
    )

    assert isinstance(gateway, UiQueryGateway)
    assert isinstance(_SessionMessageProvider([]), SessionMessageProvider)


def test_get_session_snapshot_returns_not_found_envelope() -> None:
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([]),
        task_projection=_Projection(TaskTreeView(session_id="missing")),
    )

    response = gateway.get_session_snapshot("missing", request_id="request-1")

    assert response.request_id == "request-1"
    assert response.ok is False
    assert response.data is None
    assert response.error is not None
    assert response.error.code == "not_found"


def test_get_session_snapshot_maps_project_workflow_tree_messages_and_confirmations() -> None:
    message = SessionMessageView(
        message_id="message-1",
        session_id="session-1",
        task_ref=TaskRef.published("root"),
        message_type="user",
        content_summary="Make the homepage quieter.",
    )
    option = ConfirmationOptionView(
        option_id="yes-option",
        label="Yes",
        value="yes",
        is_default=True,
    )
    confirmation = ConfirmationActionView(
        confirmation_id="confirmation-1",
        task_ref=TaskRef.published("root"),
        prompt="Proceed?",
        options=(option,),
        default_option_id="yes-option",
    )
    tree = TaskTreeView(
        session_id="session-1",
        nodes=(_card(message=message, confirmation=confirmation),),
    )
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(tree),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.cursor == "snapshot:session-1:2026-05-20T12:00:00+00:00"
    assert response.data.project.id == "local"
    assert response.data.workflow.id == "task_authoring"
    assert response.data.session.status == "waiting_user"
    assert response.data.task_tree is not None
    assert response.data.task_tree.nodes[0].status == "waiting_user"
    assert response.data.messages[0].id == "message-1"
    assert response.data.pending_confirmations[0].default_option_value == "yes"


def test_empty_tree_snapshot_has_no_task_tree_and_new_session_status() -> None:
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(TaskTreeView(session_id="session-1")),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.task_tree is None
    assert response.data.messages == ()
    assert response.data.pending_confirmations == ()
    assert response.data.session.status == "new"


def test_get_session_snapshot_includes_session_level_messages_without_task_tree() -> None:
    message = AgentMessage(
        message_id="message-user",
        session_id="session-1",
        agent_id="user",
        message_type="informational",
        content="Build a quiet personal website.",
        created_at=NOW,
    )
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(TaskTreeView(session_id="session-1")),
        session_message_provider=_SessionMessageProvider([message]),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.task_tree is None
    assert response.data.messages[0].id == "message-user"
    assert response.data.messages[0].kind == "informational"
    assert response.data.messages[0].title == "User message"
    assert response.data.messages[0].body == "Build a quiet personal website."
    assert response.data.session.status == "understanding"


def test_get_session_snapshot_uses_active_draft_tree_id_for_draft_task_tree() -> None:
    tree = TaskTreeView(session_id="session-1", nodes=(_draft_card(),))
    state_store = _AuthoringStateStore(
        ActiveAuthoringState(
            session_id="session-1",
            active_raw_task_id="raw-1",
            active_draft_tree_id="tree-active",
            active_state="draft_tree",
        )
    )
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(tree),
        authoring_state_store=state_store,
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.task_tree is not None
    assert response.data.task_tree.id == "tree-active"


def test_query_gateway_converts_unexpected_errors_to_internal_error() -> None:
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(RuntimeError("projection exploded")),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "internal_error"
    assert response.error.details["error_type"] == "RuntimeError"
