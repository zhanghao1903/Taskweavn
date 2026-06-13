"""Tests for framework-neutral UI query gateway."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from taskweavn.core import Session, SqliteEventStream, WorkspaceLayout
from taskweavn.interaction import AgentMessage, AskQuestion, AskRequest, InMemoryAskStore
from taskweavn.observability.models import LogArchiveManifest
from taskweavn.server.ui_contract import (
    AuditConfigProvider,
    AuditDisclosure,
    AuditEventProvider,
    AuditLogProvider,
    AuditRecord,
    DefaultUiQueryGateway,
    EvidenceRef,
    PayloadDisclosureResult,
    SessionMessageProvider,
    UiQueryGateway,
    WorkspaceAuditConfigProvider,
    WorkspaceAuditEventProvider,
    WorkspaceAuditLogProvider,
)
from taskweavn.server.ui_contract.ask_projection import DefaultAskProjectionService
from taskweavn.task import (
    ActiveAuthoringState,
    ConfirmationActionView,
    ConfirmationOptionView,
    FeasibilityReport,
    InMemoryRawTaskStore,
    Plan,
    PlanTaskNode,
    RawTask,
    RawTaskAnswerOption,
    RawTaskAsk,
    SessionMessageView,
    TaskCardBadges,
    TaskCardView,
    TaskDetailView,
    TaskFileChangeSummary,
    TaskRef,
    TaskSummaryView,
    TaskTreeView,
)
from taskweavn.tools.fs import FileContentObservation, ReadFileAction, WriteFileAction

NOW = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)


class _SessionReader:
    def __init__(self, sessions: list[Session]) -> None:
        self._sessions = {session.id: session for session in sessions}

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def list(self) -> list[Session]:
        return list(self._sessions.values())


class _SnapshotCursorProvider:
    def __init__(self, cursor: str | None) -> None:
        self._cursor = cursor

    def latest_cursor(self, session_id: str) -> str | None:
        del session_id
        return self._cursor


class _Projection:
    def __init__(
        self,
        tree: TaskTreeView | Exception,
        *,
        details: dict[str, TaskDetailView] | None = None,
    ) -> None:
        self._tree = tree
        self._details = details or {}

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
        if task_ref.id in self._details:
            return self._details[task_ref.id]
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
        *,
        active_plan_id: str | None = None,
    ) -> None:
        raise NotImplementedError

    def mark_published(self, session_id: str, draft_tree_id: str) -> None:
        raise NotImplementedError

    def cancel_active(self, session_id: str) -> None:
        self._state = ActiveAuthoringState(
            session_id=session_id,
            active_raw_task_id=self._state.active_raw_task_id,
            active_draft_tree_id=self._state.active_draft_tree_id,
            active_plan_id=self._state.active_plan_id,
            active_state="cancelled",
        )


class _PlanStore:
    def __init__(
        self,
        *,
        active_plan: Plan | None = None,
        task_nodes: Sequence[PlanTaskNode] = (),
    ) -> None:
        self._active_plan = active_plan
        self._plans = (
            {(active_plan.session_id, active_plan.plan_id): active_plan}
            if active_plan is not None
            else {}
        )
        self._task_nodes = {
            (node.session_id, node.plan_id): list(task_nodes) for node in task_nodes
        }

    def create_plan(
        self,
        plan: Plan,
        task_nodes: Sequence[PlanTaskNode] = (),
    ) -> Plan:
        raise NotImplementedError

    def get_plan(self, session_id: str, plan_id: str) -> Plan | None:
        return self._plans.get((session_id, plan_id))

    def list_plans(self, session_id: str) -> list[Plan]:
        return [plan for plan in self._plans.values() if plan.session_id == session_id]

    def get_active_plan(self, session_id: str) -> Plan | None:
        if self._active_plan is not None and self._active_plan.session_id == session_id:
            return self._active_plan
        return None

    def save_plan(self, plan: Plan, *, expected_version: int) -> Plan:
        raise NotImplementedError

    def get_task_node(self, session_id: str, task_node_id: str) -> PlanTaskNode | None:
        for nodes in self._task_nodes.values():
            for node in nodes:
                if node.session_id == session_id and node.task_node_id == task_node_id:
                    return node
        return None

    def list_task_nodes(self, session_id: str, plan_id: str) -> list[PlanTaskNode]:
        if (session_id, plan_id) not in self._plans:
            raise LookupError(f"Plan {plan_id!r} not found")
        return list(self._task_nodes.get((session_id, plan_id), []))

    def add_task_node(
        self,
        node: PlanTaskNode,
        *,
        expected_plan_version: int | None = None,
    ) -> PlanTaskNode:
        raise NotImplementedError

    def save_task_node(
        self,
        node: PlanTaskNode,
        *,
        expected_version: int,
    ) -> PlanTaskNode:
        raise NotImplementedError


def _session(
    session_id: str = "session-1",
    *,
    status: str = "active",
    workspace_root: Path | None = None,
) -> Session:
    return Session(
        id=session_id,
        name="Website session",
        workspace_root=workspace_root or Path("/workspace"),
        created_at=NOW,
        last_active_at=NOW,
        status=status,  # type: ignore[arg-type]
    )


def _card(
    task_id: str = "root",
    *,
    message: SessionMessageView | None = None,
    confirmation: ConfirmationActionView | None = None,
    status: str = "pending",
    result_ref: str | None = None,
    error_ref: str | None = None,
    badges: TaskCardBadges | None = None,
    parent_ref: TaskRef | None = None,
    root_ref: TaskRef | None = None,
    depth: int = 0,
) -> TaskCardView:
    ref = TaskRef.published(task_id)
    return TaskCardView(
        task_ref=ref,
        parent_ref=parent_ref,
        root_ref=root_ref or ref,
        title="Build website",
        intent_preview="Build a personal website",
        status=status,  # type: ignore[arg-type]
        depth=depth,
        result_ref=result_ref,
        error_ref=error_ref,
        badges=badges or TaskCardBadges(),
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


def _awaiting_raw_task() -> RawTask:
    return RawTask(
        raw_task_id="raw-1",
        session_id="session-1",
        source_message_id="message-1",
        user_input="How do I publish a website?",
        status="awaiting_user",
        intent_summary="Understand how to publish a website.",
        feasibility=FeasibilityReport(
            status="needs_clarification",
            confidence=0.6,
            missing_inputs=("website type",),
        ),
        asks=(
            RawTaskAsk(
                ask_id="ask-1",
                raw_task_id="raw-1",
                question="What type of website do you want to publish?",
                reason="Different website types have different publishing paths.",
                options=(
                    RawTaskAnswerOption(label="Static", value="static"),
                    RawTaskAnswerOption(label="Dynamic", value="dynamic"),
                ),
            ),
        ),
    )


def test_query_gateway_protocol_conformance() -> None:
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(TaskTreeView(session_id="session-1")),
    )

    assert isinstance(gateway, UiQueryGateway)
    assert isinstance(_SessionMessageProvider([]), SessionMessageProvider)
    assert isinstance(
        WorkspaceAuditEventProvider(WorkspaceLayout(Path("/workspace"))),
        AuditEventProvider,
    )
    assert isinstance(WorkspaceAuditConfigProvider(), AuditConfigProvider)
    assert isinstance(WorkspaceAuditLogProvider(), AuditLogProvider)


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
    assert response.data.active_plan is not None
    assert response.data.active_plan.id == "plan:legacy:session-1"
    assert response.data.active_plan.source_kind == "legacy_published_task_tree"
    assert response.data.active_plan.task_node_ids == ("root",)
    assert response.data.active_plan.task_nodes[0].task_index == "1"
    assert response.data.task_tree is not None
    assert response.data.task_tree == response.data.active_plan.task_tree_projection
    assert response.data.task_tree.nodes[0].plan_id == "plan:legacy:session-1"
    assert response.data.task_tree.nodes[0].status == "waiting_user"
    assert response.data.messages[0].id == "message-1"
    assert response.data.pending_confirmations[0].default_option_value == "yes"


def test_get_session_snapshot_prefers_active_stored_plan_over_legacy_projection() -> None:
    tree = TaskTreeView(session_id="session-1", nodes=(_draft_card("draft-legacy"),))
    plan = Plan(
        plan_id="plan-stored",
        session_id="session-1",
        source_draft_tree_id="draft-tree-1",
        title="Stored plan",
        objective="Use durable plan facts.",
        summary="Stored durable plan summary.",
        status="approved",
    )
    plan_node = PlanTaskNode(
        task_node_id="node-stored",
        plan_id=plan.plan_id,
        session_id="session-1",
        task_index="1",
        title="Stored task",
        intent="Use stored PlanTaskNode.",
        summary="Stored task summary.",
        readiness="approved",
        draft_ref=TaskRef.draft("draft-stored"),
    )
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(tree),
        authoring_state_store=_AuthoringStateStore(
            ActiveAuthoringState(
                session_id="session-1",
                active_draft_tree_id="draft-tree-1",
                active_plan_id=plan.plan_id,
                active_state="draft_tree",
            )
        ),
        plan_store=_PlanStore(active_plan=plan, task_nodes=(plan_node,)),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.active_plan is not None
    assert response.data.active_plan.id == "plan-stored"
    assert response.data.active_plan.source_kind == "plan_store"
    assert response.data.active_plan.status == "ready_to_publish"
    assert response.data.active_plan.task_node_ids == ("node-stored",)
    assert response.data.task_tree is response.data.active_plan.task_tree_projection
    assert response.data.task_tree is not None
    assert response.data.task_tree.id == "draft-tree-1"
    assert response.data.task_tree.nodes[0].id == "node-stored"


def test_get_session_snapshot_uses_latest_ui_event_cursor_when_available() -> None:
    tree = TaskTreeView(session_id="session-1", nodes=(_card(),))
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(tree),
        snapshot_cursor_provider=_SnapshotCursorProvider("event:session-1:42"),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.cursor == "event:session-1:42"
    assert response.data is not None
    assert response.data.cursor == "event:session-1:42"


def test_get_session_snapshot_marks_ask_waiting_execution_as_waiting_user() -> None:
    tree = TaskTreeView(
        session_id="session-1",
        nodes=(_card(status="waiting_for_user"),),
    )
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(tree),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.session.status == "waiting_user"
    assert response.data.task_tree is not None
    assert response.data.task_tree.nodes[0].status == "waiting_user"
    assert response.data.task_tree.nodes[0].execution == "waiting_for_user"
    assert response.data.pending_confirmations == ()


def test_get_session_snapshot_includes_pending_asks_and_active_ask() -> None:
    tree = TaskTreeView(
        session_id="session-1",
        nodes=(_card(status="waiting_for_user"),),
    )
    ask_store = InMemoryAskStore(
        [
            AskRequest(
                ask_id="ask-1",
                session_id="session-1",
                task_id="root",
                question="Which deployment target should be used?",
                reason="The agent needs a user-owned deployment decision.",
                questions=(
                    AskQuestion(
                        question_id="role",
                        question="What is your professional role?",
                    ),
                    AskQuestion(
                        question_id="goal",
                        question="What is the main goal?",
                        input_hint="Find work, attract clients, build a brand...",
                    ),
                ),
            )
        ]
    )
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(tree),
        ask_projection=DefaultAskProjectionService(ask_store),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.session.status == "waiting_user"
    assert response.data.pending_asks[0].id == "ask-1"
    assert [question.id for question in response.data.pending_asks[0].questions] == [
        "role",
        "goal",
    ]
    assert response.data.active_ask is not None
    assert response.data.active_ask.id == "ask-1"
    assert response.data.active_ask.questions[1].input_hint == (
        "Find work, attract clients, build a brand..."
    )


def test_list_and_get_asks_use_ask_projection() -> None:
    ask_store = InMemoryAskStore(
        [
            AskRequest(
                ask_id="ask-1",
                session_id="session-1",
                task_id="root",
                question="Which deployment target should be used?",
                reason="The agent needs a user-owned deployment decision.",
            )
        ]
    )
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(TaskTreeView(session_id="session-1")),
        ask_projection=DefaultAskProjectionService(ask_store),
    )

    listed = gateway.list_asks("session-1", status="pending", task_node_id="root")
    detail = gateway.get_ask("session-1", "ask-1")

    assert listed.ok is True
    assert listed.data is not None
    assert listed.data.asks[0].id == "ask-1"
    assert listed.data.active_ask is not None
    assert listed.data.active_ask.id == "ask-1"
    assert detail.ok is True
    assert detail.data is not None
    assert detail.data.id == "ask-1"


def test_list_asks_rejects_unsupported_status_filter() -> None:
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(TaskTreeView(session_id="session-1")),
        ask_projection=DefaultAskProjectionService(InMemoryAskStore()),
    )

    response = gateway.list_asks("session-1", status="paused")

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "bad_request"


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


def test_get_session_snapshot_projects_authoring_planning_ask() -> None:
    raw_task = _awaiting_raw_task()
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(TaskTreeView(session_id="session-1")),
        authoring_state_store=_AuthoringStateStore(
            ActiveAuthoringState(
                session_id="session-1",
                active_raw_task_id=raw_task.raw_task_id,
                active_state="raw_task",
            )
        ),
        raw_task_store=InMemoryRawTaskStore([raw_task]),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.session.status == "waiting_user"
    assert response.data.task_tree is None
    assert response.data.planning is not None
    assert response.data.planning.state == "awaiting_user"
    assert response.data.planning.source_raw_task_id == "raw-1"
    assert response.data.planning.asks[0].id == "ask-1"
    assert response.data.planning.asks[0].options[0].value == "static"
    dumped = response.data.model_dump(mode="json")
    assert dumped["planning"]["sourceRawTaskId"] == "raw-1"


def test_get_session_snapshot_supersedes_authoring_ask_when_task_tree_exists() -> None:
    raw_task = _awaiting_raw_task()
    tree = TaskTreeView(session_id="session-1", nodes=(_draft_card(),))
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(tree),
        authoring_state_store=_AuthoringStateStore(
            ActiveAuthoringState(
                session_id="session-1",
                active_raw_task_id=raw_task.raw_task_id,
                active_draft_tree_id="tree-active",
                active_state="draft_tree",
            )
        ),
        raw_task_store=InMemoryRawTaskStore([raw_task]),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.session.status == "draft_ready"
    assert response.data.task_tree is not None
    assert response.data.task_tree.id == "tree-active"
    assert response.data.planning is not None
    assert response.data.planning.state == "draft_ready"
    assert response.data.planning.asks[0].id == "ask-1"
    assert response.data.planning.asks[0].status == "superseded"


def test_get_session_snapshot_diagnoses_dirty_authoring_state() -> None:
    raw_task = _awaiting_raw_task()
    tree = TaskTreeView(session_id="session-1", nodes=(_draft_card(),))
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(tree),
        authoring_state_store=_AuthoringStateStore(
            ActiveAuthoringState(
                session_id="session-1",
                active_raw_task_id=raw_task.raw_task_id,
                active_state="raw_task",
            )
        ),
        raw_task_store=InMemoryRawTaskStore([raw_task]),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.task_tree is not None
    assert response.data.planning is not None
    assert response.data.planning.asks[0].status == "superseded"
    assert response.data.planning.diagnostics[0].code == "dirty_authoring_state"
    assert response.data.planning.diagnostics[0].severity == "warning"


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


def test_get_session_snapshot_prefers_rich_session_message_over_tree_latest() -> None:
    tree_message = SessionMessageView(
        message_id="message-execution",
        session_id="session-1",
        task_ref=TaskRef.published("root"),
        message_type="agent",
        content_summary="Task completed.",
        created_at=NOW,
    )
    rich_message = AgentMessage(
        message_id="message-execution",
        session_id="session-1",
        task_id="root",
        agent_id="agent",
        message_type="informational",
        content="Task completed.",
        context={
            "task_ref_kind": "published",
            "title": "Task completed",
        },
        created_at=NOW,
    )
    tree = TaskTreeView(session_id="session-1", nodes=(_card(message=tree_message),))
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(tree),
        session_message_provider=_SessionMessageProvider([rich_message]),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert len(response.data.messages) == 1
    assert response.data.messages[0].id == "message-execution"
    assert response.data.messages[0].title == "Task completed"
    assert response.data.messages[0].task_ref == TaskRef.published("root")


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


def test_get_session_snapshot_projects_result_card_for_terminal_task() -> None:
    card = _card(status="done", result_ref="result:root")
    summary = TaskSummaryView(
        task_ref=TaskRef.published("root"),
        summary="Built the requested site.",
    )
    tree = TaskTreeView(session_id="session-1", nodes=(card,))
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(
            tree,
            details={
                "root": TaskDetailView(
                    card=card,
                    full_intent=card.intent_preview,
                    result_summary=summary,
                )
            },
        ),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.result is not None
    assert response.data.result.task_node_id == "root"
    assert response.data.result.summary == "Built the requested site."


def test_get_session_snapshot_routes_result_through_stored_plan_task_node() -> None:
    card = _card("published-task", status="done", result_ref="result:published-task")
    summary = TaskSummaryView(
        task_ref=TaskRef.published("published-task"),
        summary="Built the durable plan task.",
    )
    plan = Plan(
        plan_id="plan-stored",
        session_id="session-1",
        title="Stored plan",
        objective="Use durable plan facts.",
        summary="Stored durable plan summary.",
        status="running",
    )
    plan_node = PlanTaskNode(
        task_node_id="node-stored",
        plan_id=plan.plan_id,
        session_id="session-1",
        task_index="1",
        title="Stored task",
        intent="Use stored PlanTaskNode.",
        summary="Stored task summary.",
        readiness="published",
        execution="done",
        published_ref=TaskRef.published("published-task"),
        result_ref="result:published-task",
    )
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(
            TaskTreeView(session_id="session-1"),
            details={
                "published-task": TaskDetailView(
                    card=card,
                    full_intent=card.intent_preview,
                    result_summary=summary,
                )
            },
        ),
        plan_store=_PlanStore(active_plan=plan, task_nodes=(plan_node,)),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.result is not None
    assert response.data.result.task_node_id == "node-stored"
    assert response.data.result.summary == "Built the durable plan task."


def test_get_session_snapshot_projects_file_change_summary_from_task_detail() -> None:
    card = _card(
        status="done",
        badges=TaskCardBadges(subtree_file_change_count=1),
    )
    change = TaskFileChangeSummary(
        change_id="change-1",
        owner_task_ref=TaskRef.published("root"),
        path="src/App.tsx",
        change_type="modified",
        summary="Modified src/App.tsx (12 bytes written).",
        recorded_at=NOW,
    )
    tree = TaskTreeView(session_id="session-1", nodes=(card,))
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(
            tree,
            details={
                "root": TaskDetailView(
                    card=card,
                    full_intent=card.intent_preview,
                    file_changes=(change,),
                )
            },
        ),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.file_change_summary is not None
    assert response.data.file_change_summary.task_node_id == "root"
    assert response.data.file_change_summary.recursive is True
    assert response.data.file_change_summary.summary == "1 file changed."
    assert response.data.file_change_summary.changed_files[0].path == "src/App.tsx"


def test_get_session_snapshot_routes_file_changes_through_stored_plan_task_node() -> None:
    card = _card("published-task", status="done")
    change = TaskFileChangeSummary(
        change_id="change-1",
        owner_task_ref=TaskRef.published("published-task"),
        path="src/App.tsx",
        change_type="modified",
        summary="Modified src/App.tsx (12 bytes written).",
        recorded_at=NOW,
    )
    plan = Plan(
        plan_id="plan-stored",
        session_id="session-1",
        title="Stored plan",
        objective="Use durable plan facts.",
        summary="Stored durable plan summary.",
        status="running",
    )
    plan_node = PlanTaskNode(
        task_node_id="node-stored",
        plan_id=plan.plan_id,
        session_id="session-1",
        task_index="1",
        title="Stored task",
        intent="Use stored PlanTaskNode.",
        summary="Stored task summary.",
        readiness="published",
        execution="done",
        published_ref=TaskRef.published("published-task"),
        file_summary_ref="files:published-task",
    )
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(
            TaskTreeView(session_id="session-1"),
            details={
                "published-task": TaskDetailView(
                    card=card,
                    full_intent=card.intent_preview,
                    file_changes=(change,),
                )
            },
        ),
        plan_store=_PlanStore(active_plan=plan, task_nodes=(plan_node,)),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.file_change_summary is not None
    assert response.data.file_change_summary.task_node_id == "node-stored"
    assert response.data.file_change_summary.recursive is True
    assert response.data.file_change_summary.changed_files[0].owner_task_node_id == (
        "node-stored"
    )
    assert response.data.file_change_summary.changed_files[0].path == "src/App.tsx"


def test_get_session_snapshot_prefers_root_file_change_summary_for_child_changes() -> None:
    root_ref = TaskRef.published("root")
    root_card = _card(
        "root",
        status="done",
        badges=TaskCardBadges(subtree_file_change_count=1),
    )
    child_card = _card(
        "child",
        status="done",
        parent_ref=root_ref,
        root_ref=root_ref,
        depth=1,
        badges=TaskCardBadges(
            direct_file_change_count=1,
            subtree_file_change_count=1,
        ),
    )
    child_change = TaskFileChangeSummary(
        change_id="change-child",
        owner_task_ref=TaskRef.published("child"),
        path="src/Child.tsx",
        change_type="created",
        summary="Created src/Child.tsx (8 bytes written).",
        recorded_at=NOW,
        from_subtree=True,
    )
    tree = TaskTreeView(session_id="session-1", nodes=(root_card, child_card))
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(
            tree,
            details={
                "root": TaskDetailView(
                    card=root_card,
                    full_intent=root_card.intent_preview,
                    file_changes=(child_change,),
                )
            },
        ),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is True
    assert response.data is not None
    assert response.data.file_change_summary is not None
    assert response.data.file_change_summary.task_node_id == "root"
    assert response.data.file_change_summary.changed_files[0].owner_task_node_id == ("child")


def test_get_audit_snapshot_projects_task_scope_records_and_detail() -> None:
    message = SessionMessageView(
        message_id="message-1",
        session_id="session-1",
        task_ref=TaskRef.published("root"),
        message_type="agent",
        content_summary="Implementation completed.",
        created_at=NOW,
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
        prompt="Create project files?",
        options=(option,),
        default_option_id="yes-option",
    )
    card = _card(
        status="done",
        message=message,
        confirmation=confirmation,
        result_ref="result:root",
        badges=TaskCardBadges(direct_file_change_count=1, subtree_file_change_count=1),
    )
    change = TaskFileChangeSummary(
        change_id="change-1",
        owner_task_ref=TaskRef.published("root"),
        path="src/App.tsx",
        change_type="modified",
        summary="Modified src/App.tsx.",
        recorded_at=NOW,
    )
    summary = TaskSummaryView(
        task_ref=TaskRef.published("root"),
        summary="Built the requested page.",
        updated_at=NOW,
    )
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(
            TaskTreeView(session_id="session-1", nodes=(card,)),
            details={
                "root": TaskDetailView(
                    card=card,
                    full_intent=card.intent_preview,
                    file_changes=(change,),
                    result_summary=summary,
                )
            },
        ),
    )

    response = gateway.get_audit_snapshot(
        "session-1",
        task_node_id="root",
        filter_kind="files",
        record_id="record-file-change-1",
        include_detail=True,
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.schema_version == "plato.audit.v1"
    assert response.data.scope.kind == "task"
    assert response.data.selected_task is not None
    assert response.data.selected_task.id == "root"
    assert [record.id for record in response.data.records] == ["record-file-change-1"]
    assert response.data.selected_record is not None
    assert response.data.selected_record.id == "record-file-change-1"
    assert response.data.selected_record.evidence[0].id == "evidence-record-file-change-1"
    assert response.data.overview.record_counts["confirmations"] == 1
    assert response.data.overview.record_counts["files"] == 1
    assert response.data.page_state.kind == "partial"


def test_get_audit_snapshot_routes_selected_task_through_stored_plan_task_node() -> None:
    card = _card(
        "published-task",
        status="done",
        badges=TaskCardBadges(direct_file_change_count=1, subtree_file_change_count=1),
    )
    change = TaskFileChangeSummary(
        change_id="change-1",
        owner_task_ref=TaskRef.published("published-task"),
        path="src/App.tsx",
        change_type="modified",
        summary="Modified src/App.tsx.",
        recorded_at=NOW,
    )
    plan = Plan(
        plan_id="plan-stored",
        session_id="session-1",
        title="Stored plan",
        objective="Use durable plan facts.",
        summary="Stored durable plan summary.",
        status="running",
    )
    plan_node = PlanTaskNode(
        task_node_id="node-stored",
        plan_id=plan.plan_id,
        session_id="session-1",
        task_index="1",
        title="Stored task",
        intent="Use stored PlanTaskNode.",
        summary="Stored task summary.",
        readiness="published",
        execution="done",
        published_ref=TaskRef.published("published-task"),
        file_summary_ref="files:published-task",
    )
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(
            TaskTreeView(session_id="session-1", nodes=(card,)),
            details={
                "published-task": TaskDetailView(
                    card=card,
                    full_intent=card.intent_preview,
                    file_changes=(change,),
                )
            },
        ),
        plan_store=_PlanStore(active_plan=plan, task_nodes=(plan_node,)),
    )

    response = gateway.get_audit_snapshot(
        "session-1",
        task_node_id="node-stored",
        filter_kind="files",
        record_id="record-file-change-1",
        include_detail=True,
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.scope.kind == "task"
    assert response.data.scope.task_node_id == "node-stored"
    assert response.data.entry_context.task_node_id == "node-stored"
    assert response.data.return_target.task_node_id == "node-stored"
    assert response.data.selected_task is not None
    assert response.data.selected_task.id == "node-stored"
    assert response.data.selected_task.task_ref == TaskRef.published("published-task")
    assert [record.id for record in response.data.records] == ["record-file-change-1"]
    assert response.data.records[0].task_node_id == "node-stored"
    assert response.data.records[0].task_ref == TaskRef.published("published-task")
    assert response.data.records[0].scope.kind == "file"
    assert response.data.records[0].scope.task_node_id == "node-stored"
    assert response.data.selected_record is not None
    assert response.data.selected_record.id == "record-file-change-1"
    assert response.data.selected_record.task_node_id == "node-stored"
    assert response.data.selected_record.task_ref == TaskRef.published("published-task")
    assert response.data.related_logs[0].filters["taskNodeId"] == "node-stored"


def test_audit_non_snapshot_queries_use_stored_plan_task_node_identity() -> None:
    card = _card(
        "published-task",
        status="done",
        badges=TaskCardBadges(direct_file_change_count=1, subtree_file_change_count=1),
    )
    change = TaskFileChangeSummary(
        change_id="change-1",
        owner_task_ref=TaskRef.published("published-task"),
        path="src/App.tsx",
        change_type="modified",
        summary="Modified src/App.tsx.",
        recorded_at=NOW,
    )
    plan = Plan(
        plan_id="plan-stored",
        session_id="session-1",
        title="Stored plan",
        objective="Use durable plan facts.",
        summary="Stored durable plan summary.",
        status="running",
    )
    plan_node = PlanTaskNode(
        task_node_id="node-stored",
        plan_id=plan.plan_id,
        session_id="session-1",
        task_index="1",
        title="Stored task",
        intent="Use stored PlanTaskNode.",
        summary="Stored task summary.",
        readiness="published",
        execution="done",
        published_ref=TaskRef.published("published-task"),
        file_summary_ref="files:published-task",
    )

    class _DisclosureSpy:
        def __init__(self) -> None:
            self.evidence_record_task_node_id: str | None = None

        def build_record_payload(
            self,
            record: AuditRecord,
            *,
            session: Session,
            include_sanitized_payload: bool,
        ) -> PayloadDisclosureResult:
            del session, include_sanitized_payload
            return PayloadDisclosureResult(disclosure=AuditDisclosure())

        def build_evidence_payload(
            self,
            record: AuditRecord,
            evidence_ref: EvidenceRef,
            *,
            session: Session,
            include_sanitized_payload: bool,
        ) -> PayloadDisclosureResult:
            del evidence_ref, session, include_sanitized_payload
            self.evidence_record_task_node_id = record.task_node_id
            return PayloadDisclosureResult(disclosure=AuditDisclosure())

    disclosure_spy = _DisclosureSpy()
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(
            TaskTreeView(session_id="session-1", nodes=(card,)),
            details={
                "published-task": TaskDetailView(
                    card=card,
                    full_intent=card.intent_preview,
                    file_changes=(change,),
                )
            },
        ),
        audit_payload_disclosure_service=disclosure_spy,
        plan_store=_PlanStore(active_plan=plan, task_nodes=(plan_node,)),
    )

    listed = gateway.list_audit_records(
        "session-1",
        task_node_id="node-stored",
        filter_kind="files",
    )
    detail = gateway.get_audit_record_detail(
        "session-1",
        "record-file-change-1",
        include_evidence=True,
    )
    evidence = gateway.get_evidence_detail(
        "session-1",
        "evidence-record-file-change-1",
        include_sanitized_payload=True,
    )

    assert listed.ok is True
    assert listed.data is not None
    assert listed.data.records[0].task_node_id == "node-stored"
    assert listed.data.records[0].task_ref == TaskRef.published("published-task")
    assert listed.data.records[0].scope.kind == "file"
    assert listed.data.records[0].scope.task_node_id == "node-stored"
    assert detail.ok is True
    assert detail.data is not None
    assert detail.data.task_node_id == "node-stored"
    assert detail.data.task_ref == TaskRef.published("published-task")
    assert detail.data.related_logs[0].filters["taskNodeId"] == "node-stored"
    assert evidence.ok is True
    assert evidence.data is not None
    assert evidence.data.id == "evidence-record-file-change-1"
    assert disclosure_spy.evidence_record_task_node_id == "node-stored"


def test_get_audit_snapshot_falls_back_to_legacy_task_selection() -> None:
    card = _card("legacy-task", status="done")
    plan = Plan(
        plan_id="plan-stored",
        session_id="session-1",
        title="Stored plan",
        objective="Use durable plan facts.",
        summary="Stored durable plan summary.",
        status="running",
    )
    plan_node = PlanTaskNode(
        task_node_id="node-stored",
        plan_id=plan.plan_id,
        session_id="session-1",
        task_index="1",
        title="Stored task",
        intent="Use stored PlanTaskNode.",
        summary="Stored task summary.",
        readiness="published",
        execution="done",
        published_ref=TaskRef.published("published-task"),
    )
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(TaskTreeView(session_id="session-1", nodes=(card,))),
        plan_store=_PlanStore(active_plan=plan, task_nodes=(plan_node,)),
    )

    response = gateway.get_audit_snapshot(
        "session-1",
        task_node_id="legacy-task",
        filter_kind="actions",
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.selected_task is not None
    assert response.data.selected_task.id == "legacy-task"
    assert [record.id for record in response.data.records] == [
        "record-task-published-legacy-task"
    ]


def test_audit_records_query_filters_kind_and_paginates_in_api_order() -> None:
    message = SessionMessageView(
        message_id="message-1",
        session_id="session-1",
        task_ref=TaskRef.published("root"),
        message_type="agent",
        content_summary="Implementation completed.",
        created_at=NOW,
    )
    card = _card(status="done", message=message)
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(TaskTreeView(session_id="session-1", nodes=(card,))),
    )

    response = gateway.list_audit_records(
        "session-1",
        filter_kind="actions",
        kind="action",
        limit=1,
    )

    assert response.ok is True
    assert response.data is not None
    assert response.data.total_count == 1
    assert response.data.next_cursor is None
    assert [record.id for record in response.data.records] == ["record-task-published-root"]


def test_audit_record_detail_and_evidence_detail_are_addressable() -> None:
    card = _card(status="done")
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(TaskTreeView(session_id="session-1", nodes=(card,))),
    )

    detail = gateway.get_audit_record_detail(
        "session-1",
        "record-task-published-root",
        include_evidence=True,
    )
    evidence = gateway.get_evidence_detail(
        "session-1",
        "evidence-record-task-published-root",
    )

    assert detail.ok is True
    assert detail.data is not None
    assert detail.data.id == "record-task-published-root"
    assert detail.data.evidence[0].source == "task_projection"
    assert evidence.ok is True
    assert evidence.data is not None
    assert evidence.data.id == "evidence-record-task-published-root"
    assert evidence.data.disclosure.partial_reason is not None


def test_audit_snapshot_includes_event_stream_action_and_observation_records(
    tmp_path: Path,
) -> None:
    layout = WorkspaceLayout(tmp_path)
    layout.bootstrap_session("session-1")
    action = ReadFileAction(
        event_id="action-read",
        timestamp=NOW,
        path="README.md",
    )
    observation = FileContentObservation(
        event_id="observation-read",
        timestamp=datetime(2026, 5, 20, 12, 1, tzinfo=UTC),
        action_id="action-read",
        path="README.md",
        content="hello",
        bytes_read=5,
    )
    with SqliteEventStream(layout.session_events_db("session-1")) as stream:
        stream.append(action, task_id="root")
        stream.append(observation, task_id="root")
    card = _card(status="done")
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session(workspace_root=tmp_path)]),
        task_projection=_Projection(TaskTreeView(session_id="session-1", nodes=(card,))),
        audit_event_provider=WorkspaceAuditEventProvider(layout),
    )

    response = gateway.list_audit_records(
        "session-1",
        task_node_id="root",
        filter_kind="actions",
    )
    evidence = gateway.get_evidence_detail(
        "session-1",
        "evidence-event-action-action-read",
    )

    assert response.ok is True
    assert response.data is not None
    assert "record-event-action-action-read" in {
        record.id for record in response.data.records
    }
    assert "record-event-observation-observation-read" in {
        record.id for record in response.data.records
    }
    assert evidence.ok is True
    assert evidence.data is not None
    assert evidence.data.source == "event_stream"


def test_audit_record_payload_is_generated_only_when_requested(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    layout.bootstrap_session("session-1")
    action = WriteFileAction(
        event_id="action-write",
        timestamp=NOW,
        path=str(layout.session_project_dir("session-1") / "src/App.tsx"),
        content="OPENAI_API_KEY=sk-test\nhello",
    )
    with SqliteEventStream(layout.session_events_db("session-1")) as stream:
        stream.append(action, task_id="root")
    card = _card(status="done")
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session(workspace_root=tmp_path)]),
        task_projection=_Projection(TaskTreeView(session_id="session-1", nodes=(card,))),
        audit_event_provider=WorkspaceAuditEventProvider(layout),
    )

    default_detail = gateway.get_audit_record_detail(
        "session-1",
        "record-event-action-action-write",
    )
    requested_detail = gateway.get_audit_record_detail(
        "session-1",
        "record-event-action-action-write",
        include_sanitized_payload=True,
    )

    assert default_detail.ok is True
    assert default_detail.data is not None
    assert default_detail.data.raw_payload is None
    assert default_detail.data.disclosure.raw_payload_available is True
    assert default_detail.data.disclosure.raw_payload_shown is False
    assert requested_detail.ok is True
    assert requested_detail.data is not None
    assert requested_detail.data.raw_payload is not None
    assert requested_detail.data.disclosure.raw_payload_shown is True
    assert "sk-test" not in requested_detail.data.raw_payload.content
    assert "[redacted:content" in requested_detail.data.raw_payload.content
    assert "workspace://" in requested_detail.data.raw_payload.content
    assert requested_detail.data.raw_payload.redactions


def test_audit_evidence_payload_summarizes_observation_content(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    layout.bootstrap_session("session-1")
    observation = FileContentObservation(
        event_id="observation-read",
        timestamp=NOW,
        action_id="action-read",
        path="README.md",
        content="secret=abc123\n" * 50,
        bytes_read=700,
    )
    with SqliteEventStream(layout.session_events_db("session-1")) as stream:
        stream.append(observation, task_id="root")
    card = _card(status="done")
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session(workspace_root=tmp_path)]),
        task_projection=_Projection(TaskTreeView(session_id="session-1", nodes=(card,))),
        audit_event_provider=WorkspaceAuditEventProvider(layout),
    )

    evidence = gateway.get_evidence_detail(
        "session-1",
        "evidence-event-observation-observation-read",
        include_sanitized_payload=True,
    )

    assert evidence.ok is True
    assert evidence.data is not None
    assert evidence.data.sanitized_payload is not None
    assert evidence.data.disclosure.raw_payload_shown is True
    assert evidence.data.disclosure.partial_reason is not None
    assert "abc123" not in evidence.data.sanitized_payload.content
    assert "[redacted:content" in evidence.data.sanitized_payload.content


def test_audit_snapshot_includes_workspace_log_and_config_records(
    tmp_path: Path,
) -> None:
    layout = WorkspaceLayout(tmp_path)
    layout.bootstrap_session("session-1")
    session = _session(workspace_root=tmp_path)
    log_dir = layout.session_logs_dir("session-1")
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "frontend-errors.jsonl").write_text(
        "\n".join(
            [
                '{"message":"render.failed","token":"abc123"}',
                *[f'{{"message":"line-{index}"}}' for index in range(25)],
            ]
        ),
        encoding="utf-8",
    )
    manifest = LogArchiveManifest(
        session_id="session-1",
        created_at=NOW,
        config_hash="abc123",
        active_config_path="logging.json",
        archive_root=str(log_dir),
        files={"frontend": "frontend-errors.jsonl"},
    )
    (log_dir / "manifest.json").write_text(
        manifest.model_dump_json(),
        encoding="utf-8",
    )
    card = _card(status="done")
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([session]),
        task_projection=_Projection(TaskTreeView(session_id="session-1", nodes=(card,))),
        audit_config_provider=WorkspaceAuditConfigProvider(),
        audit_log_provider=WorkspaceAuditLogProvider(),
    )

    config_response = gateway.list_audit_records("session-1", filter_kind="config")
    logs_response = gateway.list_audit_records("session-1", filter_kind="logs")
    snapshot = gateway.get_audit_snapshot("session-1")
    config_evidence = gateway.get_evidence_detail(
        "session-1",
        "evidence-record-config-logging-manifest",
        include_sanitized_payload=True,
    )
    log_evidence = gateway.get_evidence_detail(
        "session-1",
        "evidence-record-log-frontend-errors.jsonl",
        include_sanitized_payload=True,
    )

    assert config_response.ok is True
    assert config_response.data is not None
    assert [record.kind for record in config_response.data.records] == ["config_change"]
    assert logs_response.ok is True
    assert logs_response.data is not None
    assert [record.kind for record in logs_response.data.records] == ["log_evidence"]
    assert snapshot.ok is True
    assert snapshot.data is not None
    assert snapshot.data.effective_config is not None
    assert snapshot.data.effective_config.profile_label == "Session log manifest"
    assert snapshot.data.related_logs[0].enabled is True
    assert snapshot.data.related_logs[0].href == (
        "/sessions/session-1/diagnostics/logs?category=audit"
    )
    assert str(log_dir) not in snapshot.data.related_logs[0].href
    assert config_evidence.ok is True
    assert config_evidence.data is not None
    assert config_evidence.data.source == "config_store"
    assert config_evidence.data.sanitized_payload is not None
    assert "abc123" in config_evidence.data.sanitized_payload.content
    assert str(log_dir) not in config_evidence.data.sanitized_payload.content
    assert "session-logs://" in config_evidence.data.sanitized_payload.content
    assert log_evidence.ok is True
    assert log_evidence.data is not None
    assert log_evidence.data.source == "log_archive"
    assert log_evidence.data.sanitized_payload is not None
    assert "abc123" not in log_evidence.data.sanitized_payload.content
    assert "[redacted:secret]" in log_evidence.data.sanitized_payload.content
    assert log_evidence.data.disclosure.partial_reason is not None


def test_audit_snapshot_returns_not_found_for_unknown_task() -> None:
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(TaskTreeView(session_id="session-1", nodes=(_card(),))),
    )

    response = gateway.get_audit_snapshot("session-1", task_node_id="missing")

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "not_found"


def test_query_gateway_converts_unexpected_errors_to_internal_error() -> None:
    gateway = DefaultUiQueryGateway(
        session_reader=_SessionReader([_session()]),
        task_projection=_Projection(RuntimeError("projection exploded")),
    )

    response = gateway.get_session_snapshot("session-1")

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "internal_error"
    assert response.error.details["productCategory"] == "unexpected_internal"
    assert response.error.details["recoveryActions"] == [
        "refresh_snapshot",
        "export_diagnostics",
    ]
    assert response.error.details["error_type"] == "RuntimeError"
