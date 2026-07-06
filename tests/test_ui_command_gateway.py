"""Tests for framework-neutral UI command gateway."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from taskweavn.server.ui_contract import (
    AnswerAskPayload,
    AnswerAuthoringAskBatchPayload,
    AnswerAuthoringAskItemPayload,
    AppendSessionInputPayload,
    AppendTaskInputPayload,
    ArchivePlanPayload,
    CancelAskPayload,
    CommandRequest,
    DefaultUiCommandGateway,
    DeferAskPayload,
    GenerateTaskTreePayload,
    PublishTaskTreePayload,
    RepairAuthoringStatePayload,
    ResolveConfirmationPayload,
    RetryTaskPayload,
    StopTaskPayload,
    TaskRefResolver,
    UiCommandGateway,
    UpdateTaskNodePayload,
)
from taskweavn.task import (
    ActiveAuthoringState,
    FeasibilityReport,
    InMemoryRawTaskStore,
    Plan,
    PlanTaskNode,
    PublishPlanCommand,
    PublishPlanResult,
    RawTask,
    RawTaskAnswer,
    RawTaskAnswerOption,
    RawTaskAsk,
    TaskNodePatch,
    TaskRef,
)
from taskweavn.task import (
    CommandResult as CoreCommandResult,
)
from taskweavn.task.views import (
    TaskCardView as CoreTaskCardView,
)
from taskweavn.task.views import (
    TaskDetailView as CoreTaskDetailView,
)
from taskweavn.task.views import (
    TaskTreeView as CoreTaskTreeView,
)


@dataclass
class _Collaborator:
    result: CoreCommandResult = field(
        default_factory=lambda: CoreCommandResult(
            command_id="backend-command",
            status="accepted",
            message="ok",
        )
    )
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def start_session(self, session_id: str) -> CoreCommandResult:
        self.calls.append(("start_session", {"session_id": session_id}))
        return self.result

    def append_session_message(
        self,
        *,
        session_id: str,
        content: str,
        source_message_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "append_session_message",
                {
                    "session_id": session_id,
                    "content": content,
                    "source_message_id": source_message_id,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        return self.result

    def answer_raw_task_ask(
        self,
        *,
        session_id: str,
        raw_task_id: str,
        ask_id: str,
        value: str,
        source_message_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CoreCommandResult:
        raise NotImplementedError

    def answer_raw_task_asks(
        self,
        *,
        session_id: str,
        raw_task_id: str,
        answers: tuple[object, ...],
        source_message_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "answer_raw_task_asks",
                {
                    "session_id": session_id,
                    "raw_task_id": raw_task_id,
                    "answers": answers,
                    "source_message_id": source_message_id,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        return self.result

    def generate_task_tree(
        self,
        *,
        session_id: str,
        raw_task_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "generate_task_tree",
                {
                    "session_id": session_id,
                    "raw_task_id": raw_task_id,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        return self.result

    def append_task_message(
        self,
        *,
        session_id: str,
        task_ref: TaskRef,
        content: str,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "append_task_message",
                {"session_id": session_id, "task_ref": task_ref, "content": content},
            )
        )
        return self.result

    def publish_task_tree(
        self,
        *,
        session_id: str,
        draft_tree_id: str,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
        start_immediately: bool = True,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "publish_task_tree",
                {
                    "session_id": session_id,
                    "draft_tree_id": draft_tree_id,
                    "expected_version": expected_version,
                    "idempotency_key": idempotency_key,
                    "start_immediately": start_immediately,
                },
            )
        )
        return self.result


@dataclass
class _TaskCommands:
    result: CoreCommandResult = field(
        default_factory=lambda: CoreCommandResult(
            command_id="task-command",
            status="accepted",
            message="ok",
            affected_task_refs=(TaskRef.published("task-1"),),
        )
    )
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def update_task_node(
        self,
        session_id: str,
        task_ref: TaskRef,
        patch: TaskNodePatch,
        *,
        expected_version: int | None = None,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "update_task_node",
                {
                    "session_id": session_id,
                    "task_ref": task_ref,
                    "patch": patch,
                    "expected_version": expected_version,
                },
            )
        )
        return self.result

    def append_task_message(
        self,
        session_id: str,
        task_ref: TaskRef,
        content: str,
        *,
        mode: str,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "append_task_message",
                {
                    "session_id": session_id,
                    "task_ref": task_ref,
                    "content": content,
                    "mode": mode,
                },
            )
        )
        return self.result

    def resolve_confirmation(
        self,
        session_id: str,
        confirmation_id: str,
        value: str,
        *,
        note: str | None = None,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "resolve_confirmation",
                {
                    "session_id": session_id,
                    "confirmation_id": confirmation_id,
                    "value": value,
                    "note": note,
                },
            )
        )
        return self.result

    def publish_task_tree(self, session_id: str, draft_tree_id: str) -> CoreCommandResult:
        raise NotImplementedError

    def retry_task(
        self,
        session_id: str,
        task_id: str,
        instruction: str | None = None,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "retry_task",
                {
                    "session_id": session_id,
                    "task_id": task_id,
                    "instruction": instruction,
                },
            )
        )
        return self.result

    def stop_task(
        self,
        session_id: str,
        task_id: str,
        *,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "stop_task",
                {
                    "session_id": session_id,
                    "task_id": task_id,
                    "reason": reason,
                    "request_id": request_id,
                },
            )
        )
        return self.result


@dataclass
class _AskCommands:
    result: CoreCommandResult = field(
        default_factory=lambda: CoreCommandResult(
            command_id="ask-command",
            status="accepted",
            message="ask command accepted",
            affected_task_refs=(TaskRef.published("task-1"),),
        )
    )
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def answer_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        selected_option_ids: tuple[str, ...] = (),
        text: str | None = None,
        idempotency_key: str | None = None,
        command_id: str | None = None,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "answer_ask",
                {
                    "session_id": session_id,
                    "ask_id": ask_id,
                    "selected_option_ids": selected_option_ids,
                    "text": text,
                    "idempotency_key": idempotency_key,
                    "command_id": command_id,
                },
            )
        )
        return self.result

    def defer_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str | None = None,
        idempotency_key: str | None = None,
        command_id: str | None = None,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "defer_ask",
                {
                    "session_id": session_id,
                    "ask_id": ask_id,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "command_id": command_id,
                },
            )
        )
        return self.result

    def cancel_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str,
        idempotency_key: str | None = None,
        command_id: str | None = None,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "cancel_ask",
                {
                    "session_id": session_id,
                    "ask_id": ask_id,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                    "command_id": command_id,
                },
            )
        )
        return self.result


@dataclass(frozen=True)
class _Resolver:
    refs: dict[str, TaskRef]

    def resolve(self, session_id: str, task_node_id: str) -> TaskRef:
        try:
            return self.refs[task_node_id]
        except KeyError as exc:
            raise LookupError(f"task node {task_node_id!r} not found") from exc


@dataclass(frozen=True)
class _TaskProjection:
    has_published_tree: bool = False
    tree: CoreTaskTreeView | None = None

    def list_task_tree(
        self,
        session_id: str,
        *,
        root_ref: TaskRef | None = None,
        include_drafts: bool = True,
        include_published: bool = True,
    ) -> CoreTaskTreeView:
        if self.tree is not None:
            return self.tree
        if not include_published or not self.has_published_tree:
            return CoreTaskTreeView(session_id=session_id)
        ref = TaskRef.published("task-1")
        return CoreTaskTreeView(
            session_id=session_id,
            nodes=(
                CoreTaskCardView(
                    task_ref=ref,
                    root_ref=ref,
                    title="Published task",
                    intent_preview="A published task exists.",
                    status="pending",
                ),
            ),
        )

    def get_task_card(self, session_id: str, task_ref: TaskRef) -> CoreTaskCardView:
        raise NotImplementedError

    def get_task_detail(
        self,
        session_id: str,
        task_ref: TaskRef,
        *,
        message_limit: int = 100,
    ) -> CoreTaskDetailView:
        raise NotImplementedError


@dataclass
class _AuthoringStateStore:
    state: ActiveAuthoringState
    published: list[tuple[str, str]] = field(default_factory=list)

    def get_active(self, session_id: str) -> ActiveAuthoringState:
        return self.state

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
        self.published.append((session_id, draft_tree_id))

    def cancel_active(self, session_id: str) -> None:
        self.state = ActiveAuthoringState(
            session_id=session_id,
            active_raw_task_id=self.state.active_raw_task_id,
            active_draft_tree_id=self.state.active_draft_tree_id,
            active_plan_id=self.state.active_plan_id,
            active_state="cancelled",
        )


@dataclass
class _PlanStore:
    active_plan: Plan | None = None
    created_plans: list[Plan] = field(default_factory=list)
    created_task_nodes: list[PlanTaskNode] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._plans: dict[tuple[str, str], Plan] = {}
        self._task_nodes: dict[tuple[str, str], list[PlanTaskNode]] = {}
        if self.active_plan is not None:
            self._plans[
                (self.active_plan.session_id, self.active_plan.plan_id)
            ] = self.active_plan

    def create_plan(
        self,
        plan: Plan,
        task_nodes: Sequence[PlanTaskNode] = (),
    ) -> Plan:
        if (plan.session_id, plan.plan_id) in self._plans:
            raise ValueError(f"Plan {plan.plan_id!r} already exists")
        saved = plan.model_copy(
            update={
                "task_node_ids": tuple(node.task_node_id for node in task_nodes),
            }
        )
        self._plans[(saved.session_id, saved.plan_id)] = saved
        self._task_nodes[(saved.session_id, saved.plan_id)] = list(task_nodes)
        self.created_plans.append(saved)
        self.created_task_nodes.extend(task_nodes)
        return saved

    def get_plan(self, session_id: str, plan_id: str) -> Plan | None:
        return self._plans.get((session_id, plan_id))

    def list_plans(self, session_id: str) -> list[Plan]:
        return [plan for plan in self._plans.values() if plan.session_id == session_id]

    def get_active_plan(self, session_id: str) -> Plan | None:
        if self.active_plan is None or self.active_plan.session_id != session_id:
            return None
        return self.active_plan

    def save_plan(self, plan: Plan, *, expected_version: int) -> Plan:
        raise NotImplementedError

    def archive_plan(
        self,
        session_id: str,
        plan_id: str,
        *,
        expected_version: int | None = None,
    ) -> Plan:
        raise NotImplementedError

    def get_task_node(self, session_id: str, task_node_id: str) -> PlanTaskNode | None:
        raise NotImplementedError

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


@dataclass
class _PlanPublisher:
    result: PublishPlanResult = field(
        default_factory=lambda: PublishPlanResult(
            command_id="plan-publish",
            request_id="plan-publish",
            session_id="session-1",
            plan_id="plan-1",
            published_task_ids=("published-plan-task",),
            root_task_ids=("published-plan-task",),
        )
    )
    calls: list[PublishPlanCommand] = field(default_factory=list)

    def publish_plan(self, command: PublishPlanCommand) -> PublishPlanResult:
        self.calls.append(command)
        return self.result.model_copy(
            update={
                "command_id": command.command_id,
                "request_id": command.command_id,
                "session_id": command.session_id,
                "plan_id": command.plan_id,
            }
        )


@dataclass
class _PlanLifecycleCommands:
    result: CoreCommandResult = field(
        default_factory=lambda: CoreCommandResult(
            command_id="plan-lifecycle",
            status="accepted",
            message="Plan archived.",
            emitted_message_ids=("message-1",),
        )
    )
    calls: list[tuple[str, str, dict[str, object]]] = field(default_factory=list)

    def archive_plan(
        self,
        session_id: str,
        plan_id: str,
        *,
        expected_version: int | None = None,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                session_id,
                plan_id,
                {
                    "expected_version": expected_version,
                    "reason": reason,
                    "request_id": request_id,
                },
            )
        )
        return self.result


def _gateway(
    *,
    collaborator: _Collaborator | None = None,
    task_commands: _TaskCommands | None = None,
    ask_commands: _AskCommands | None = None,
    resolver: _Resolver | None = None,
    authoring_state_store: _AuthoringStateStore | None = None,
    raw_task_store: InMemoryRawTaskStore | None = None,
    task_projection: _TaskProjection | None = None,
    plan_store: _PlanStore | None = None,
    plan_publisher: _PlanPublisher | None = None,
    plan_lifecycle_commands: _PlanLifecycleCommands | None = None,
) -> DefaultUiCommandGateway:
    return DefaultUiCommandGateway(
        collaborator=collaborator or _Collaborator(),
        task_commands=task_commands or _TaskCommands(),
        task_ref_resolver=resolver
        or _Resolver({"draft-1": TaskRef.draft("draft-1"), "task-1": TaskRef.published("task-1")}),
        authoring_state_store=authoring_state_store,
        raw_task_store=raw_task_store,
        ask_commands=ask_commands,
        task_projection=task_projection,
        plan_store=plan_store,
        plan_publisher=plan_publisher,
        plan_lifecycle_commands=plan_lifecycle_commands,
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


def _answered_raw_task() -> RawTask:
    raw_task = _awaiting_raw_task()
    return raw_task.model_copy(
        update={
            "answers": (
                RawTaskAnswer(
                    raw_task_id="raw-1",
                    ask_id="ask-1",
                    value="static",
                    source_message_id="answer-message-1",
                ),
            ),
            "status": "assessing",
        }
    )


def test_command_gateway_protocol_conformance() -> None:
    gateway = _gateway()
    assert isinstance(gateway, UiCommandGateway)
    assert isinstance(_Resolver({}), TaskRefResolver)


def test_append_session_input_wraps_collaborator_result() -> None:
    collaborator = _Collaborator()
    gateway = _gateway(collaborator=collaborator)
    request = CommandRequest[AppendSessionInputPayload](
        command_id="ui-command",
        session_id="session-1",
        payload=AppendSessionInputPayload(
            content="Build a website",
            mode="generate_task_tree",
        ),
    )

    response = gateway.append_session_input(request)

    assert response.ok is True
    assert response.result is not None
    assert response.request_id == "ui-command"
    assert response.result.command_id == "ui-command"
    assert response.result.debug_refs == {"backendCommandId": "backend-command"}
    assert response.result.object_refs[0].kind == "command"
    assert response.refresh.affected_scopes[0].kind == "session"
    assert collaborator.calls[0][0] == "append_session_message"
    assert collaborator.calls[0][1]["source_message_id"] is None


def test_generate_task_tree_with_raw_task_carries_object_refs() -> None:
    collaborator = _Collaborator()
    gateway = _gateway(collaborator=collaborator)
    request = CommandRequest[GenerateTaskTreePayload](
        command_id="generate-1",
        session_id="session-1",
        payload=GenerateTaskTreePayload(raw_task_id="raw-1"),
    )

    response = gateway.generate_task_tree(request)

    assert response.ok is True
    assert response.result is not None
    assert {"kind": "raw_task", "id": "raw-1"} in response.result.model_dump(
        mode="json"
    )["objectRefs"]
    assert response.result.affected_objects[0].impact == "changed"
    assert collaborator.calls[0] == (
        "generate_task_tree",
        {
            "session_id": "session-1",
            "raw_task_id": "raw-1",
            "idempotency_key": None,
        },
    )


def test_generate_task_tree_with_prompt_creates_raw_then_tree() -> None:
    collaborator = _Collaborator(
        result=CoreCommandResult(
            command_id="backend-command",
            status="accepted",
            message="ok",
            affected_task_refs=(TaskRef.draft("draft-1"),),
            emitted_message_ids=("message-1",),
        )
    )
    gateway = _gateway(collaborator=collaborator)
    request = CommandRequest[GenerateTaskTreePayload](
        command_id="generate-1",
        session_id="session-1",
        payload=GenerateTaskTreePayload(prompt="Build a website"),
    )

    response = gateway.generate_task_tree(request)

    assert response.ok is True
    assert response.result is not None
    assert response.result.affected_task_refs == (TaskRef.draft("draft-1"),)
    assert response.refresh.affected_scopes[1].kind == "task_tree"
    assert collaborator.calls == [
        (
            "append_session_message",
            {
                "session_id": "session-1",
                "content": "Build a website",
                "source_message_id": "generate-1",
                "idempotency_key": None,
            },
        ),
        (
            "generate_task_tree",
            {
                "session_id": "session-1",
                "raw_task_id": None,
                "idempotency_key": None,
            },
        ),
    ]


def test_generate_task_tree_with_prompt_stops_when_raw_task_needs_answers() -> None:
    collaborator = _Collaborator(
        result=CoreCommandResult(
            command_id="backend-command",
            status="accepted",
            message="ok",
        )
    )
    gateway = _gateway(
        collaborator=collaborator,
        raw_task_store=InMemoryRawTaskStore([_awaiting_raw_task()]),
    )
    request = CommandRequest[GenerateTaskTreePayload](
        command_id="generate-1",
        session_id="session-1",
        payload=GenerateTaskTreePayload(prompt="How do I publish a website?"),
    )

    response = gateway.generate_task_tree(request)

    assert response.ok is True
    assert response.result is not None
    assert response.result.status == "accepted"
    assert collaborator.calls == [
        (
            "append_session_message",
            {
                "session_id": "session-1",
                "content": "How do I publish a website?",
                "source_message_id": "generate-1",
                "idempotency_key": None,
            },
        )
    ]


def test_generate_task_tree_with_unready_raw_task_is_rejected() -> None:
    collaborator = _Collaborator()
    gateway = _gateway(
        collaborator=collaborator,
        raw_task_store=InMemoryRawTaskStore([_awaiting_raw_task()]),
    )
    request = CommandRequest[GenerateTaskTreePayload](
        command_id="generate-1",
        session_id="session-1",
        payload=GenerateTaskTreePayload(raw_task_id="raw-1"),
    )

    response = gateway.generate_task_tree(request)

    assert response.ok is False
    assert response.result is not None
    assert response.result.status == "rejected"
    assert "requires authoring answers" in response.result.message
    assert collaborator.calls == []


def test_answer_authoring_ask_batch_routes_to_collaborator() -> None:
    collaborator = _Collaborator()
    gateway = _gateway(collaborator=collaborator)
    request = CommandRequest[AnswerAuthoringAskBatchPayload](
        command_id="answer-authoring-1",
        session_id="session-1",
        idempotency_key="answer-batch-1",
        payload=AnswerAuthoringAskBatchPayload(
            answers=(
                AnswerAuthoringAskItemPayload(ask_id="ask-1", value="Developers"),
                AnswerAuthoringAskItemPayload(ask_id="ask-2", value="Portfolio"),
            )
        ),
    )

    response = gateway.answer_authoring_ask_batch("raw-1", request)

    assert response.ok is True
    assert response.result is not None
    dumped = response.result.model_dump(mode="json")
    assert {"kind": "raw_task", "id": "raw-1"} in dumped["objectRefs"]
    assert {"kind": "raw_task_ask", "id": "ask-1"} in dumped["objectRefs"]
    assert response.refresh.suggested_queries == (
        "session.snapshot",
        "session.messages",
        "task.tree",
    )
    assert collaborator.calls[0][0] == "answer_raw_task_asks"
    call = collaborator.calls[0][1]
    assert call["session_id"] == "session-1"
    assert call["raw_task_id"] == "raw-1"
    assert call["idempotency_key"] == "answer-batch-1"
    answers = call["answers"]
    assert isinstance(answers, tuple)
    assert [(answer.ask_id, answer.value) for answer in answers] == [
        ("ask-1", "Developers"),
        ("ask-2", "Portfolio"),
    ]


def test_answer_authoring_ask_batch_generates_tree_after_all_asks_answered() -> None:
    collaborator = _Collaborator(
        result=CoreCommandResult(
            command_id="backend-command",
            status="accepted",
            message="ok",
            affected_task_refs=(TaskRef.draft("draft-1"),),
        )
    )
    gateway = _gateway(
        collaborator=collaborator,
        raw_task_store=InMemoryRawTaskStore([_answered_raw_task()]),
    )
    request = CommandRequest[AnswerAuthoringAskBatchPayload](
        command_id="answer-authoring-1",
        session_id="session-1",
        idempotency_key="answer-batch-1",
        payload=AnswerAuthoringAskBatchPayload(
            answers=(
                AnswerAuthoringAskItemPayload(ask_id="ask-1", value="static"),
            )
        ),
    )

    response = gateway.answer_authoring_ask_batch("raw-1", request)

    assert response.ok is True
    assert response.result is not None
    assert response.result.affected_task_refs == (TaskRef.draft("draft-1"),)
    assert collaborator.calls[-1] == (
        "generate_task_tree",
        {
            "session_id": "session-1",
            "raw_task_id": "raw-1",
            "idempotency_key": "answer-batch-1:tree",
        },
    )


def test_answer_authoring_ask_batch_rejects_stale_authoring_context() -> None:
    collaborator = _Collaborator()
    state_store = _AuthoringStateStore(
        ActiveAuthoringState(
            session_id="session-1",
            active_raw_task_id="raw-1",
            active_draft_tree_id="tree-active",
            active_state="draft_tree",
        )
    )
    gateway = _gateway(
        collaborator=collaborator,
        authoring_state_store=state_store,
    )
    request = CommandRequest[AnswerAuthoringAskBatchPayload](
        command_id="answer-authoring-stale",
        session_id="session-1",
        payload=AnswerAuthoringAskBatchPayload(
            answers=(AnswerAuthoringAskItemPayload(ask_id="ask-1", value="static"),)
        ),
    )

    response = gateway.answer_authoring_ask_batch("raw-1", request)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "command_rejected"
    assert response.result is not None
    assert response.result.status == "rejected"
    assert "stale_authoring_context" in response.result.message
    assert collaborator.calls == []
    dumped = response.result.model_dump(mode="json")
    assert {"kind": "raw_task", "id": "raw-1"} in dumped["objectRefs"]
    assert dumped["affectedObjects"][0]["impact"] == "superseded"
    assert response.refresh.wait_for_events is False
    assert response.refresh.suggested_queries == (
        "session.snapshot",
        "session.messages",
        "task.tree",
    )


def test_answer_authoring_ask_batch_rejects_raw_task_when_published_tree_exists() -> None:
    collaborator = _Collaborator()
    state_store = _AuthoringStateStore(
        ActiveAuthoringState(
            session_id="session-1",
            active_raw_task_id="raw-1",
            active_state="raw_task",
        )
    )
    gateway = _gateway(
        collaborator=collaborator,
        authoring_state_store=state_store,
        task_projection=_TaskProjection(has_published_tree=True),
    )
    request = CommandRequest[AnswerAuthoringAskBatchPayload](
        command_id="answer-authoring-dirty",
        session_id="session-1",
        payload=AnswerAuthoringAskBatchPayload(
            answers=(AnswerAuthoringAskItemPayload(ask_id="ask-1", value="static"),)
        ),
    )

    response = gateway.answer_authoring_ask_batch("raw-1", request)

    assert response.ok is False
    assert response.result is not None
    assert "stale_authoring_context" in response.result.message
    assert collaborator.calls == []
    dumped = response.result.model_dump(mode="json")
    assert {"kind": "raw_task_ask", "id": "ask-1"} in dumped["objectRefs"]
    assert dumped["affectedObjects"][0]["impact"] == "superseded"


def test_repair_authoring_state_closes_dirty_raw_task_flow() -> None:
    state_store = _AuthoringStateStore(
        ActiveAuthoringState(
            session_id="session-1",
            active_raw_task_id="raw-1",
            active_state="raw_task",
        )
    )
    gateway = _gateway(
        authoring_state_store=state_store,
        task_projection=_TaskProjection(has_published_tree=True),
    )
    request = CommandRequest[RepairAuthoringStatePayload](
        command_id="repair-authoring-1",
        session_id="session-1",
        payload=RepairAuthoringStatePayload(),
    )

    response = gateway.repair_authoring_state(request)

    assert response.ok is True
    assert response.result is not None
    assert state_store.state.active_state == "cancelled"
    assert state_store.state.active_raw_task_id == "raw-1"
    assert any(
        ref.kind == "raw_task" and ref.id == "raw-1"
        for ref in response.result.object_refs
    )
    assert response.result.affected_objects[0].impact == "superseded"
    assert response.refresh.suggested_queries == (
        "session.snapshot",
        "session.messages",
        "task.tree",
    )


def test_repair_authoring_state_rejects_without_existing_task_tree() -> None:
    state_store = _AuthoringStateStore(
        ActiveAuthoringState(
            session_id="session-1",
            active_raw_task_id="raw-1",
            active_state="raw_task",
        )
    )
    gateway = _gateway(
        authoring_state_store=state_store,
        task_projection=_TaskProjection(has_published_tree=False),
    )
    request = CommandRequest[RepairAuthoringStatePayload](
        command_id="repair-authoring-1",
        session_id="session-1",
        payload=RepairAuthoringStatePayload(),
    )

    response = gateway.repair_authoring_state(request)

    assert response.ok is False
    assert response.result is not None
    assert response.result.status == "rejected"
    assert state_store.state.active_state == "raw_task"
    assert "requires an existing TaskTree" in response.result.message


def test_update_task_node_resolves_task_ref_and_preserves_subtree_intent() -> None:
    commands = _TaskCommands()
    gateway = _gateway(task_commands=commands)
    request = CommandRequest[UpdateTaskNodePayload](
        command_id="update-1",
        session_id="session-1",
        expected_version=3,
        payload=UpdateTaskNodePayload(
            full_intent="Rebuild the subtree around this parent.",
            update_mode="replace_subtree",
        ),
    )

    response = gateway.update_task_node("draft-1", request)
    call = commands.calls[0][1]
    patch = call["patch"]

    assert response.ok is True
    assert call["task_ref"] == TaskRef.draft("draft-1")
    assert call["expected_version"] == 3
    assert isinstance(patch, TaskNodePatch)
    assert patch.intent == "Rebuild the subtree around this parent."
    assert patch.children_ops == ({"op": "replace_subtree", "preserve_root_id": True},)
    assert response.refresh.affected_scopes[0].kind == "task_subtree"


def test_append_task_input_routes_draft_to_collaborator_and_published_to_task_commands() -> None:
    collaborator = _Collaborator()
    commands = _TaskCommands()
    gateway = _gateway(collaborator=collaborator, task_commands=commands)
    draft_request = CommandRequest[AppendTaskInputPayload](
        command_id="draft-input",
        session_id="session-1",
        payload=AppendTaskInputPayload(content="Tighten this node", mode="guidance"),
    )
    published_request = CommandRequest[AppendTaskInputPayload](
        command_id="published-input",
        session_id="session-1",
        payload=AppendTaskInputPayload(
            content="Revise this task",
            mode="revision_request",
        ),
    )

    draft_response = gateway.append_task_input("draft-1", draft_request)
    published_response = gateway.append_task_input("task-1", published_request)

    assert draft_response.ok is True
    assert collaborator.calls[0][0] == "append_task_message"
    assert published_response.ok is True
    assert commands.calls[0][0] == "append_task_message"
    assert commands.calls[0][1]["mode"] == "correction"


def test_publish_task_tree_wraps_draft_tree_and_published_task_refs() -> None:
    collaborator = _Collaborator(
        CoreCommandResult(
            command_id="backend-publish",
            status="accepted",
            message="published",
            affected_task_refs=(TaskRef.published("published-root"),),
            published_task_ids=("published-root",),
        )
    )
    gateway = _gateway(collaborator=collaborator)
    request = CommandRequest[PublishTaskTreePayload](
        command_id="publish-1",
        session_id="session-1",
        expected_version=5,
        idempotency_key="publish-key",
        payload=PublishTaskTreePayload(task_tree_id="tree-1", start_immediately=False),
    )

    response = gateway.publish_task_tree(request)

    assert response.ok is True
    assert response.result is not None
    assert response.result.published_task_ids == ("published-root",)
    assert {"kind": "draft_tree", "id": "tree-1"} in response.result.model_dump(
        mode="json"
    )["objectRefs"]
    assert response.result.debug_refs["idempotencyKey"] == "publish-key"
    assert collaborator.calls[0][1]["start_immediately"] is False


def test_publish_task_tree_routes_active_durable_plan_to_plan_publisher() -> None:
    collaborator = _Collaborator()
    state_store = _AuthoringStateStore(
        ActiveAuthoringState(
            session_id="session-1",
            active_raw_task_id="raw-1",
            active_draft_tree_id="tree-active",
            active_state="draft_tree",
        )
    )
    plan = Plan(
        plan_id="plan-1",
        session_id="session-1",
        title="Plan",
        objective="Publish the active Plan.",
        summary="Flat TaskNode plan.",
        version=3,
    )
    plan_store = _PlanStore(active_plan=plan)
    plan_publisher = _PlanPublisher()
    gateway = _gateway(
        collaborator=collaborator,
        authoring_state_store=state_store,
        plan_store=plan_store,
        plan_publisher=plan_publisher,
    )
    request = CommandRequest[PublishTaskTreePayload](
        command_id="publish-plan",
        session_id="session-1",
        expected_version=3,
        idempotency_key="publish-key",
        payload=PublishTaskTreePayload(
            task_tree_id="session:session-1:task-tree",
            start_immediately=True,
        ),
    )

    response = gateway.publish_task_tree(request)

    assert response.ok is True
    assert response.result is not None
    assert response.result.published_task_ids == ("published-plan-task",)
    assert {"kind": "plan", "id": "plan-1"} in response.result.model_dump(
        mode="json"
    )["objectRefs"]
    assert collaborator.calls == []
    assert state_store.published == []
    assert len(plan_publisher.calls) == 1
    command = plan_publisher.calls[0]
    assert command.command_id == "publish-plan"
    assert command.session_id == "session-1"
    assert command.plan_id == "plan-1"
    assert command.expected_plan_version == 3
    assert command.idempotency_key == "publish-key"


def test_publish_task_tree_plan_publish_uses_command_id_as_idempotency_fallback() -> None:
    collaborator = _Collaborator()
    plan_store = _PlanStore(
        active_plan=Plan(
            plan_id="plan-1",
            session_id="session-1",
            title="Plan",
            objective="Publish the active Plan.",
            summary="Flat TaskNode plan.",
        )
    )
    plan_publisher = _PlanPublisher()
    gateway = _gateway(
        collaborator=collaborator,
        plan_store=plan_store,
        plan_publisher=plan_publisher,
    )
    request = CommandRequest[PublishTaskTreePayload](
        command_id="publish-plan-without-key",
        session_id="session-1",
        payload=PublishTaskTreePayload(),
    )

    response = gateway.publish_task_tree(request)

    assert response.ok is True
    assert collaborator.calls == []
    assert plan_publisher.calls[0].idempotency_key == "publish-plan-without-key"


def test_archive_plan_routes_to_plan_lifecycle_commands() -> None:
    plan_lifecycle = _PlanLifecycleCommands()
    gateway = _gateway(plan_lifecycle_commands=plan_lifecycle)
    request = CommandRequest[ArchivePlanPayload](
        command_id="archive-plan-1",
        session_id="session-1",
        expected_version=7,
        payload=ArchivePlanPayload(reason="user moved completed plan to history"),
    )

    response = gateway.archive_plan("plan-1", request)

    assert response.ok is True
    assert response.result is not None
    assert response.result.message == "Plan archived."
    assert {"kind": "plan", "id": "plan-1"} in response.result.model_dump(
        mode="json"
    )["objectRefs"]
    assert response.result.emitted_message_ids == ("message-1",)
    assert response.refresh.suggested_queries == (
        "session.snapshot",
        "session.activity",
        "task.tree",
        "plans.history",
    )
    assert [scope.kind for scope in response.refresh.affected_scopes] == [
        "session",
        "task_tree",
        "messages",
    ]
    assert plan_lifecycle.calls == [
        (
            "session-1",
            "plan-1",
            {
                "expected_version": 7,
                "reason": "user moved completed plan to history",
                "request_id": "archive-plan-1",
            },
        )
    ]


def test_archive_plan_materializes_completed_legacy_plan() -> None:
    ref = TaskRef.published("task-1")
    task_projection = _TaskProjection(
        tree=CoreTaskTreeView(
            session_id="session-1",
            title="Legacy plan",
            summary="Completed legacy task tree.",
            nodes=(
                CoreTaskCardView(
                    task_ref=ref,
                    root_ref=ref,
                    title="Complete task",
                    intent_preview="Completed task summary.",
                    full_intent="Complete the task.",
                    instructions="Check the output.",
                    acceptance_criteria=("Output checked",),
                    status="done",
                ),
            ),
        )
    )
    plan_store = _PlanStore(active_plan=None)
    plan_lifecycle = _PlanLifecycleCommands()
    authoring_state_store = _AuthoringStateStore(
        ActiveAuthoringState(
            session_id="session-1",
            active_draft_tree_id="legacy-tree",
            active_state="published",
        )
    )
    gateway = _gateway(
        authoring_state_store=authoring_state_store,
        task_projection=task_projection,
        plan_store=plan_store,
        plan_lifecycle_commands=plan_lifecycle,
    )
    request = CommandRequest[ArchivePlanPayload](
        command_id="archive-legacy-plan",
        session_id="session-1",
        expected_version=4,
        payload=ArchivePlanPayload(reason="done"),
    )

    response = gateway.archive_plan("plan:legacy:session-1", request)

    assert response.ok is True
    assert response.result is not None
    assert response.result.message == "Plan archived."
    assert plan_lifecycle.calls == []
    assert len(plan_store.created_plans) == 1
    archived = plan_store.created_plans[0]
    assert archived.plan_id == "plan:legacy:session-1"
    assert archived.status == "archived"
    assert archived.version == 4
    assert archived.archived_at is not None
    assert len(plan_store.created_task_nodes) == 1
    archived_node = plan_store.created_task_nodes[0]
    assert archived_node.task_node_id == "task-1"
    assert archived_node.execution == "done"
    assert archived_node.published_ref == ref
    assert authoring_state_store.state.active_state == "cancelled"


def test_archive_plan_materializes_encoded_legacy_plan_id() -> None:
    ref = TaskRef.published("task-1")
    task_projection = _TaskProjection(
        tree=CoreTaskTreeView(
            session_id="session-1",
            title="Legacy plan",
            summary="Completed legacy task tree.",
            nodes=(
                CoreTaskCardView(
                    task_ref=ref,
                    root_ref=ref,
                    title="Complete task",
                    intent_preview="Completed task summary.",
                    full_intent="Complete the task.",
                    instructions="Check the output.",
                    acceptance_criteria=("Output checked",),
                    status="done",
                ),
            ),
        )
    )
    plan_store = _PlanStore(active_plan=None)
    plan_lifecycle = _PlanLifecycleCommands()
    gateway = _gateway(
        task_projection=task_projection,
        plan_store=plan_store,
        plan_lifecycle_commands=plan_lifecycle,
    )
    request = CommandRequest[ArchivePlanPayload](
        command_id="archive-legacy-plan",
        session_id="session-1",
        expected_version=4,
        payload=ArchivePlanPayload(reason="done"),
    )

    response = gateway.archive_plan("plan%3Alegacy%3Asession-1", request)

    assert response.ok is True
    assert response.result is not None
    assert response.result.message == "Plan archived."
    assert plan_lifecycle.calls == []
    assert len(plan_store.created_plans) == 1
    assert plan_store.created_plans[0].plan_id == "plan:legacy:session-1"


def test_publish_task_tree_falls_back_to_legacy_without_active_durable_plan() -> None:
    collaborator = _Collaborator()
    plan_store = _PlanStore(active_plan=None)
    plan_publisher = _PlanPublisher()
    gateway = _gateway(
        collaborator=collaborator,
        plan_store=plan_store,
        plan_publisher=plan_publisher,
    )
    request = CommandRequest[PublishTaskTreePayload](
        command_id="publish-legacy",
        session_id="session-1",
        payload=PublishTaskTreePayload(task_tree_id="tree-legacy"),
    )

    response = gateway.publish_task_tree(request)

    assert response.ok is True
    assert collaborator.calls[0][0] == "publish_task_tree"
    assert collaborator.calls[0][1]["draft_tree_id"] == "tree-legacy"
    assert plan_publisher.calls == []


def test_publish_task_tree_does_not_fallback_when_active_plan_publish_rejects() -> None:
    collaborator = _Collaborator()
    plan_store = _PlanStore(
        active_plan=Plan(
            plan_id="plan-1",
            session_id="session-1",
            title="Plan",
            objective="Publish the active Plan.",
            summary="Flat TaskNode plan.",
        )
    )
    plan_publisher = _PlanPublisher(
        PublishPlanResult(
            command_id="plan-publish",
            request_id="plan-publish",
            session_id="session-1",
            plan_id="plan-1",
            skipped=True,
            reason="plan has no TaskNodes",
        )
    )
    gateway = _gateway(
        collaborator=collaborator,
        plan_store=plan_store,
        plan_publisher=plan_publisher,
    )
    request = CommandRequest[PublishTaskTreePayload](
        command_id="publish-empty-plan",
        session_id="session-1",
        payload=PublishTaskTreePayload(task_tree_id="tree-legacy"),
    )

    response = gateway.publish_task_tree(request)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "command_rejected"
    assert response.error.message == "plan has no TaskNodes"
    assert collaborator.calls == []
    assert len(plan_publisher.calls) == 1


def test_publish_task_tree_rejects_synthetic_id_without_active_state_store() -> None:
    collaborator = _Collaborator()
    gateway = _gateway(collaborator=collaborator)
    request = CommandRequest[PublishTaskTreePayload](
        command_id="publish-synthetic-without-state",
        session_id="session-1",
        payload=PublishTaskTreePayload(task_tree_id="session:session-1:task-tree"),
    )

    response = gateway.publish_task_tree(request)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "bad_request"
    assert (
        response.error.details["reason"]
        == "synthetic_task_tree_identity_unresolved"
    )
    assert collaborator.calls == []


def test_publish_task_tree_without_id_uses_active_draft_tree() -> None:
    collaborator = _Collaborator()
    state_store = _AuthoringStateStore(
        ActiveAuthoringState(
            session_id="session-1",
            active_raw_task_id="raw-1",
            active_draft_tree_id="tree-active",
            active_state="draft_tree",
        )
    )
    gateway = _gateway(collaborator=collaborator, authoring_state_store=state_store)
    request = CommandRequest[PublishTaskTreePayload](
        command_id="publish-active",
        session_id="session-1",
        payload=PublishTaskTreePayload(start_immediately=False),
    )

    response = gateway.publish_task_tree(request)

    assert response.ok is True
    assert collaborator.calls[0][1]["draft_tree_id"] == "tree-active"
    assert collaborator.calls[0][1]["start_immediately"] is False
    assert state_store.published == [("session-1", "tree-active")]


def test_publish_task_tree_resolves_synthetic_tree_id_to_active_draft_tree() -> None:
    collaborator = _Collaborator()
    state_store = _AuthoringStateStore(
        ActiveAuthoringState(
            session_id="session-1",
            active_raw_task_id="raw-1",
            active_draft_tree_id="tree-active",
            active_state="draft_tree",
        )
    )
    gateway = _gateway(collaborator=collaborator, authoring_state_store=state_store)
    request = CommandRequest[PublishTaskTreePayload](
        command_id="publish-synthetic",
        session_id="session-1",
        payload=PublishTaskTreePayload(
            task_tree_id="session:session-1:task-tree",
            start_immediately=True,
        ),
    )

    response = gateway.publish_task_tree(request)

    assert response.ok is True
    assert collaborator.calls[0][1]["draft_tree_id"] == "tree-active"


def test_publish_task_tree_rejects_non_active_tree_identity() -> None:
    collaborator = _Collaborator()
    state_store = _AuthoringStateStore(
        ActiveAuthoringState(
            session_id="session-1",
            active_raw_task_id="raw-1",
            active_draft_tree_id="tree-active",
            active_state="draft_tree",
        )
    )
    gateway = _gateway(collaborator=collaborator, authoring_state_store=state_store)
    request = CommandRequest[PublishTaskTreePayload](
        command_id="publish-invalid",
        session_id="session-1",
        payload=PublishTaskTreePayload(task_tree_id="tree-other"),
    )

    response = gateway.publish_task_tree(request)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "bad_request"
    assert response.error.details["reason"] == "invalid_task_tree_identity"
    assert response.error.details["active_draft_tree_id"] == "tree-active"
    assert collaborator.calls == []


def test_publish_task_tree_rejects_missing_active_draft_tree() -> None:
    collaborator = _Collaborator()
    state_store = _AuthoringStateStore(ActiveAuthoringState(session_id="session-1"))
    gateway = _gateway(collaborator=collaborator, authoring_state_store=state_store)
    request = CommandRequest[PublishTaskTreePayload](
        command_id="publish-missing-active",
        session_id="session-1",
        payload=PublishTaskTreePayload(),
    )

    response = gateway.publish_task_tree(request)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "bad_request"
    assert response.error.details["reason"] == "no_active_draft_tree"
    assert collaborator.calls == []


def test_retry_task_wraps_published_failed_task_command() -> None:
    commands = _TaskCommands(
        CoreCommandResult(
            command_id="backend-retry",
            status="accepted",
            message="task retry queued",
            affected_task_refs=(TaskRef.published("task-1"),),
        )
    )
    gateway = _gateway(task_commands=commands)
    request = CommandRequest[RetryTaskPayload](
        command_id="retry-1",
        session_id="session-1",
        payload=RetryTaskPayload(
            instruction="Try a safer route",
            start_immediately=False,
        ),
    )

    response = gateway.retry_task("task-1", request)

    assert response.ok is True
    assert commands.calls == [
        (
            "retry_task",
            {
                "session_id": "session-1",
                "task_id": "task-1",
                "instruction": "Try a safer route",
            },
        )
    ]
    assert response.result is not None
    body = response.result.model_dump(mode="json")
    assert {"kind": "published_task", "id": "task-1"} in body["objectRefs"]
    assert {"kind": "published_task", "id": "retry-root"} not in body["objectRefs"]
    assert response.result.published_task_ids == ()
    assert {
        "ref": {"kind": "published_task", "id": "task-1"},
        "impact": "changed",
        "reason": "Manual retry moved this failed Task back to pending.",
    } in body["affectedObjects"]
    assert not any(
        affected["ref"] == {"kind": "published_task", "id": "retry-root"}
        for affected in body["affectedObjects"]
    )
    assert response.refresh.suggested_queries == (
        "session.snapshot",
        "task.tree",
        "task.detail",
    )


def test_retry_task_uses_resolved_published_task_ref() -> None:
    commands = _TaskCommands(
        CoreCommandResult(
            command_id="backend-retry",
            status="accepted",
            message="task retry queued",
            affected_task_refs=(TaskRef.published("published-task-1"),),
        )
    )
    gateway = _gateway(
        task_commands=commands,
        resolver=_Resolver({"plan-node-1": TaskRef.published("published-task-1")}),
    )
    request = CommandRequest[RetryTaskPayload](
        command_id="retry-plan-node",
        session_id="session-1",
        payload=RetryTaskPayload(
            instruction="Try again after the task node mapping fix",
            start_immediately=False,
        ),
    )

    response = gateway.retry_task("plan-node-1", request)

    assert response.ok is True
    assert commands.calls == [
        (
            "retry_task",
            {
                "session_id": "session-1",
                "task_id": "published-task-1",
                "instruction": "Try again after the task node mapping fix",
            },
        )
    ]
    assert response.result is not None
    body = response.result.model_dump(mode="json")
    assert {"kind": "published_task", "id": "published-task-1"} in body["objectRefs"]
    assert {"kind": "published_task", "id": "plan-node-1"} not in body["objectRefs"]


def test_retry_task_rejects_draft_task_ref() -> None:
    commands = _TaskCommands()
    gateway = _gateway(
        task_commands=commands,
        resolver=_Resolver({"draft-1": TaskRef.draft("draft-1")}),
    )
    request = CommandRequest[RetryTaskPayload](
        command_id="retry-draft",
        session_id="session-1",
        payload=RetryTaskPayload(start_immediately=False),
    )

    response = gateway.retry_task("draft-1", request)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "command_rejected"
    assert response.error.details["productCategory"] == "command_conflict"
    assert response.error.details["recoveryActions"] == ["refresh_snapshot"]
    assert commands.calls == []


def test_stop_task_wraps_published_active_task_command() -> None:
    commands = _TaskCommands(
        CoreCommandResult(
            command_id="backend-stop",
            status="accepted",
            message="task stop requested",
            affected_task_refs=(TaskRef.published("task-1"),),
        )
    )
    gateway = _gateway(task_commands=commands)
    request = CommandRequest[StopTaskPayload](
        command_id="stop-1",
        session_id="session-1",
        payload=StopTaskPayload(reason="Stop after safe point"),
    )

    response = gateway.stop_task("task-1", request)

    assert response.ok is True
    assert commands.calls == [
        (
            "stop_task",
            {
                "session_id": "session-1",
                "task_id": "task-1",
                "reason": "Stop after safe point",
                "request_id": "stop-1",
            },
        )
    ]
    assert response.result is not None
    body = response.result.model_dump(mode="json")
    assert {"kind": "published_task", "id": "task-1"} in body["objectRefs"]
    assert {
        "ref": {"kind": "published_task", "id": "task-1"},
        "impact": "changed",
        "reason": "Stop intent was recorded for this Task.",
    } in body["affectedObjects"]
    assert response.refresh.suggested_queries == (
        "session.snapshot",
        "task.tree",
        "task.detail",
    )
    assert {scope.kind for scope in response.refresh.affected_scopes} == {
        "task_tree",
        "task_detail",
        "messages",
    }


def test_stop_task_rejects_draft_task_ref() -> None:
    commands = _TaskCommands()
    gateway = _gateway(
        task_commands=commands,
        resolver=_Resolver({"draft-1": TaskRef.draft("draft-1")}),
    )
    request = CommandRequest[StopTaskPayload](
        command_id="stop-draft",
        session_id="session-1",
        payload=StopTaskPayload(),
    )

    response = gateway.stop_task("draft-1", request)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "command_rejected"
    assert commands.calls == []


def test_resolve_confirmation_rejection_maps_to_command_rejected_error() -> None:
    commands = _TaskCommands(
        CoreCommandResult(
            command_id="backend-reject",
            status="rejected",
            message="confirmation not found",
        )
    )
    gateway = _gateway(task_commands=commands)
    request = CommandRequest[ResolveConfirmationPayload](
        command_id="resolve-1",
        session_id="session-1",
        payload=ResolveConfirmationPayload(value="yes", note="Looks good"),
    )

    response = gateway.resolve_confirmation("confirmation-1", request)

    assert response.ok is False
    assert response.result is not None
    assert response.result.status == "rejected"
    assert response.error is not None
    assert response.error.code == "command_rejected"
    assert response.refresh.wait_for_events is False


def test_answer_ask_wraps_ask_command_refs_and_refresh_scopes() -> None:
    ask_commands = _AskCommands()
    gateway = _gateway(ask_commands=ask_commands)
    request = CommandRequest[AnswerAskPayload](
        command_id="answer-1",
        session_id="session-1",
        idempotency_key="answer-key",
        payload=AnswerAskPayload(text="Use Vercel."),
    )

    response = gateway.answer_ask("ask-1", request)

    assert response.ok is True
    assert ask_commands.calls == [
        (
            "answer_ask",
            {
                "session_id": "session-1",
                "ask_id": "ask-1",
                "selected_option_ids": (),
                "text": "Use Vercel.",
                "idempotency_key": "answer-key",
                "command_id": "answer-1",
            },
        )
    ]
    assert response.result is not None
    body = response.result.model_dump(mode="json")
    assert {"kind": "ask", "id": "ask-1"} in body["objectRefs"]
    assert {
        "ref": {"kind": "ask", "id": "ask-1"},
        "impact": "changed",
        "reason": "ASK was answered.",
    } in body["affectedObjects"]
    assert response.refresh.suggested_queries == (
        "session.snapshot",
        "asks",
        "task.tree",
        "task.detail",
    )
    assert {scope.kind for scope in response.refresh.affected_scopes} == {
        "asks",
        "task_tree",
        "task_detail",
    }


def test_defer_and_cancel_ask_delegate_to_ask_commands() -> None:
    ask_commands = _AskCommands()
    gateway = _gateway(ask_commands=ask_commands)

    defer = gateway.defer_ask(
        "ask-1",
        CommandRequest[DeferAskPayload](
            command_id="defer-1",
            session_id="session-1",
            payload=DeferAskPayload(reason="Need more context later."),
        ),
    )
    cancel = gateway.cancel_ask(
        "ask-1",
        CommandRequest[CancelAskPayload](
            command_id="cancel-1",
            session_id="session-1",
            payload=CancelAskPayload(reason="User cancelled the ASK."),
        ),
    )

    assert defer.ok is True
    assert cancel.ok is True
    assert [call[0] for call in ask_commands.calls] == ["defer_ask", "cancel_ask"]
    assert defer.result is not None
    assert cancel.result is not None
    assert {
        "ref": {"kind": "ask", "id": "ask-1"},
        "impact": "changed",
        "reason": "ASK was deferred.",
    } in defer.result.model_dump(mode="json")["affectedObjects"]
    assert {
        "ref": {"kind": "ask", "id": "ask-1"},
        "impact": "changed",
        "reason": "ASK was cancelled.",
    } in cancel.result.model_dump(mode="json")["affectedObjects"]


def test_answer_ask_rejects_when_service_is_not_configured() -> None:
    gateway = _gateway()
    request = CommandRequest[AnswerAskPayload](
        command_id="answer-1",
        session_id="session-1",
        payload=AnswerAskPayload(text="Use Vercel."),
    )

    response = gateway.answer_ask("ask-1", request)

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "command_rejected"


def test_task_ref_resolver_miss_returns_not_found() -> None:
    gateway = _gateway(resolver=_Resolver({}))
    request = CommandRequest[UpdateTaskNodePayload](
        command_id="update-missing",
        session_id="session-1",
        payload=UpdateTaskNodePayload(title="New title"),
    )

    response = gateway.update_task_node("missing", request)

    assert response.ok is False
    assert response.result is None
    assert response.error is not None
    assert response.error.code == "not_found"
