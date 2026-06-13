"""Tests for AuthoringCommandService handlers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from taskweavn.interaction import AgentMessage
from taskweavn.task import (
    ActiveAuthoringState,
    ActorRef,
    AuthoringCommandBatch,
    AuthoringCommandService,
    DefaultAuthoringCommandService,
    DraftTaskNode,
    DraftTaskTreeOperation,
    DraftTaskTreeValidator,
    DraftToPublishedMapping,
    InMemoryAuthoringCommandIdempotencyStore,
    InMemoryDraftTaskStore,
    InMemoryRawTaskStore,
    MutateDraftTaskTreeCommand,
    MutateRawTaskCommand,
    Plan,
    PlanTaskNode,
    PublishDraftTaskTreeCommand,
    RawTask,
    RawTaskOperation,
    StaticCapabilityCatalog,
    TaskPublishResult,
    TaskRef,
)


class _MessageBus:
    def __init__(self) -> None:
        self.messages: list[AgentMessage] = []

    def publish(self, message: AgentMessage) -> None:
        self.messages.append(message)


class _Publisher:
    kind: Any = "collaborator"

    def __init__(self, result: TaskPublishResult) -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def preview(self, request: Any) -> Any:
        raise NotImplementedError

    def publish(self, request: Any) -> Any:
        raise NotImplementedError

    def publish_draft_tree(self, session_id: str, draft_tree_id: str) -> TaskPublishResult:
        self.calls.append((session_id, draft_tree_id))
        return self.result

    def retry_task(
        self,
        session_id: str,
        task_id: str,
        instruction: str | None = None,
    ) -> TaskPublishResult:
        raise NotImplementedError


class _PlanStore:
    def __init__(self) -> None:
        self.created_plans: list[Plan] = []
        self.created_nodes: list[PlanTaskNode] = []

    def create_plan(
        self,
        plan: Plan,
        task_nodes: Sequence[PlanTaskNode] = (),
    ) -> Plan:
        saved = plan.model_copy(
            update={"task_node_ids": tuple(node.task_node_id for node in task_nodes)}
        )
        self.created_plans.append(saved)
        self.created_nodes.extend(task_nodes)
        return saved

    def get_plan(self, session_id: str, plan_id: str) -> Plan | None:
        return next(
            (
                plan
                for plan in self.created_plans
                if plan.session_id == session_id and plan.plan_id == plan_id
            ),
            None,
        )

    def list_plans(self, session_id: str) -> list[Plan]:
        return [plan for plan in self.created_plans if plan.session_id == session_id]

    def get_active_plan(self, session_id: str) -> Plan | None:
        plans = self.list_plans(session_id)
        return plans[-1] if plans else None

    def save_plan(self, plan: Plan, *, expected_version: int) -> Plan:
        raise NotImplementedError

    def get_task_node(self, session_id: str, task_node_id: str) -> PlanTaskNode | None:
        return next(
            (
                node
                for node in self.created_nodes
                if node.session_id == session_id and node.task_node_id == task_node_id
            ),
            None,
        )

    def list_task_nodes(self, session_id: str, plan_id: str) -> list[PlanTaskNode]:
        return [
            node
            for node in self.created_nodes
            if node.session_id == session_id and node.plan_id == plan_id
        ]

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


class _AuthoringStateStore:
    def __init__(self) -> None:
        self.active = ActiveAuthoringState(session_id="s1", active_state="none")

    def get_active(self, session_id: str) -> ActiveAuthoringState:
        return self.active

    def set_active_raw_task(self, session_id: str, raw_task_id: str) -> None:
        self.active = ActiveAuthoringState(
            session_id=session_id,
            active_raw_task_id=raw_task_id,
            active_state="raw_task",
        )

    def set_active_draft_tree(
        self,
        session_id: str,
        raw_task_id: str | None,
        draft_tree_id: str,
        *,
        active_plan_id: str | None = None,
    ) -> None:
        self.active = ActiveAuthoringState(
            session_id=session_id,
            active_raw_task_id=raw_task_id,
            active_draft_tree_id=draft_tree_id,
            active_plan_id=active_plan_id,
            active_state="draft_tree",
        )

    def mark_published(self, session_id: str, draft_tree_id: str) -> None:
        self.active = ActiveAuthoringState(
            session_id=session_id,
            active_raw_task_id=self.active.active_raw_task_id,
            active_draft_tree_id=draft_tree_id,
            active_plan_id=self.active.active_plan_id,
            active_state="published",
        )

    def cancel_active(self, session_id: str) -> None:
        self.active = ActiveAuthoringState(
            session_id=session_id,
            active_raw_task_id=self.active.active_raw_task_id,
            active_draft_tree_id=self.active.active_draft_tree_id,
            active_plan_id=self.active.active_plan_id,
            active_state="cancelled",
        )


def _actor() -> ActorRef:
    return ActorRef(actor_id="collaborator", kind="collaborator")


def _service(
    *,
    raw_store: InMemoryRawTaskStore | None = None,
    draft_store: InMemoryDraftTaskStore | None = None,
    bus: _MessageBus | None = None,
    publisher: _Publisher | None = None,
    validator: DraftTaskTreeValidator | None = None,
    idempotency_store: InMemoryAuthoringCommandIdempotencyStore | None = None,
    authoring_state_store: _AuthoringStateStore | None = None,
    plan_store: _PlanStore | None = None,
) -> DefaultAuthoringCommandService:
    return DefaultAuthoringCommandService(
        raw_task_store=raw_store or InMemoryRawTaskStore(),
        draft_store=draft_store or InMemoryDraftTaskStore(),
        message_bus=bus,  # type: ignore[arg-type]
        task_publisher=publisher,
        draft_validator=validator,
        authoring_state_store=authoring_state_store,
        plan_store=plan_store,
        idempotency_store=idempotency_store,
    )


def _raw_create_command(
    *,
    raw_task_id: str = "raw1",
    command_id: str = "cmd-raw",
) -> MutateRawTaskCommand:
    return MutateRawTaskCommand(
        command_id=command_id,
        session_id="s1",
        actor=_actor(),
        operations=(
            RawTaskOperation(
                op="create",
                payload={
                    "raw_task_id": raw_task_id,
                    "source_message_id": "m1",
                    "user_input": "Build a docs site",
                },
            ),
        ),
    )


def test_authoring_command_service_protocol_conformance() -> None:
    assert isinstance(_service(), AuthoringCommandService)


def test_submit_creates_raw_task_and_is_idempotent() -> None:
    raw_store = InMemoryRawTaskStore()
    service = _service(raw_store=raw_store)
    batch = AuthoringCommandBatch(
        batch_id="batch1",
        session_id="s1",
        actor=_actor(),
        idempotency_key="raw-create",
        commands=(_raw_create_command(),),
    )

    first = service.submit(batch)
    second = service.submit(batch)

    assert first.ok
    assert second == first
    assert raw_store.get("s1", "raw1") is not None
    assert len(raw_store.list_for_session("s1")) == 1


def test_submit_replays_idempotent_result_across_service_instances() -> None:
    raw_store = InMemoryRawTaskStore()
    idempotency_store = InMemoryAuthoringCommandIdempotencyStore()
    batch = AuthoringCommandBatch(
        batch_id="batch1",
        session_id="s1",
        actor=_actor(),
        idempotency_key="raw-create",
        commands=(_raw_create_command(),),
    )

    first = _service(
        raw_store=raw_store,
        idempotency_store=idempotency_store,
    ).submit(batch)
    second = _service(
        raw_store=raw_store,
        idempotency_store=idempotency_store,
    ).submit(batch.model_copy(update={"batch_id": "batch2"}))

    assert first.ok
    assert second == first
    assert len(raw_store.list_for_session("s1")) == 1


def test_submit_mutates_raw_task_clarification_flow() -> None:
    raw_store = InMemoryRawTaskStore(
        [
            RawTask(
                raw_task_id="raw1",
                session_id="s1",
                source_message_id="m1",
                user_input="Build something",
            )
        ]
    )
    service = _service(raw_store=raw_store)
    ask_command = MutateRawTaskCommand(
        command_id="ask",
        session_id="s1",
        raw_task_id="raw1",
        actor=_actor(),
        operations=(
            RawTaskOperation(
                op="add_clarification_ask",
                payload={
                    "ask_id": "ask1",
                    "question": "Who is the audience?",
                    "reason": "Need scope",
                },
            ),
        ),
    )
    answer_command = MutateRawTaskCommand(
        command_id="answer",
        session_id="s1",
        raw_task_id="raw1",
        expected_version=2,
        actor=_actor(),
        operations=(
            RawTaskOperation(
                op="apply_answer",
                payload={
                    "ask_id": "ask1",
                    "value": "Developers",
                    "source_message_id": "m2",
                },
            ),
        ),
    )

    ask_result = service.submit(
        AuthoringCommandBatch(session_id="s1", actor=_actor(), commands=(ask_command,))
    )
    answer_result = service.submit(
        AuthoringCommandBatch(session_id="s1", actor=_actor(), commands=(answer_command,))
    )
    raw = raw_store.get("s1", "raw1")

    assert ask_result.ok
    assert answer_result.ok
    assert raw is not None
    assert raw.status == "assessing"
    assert raw.answers[0].value == "Developers"


def test_submit_rejects_answering_already_answered_raw_task_ask() -> None:
    raw_store = InMemoryRawTaskStore(
        [
            RawTask(
                raw_task_id="raw1",
                session_id="s1",
                source_message_id="m1",
                user_input="Build something",
            )
        ]
    )
    service = _service(raw_store=raw_store)
    ask_command = MutateRawTaskCommand(
        command_id="ask",
        session_id="s1",
        raw_task_id="raw1",
        actor=_actor(),
        operations=(
            RawTaskOperation(
                op="add_clarification_ask",
                payload={
                    "ask_id": "ask1",
                    "question": "Who is the audience?",
                    "reason": "Need scope",
                },
            ),
        ),
    )
    answer_command = MutateRawTaskCommand(
        command_id="answer",
        session_id="s1",
        raw_task_id="raw1",
        expected_version=2,
        actor=_actor(),
        operations=(
            RawTaskOperation(
                op="apply_answer",
                payload={
                    "ask_id": "ask1",
                    "value": "Developers",
                    "source_message_id": "m2",
                },
            ),
        ),
    )
    duplicate_answer = answer_command.model_copy(
        update={"command_id": "duplicate-answer", "expected_version": 3}
    )

    service.submit(
        AuthoringCommandBatch(session_id="s1", actor=_actor(), commands=(ask_command,))
    )
    first = service.submit(
        AuthoringCommandBatch(session_id="s1", actor=_actor(), commands=(answer_command,))
    )
    second = service.submit(
        AuthoringCommandBatch(
            session_id="s1",
            actor=_actor(),
            commands=(duplicate_answer,),
        )
    )
    raw = raw_store.get("s1", "raw1")

    assert first.ok
    assert not second.ok
    assert "already answered" in second.errors[0].message
    assert raw is not None
    assert len(raw.answers) == 1


def test_submit_creates_draft_tree_with_children() -> None:
    draft_store = InMemoryDraftTaskStore()
    service = _service(draft_store=draft_store)
    command = MutateDraftTaskTreeCommand(
        command_id="draft-create",
        session_id="s1",
        actor=_actor(),
        operations=(
            DraftTaskTreeOperation(
                op="create_tree",
                payload={
                    "roots": [
                        {
                            "draft_task_id": "root",
                            "title": "Root",
                            "intent": "Build app",
                            "required_capability": "general",
                            "children": [
                                {
                                    "draft_task_id": "child",
                                    "title": "Child",
                                    "intent": "Write tests",
                                    "required_capability": "testing",
                                }
                            ],
                        }
                    ]
                },
            ),
        ),
    )

    result = service.submit(
        AuthoringCommandBatch(session_id="s1", actor=_actor(), commands=(command,))
    )
    tree = draft_store.list_trees("s1")[0]
    child = draft_store.get_node("s1", "child")

    assert result.ok
    assert {ref.id for ref in result.object_refs} == {"root", "child"}
    assert child is not None
    assert child.parent_draft_task_id == "root"
    assert len(draft_store.list_nodes("s1", tree.draft_tree_id)) == 2


def test_submit_creates_durable_plan_from_draft_tree_and_records_active_identity() -> None:
    draft_store = InMemoryDraftTaskStore()
    plan_store = _PlanStore()
    state_store = _AuthoringStateStore()
    service = _service(
        draft_store=draft_store,
        authoring_state_store=state_store,
        plan_store=plan_store,
    )
    command = MutateDraftTaskTreeCommand(
        command_id="draft-create",
        session_id="s1",
        raw_task_id="raw1",
        actor=_actor(),
        operations=(
            DraftTaskTreeOperation(
                op="create_tree",
                payload={
                    "title": "Website plan",
                    "summary": "Build a website.",
                    "roots": [
                        {
                            "draft_task_id": "root",
                            "title": "Root",
                            "intent": "Build app",
                            "required_capability": "general",
                            "children": [
                                {
                                    "draft_task_id": "child",
                                    "title": "Child",
                                    "intent": "Write tests",
                                    "summary": "Test app",
                                    "required_capability": "testing",
                                }
                            ],
                        }
                    ],
                },
            ),
        ),
    )

    result = service.submit(
        AuthoringCommandBatch(session_id="s1", actor=_actor(), commands=(command,))
    )

    assert result.ok
    assert len(plan_store.created_plans) == 1
    plan = plan_store.created_plans[0]
    assert plan.title == "Website plan"
    assert plan.source_raw_task_id == "raw1"
    assert plan.source_draft_tree_id == state_store.active.active_draft_tree_id
    assert state_store.active.active_plan_id == plan.plan_id
    assert state_store.active.active_state == "draft_tree"
    assert plan.task_node_ids == ("root", "child")
    assert [(node.task_node_id, node.task_index) for node in plan_store.created_nodes] == [
        ("root", "1"),
        ("child", "1.1"),
    ]
    assert plan_store.created_nodes[0].draft_ref == TaskRef.draft("root")
    assert plan_store.created_nodes[1].summary == "Test app"


def test_submit_patches_draft_node_and_publishes_option_effect() -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "s1",
        [
            _draft_node_payload(
                "root",
                title="Old",
                intent="Old intent",
                capability="general",
            )
        ],
    )
    bus = _MessageBus()
    service = _service(draft_store=draft_store, bus=bus)
    command = MutateDraftTaskTreeCommand(
        command_id="patch",
        session_id="s1",
        draft_tree_id=tree.draft_tree_id,
        actor=_actor(),
        operations=(
            DraftTaskTreeOperation(
                op="patch_node",
                payload={"draft_task_id": "root", "patch": {"title": "New"}},
            ),
            DraftTaskTreeOperation(
                op="attach_options",
                payload={
                    "draft_task_id": "root",
                    "content": "Pick one",
                    "options": ["small", "large"],
                },
            ),
        ),
    )

    result = service.submit(
        AuthoringCommandBatch(session_id="s1", actor=_actor(), commands=(command,))
    )
    node = draft_store.get_node("s1", "root")

    assert result.ok
    assert result.emitted_message_ids == (bus.messages[0].message_id,)
    assert node is not None
    assert node.title == "New"
    assert bus.messages[0].message_type == "actionable"
    assert bus.messages[0].action_options == ["small", "large"]


def test_all_or_nothing_rolls_back_on_failure() -> None:
    raw_store = InMemoryRawTaskStore()
    service = _service(raw_store=raw_store)
    invalid_patch = MutateDraftTaskTreeCommand(
        command_id="bad-draft",
        session_id="s1",
        draft_tree_id="missing-tree",
        actor=_actor(),
        operations=(
            DraftTaskTreeOperation(
                op="patch_node",
                payload={"draft_task_id": "missing", "patch": {"title": "Nope"}},
            ),
        ),
    )
    batch = AuthoringCommandBatch(
        session_id="s1",
        actor=_actor(),
        commands=(_raw_create_command(), invalid_patch),
    )

    result = service.submit(batch)

    assert not result.ok
    assert raw_store.get("s1", "raw1") is None


def test_best_effort_keeps_successful_commands() -> None:
    raw_store = InMemoryRawTaskStore()
    service = _service(raw_store=raw_store)
    invalid_patch = MutateDraftTaskTreeCommand(
        command_id="bad-draft",
        session_id="s1",
        draft_tree_id="missing-tree",
        actor=_actor(),
        operations=(
            DraftTaskTreeOperation(
                op="patch_node",
                payload={"draft_task_id": "missing", "patch": {"title": "Nope"}},
            ),
        ),
    )
    batch = AuthoringCommandBatch(
        session_id="s1",
        actor=_actor(),
        mode="best_effort",
        commands=(_raw_create_command(), invalid_patch),
    )

    result = service.submit(batch)

    assert not result.ok
    assert result.applied_command_ids == ("cmd-raw",)
    assert raw_store.get("s1", "raw1") is not None


def test_publish_command_publishes_accepted_tree_and_records_mapping() -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "s1",
        [
            _draft_node_payload(
                "root",
                title="Root",
                intent="Do work",
                capability="general",
            )
        ],
    )
    accepted = draft_store.mark_accepted("s1", tree.draft_tree_id, expected_version=tree.version)
    publisher = _Publisher(
        TaskPublishResult(
            root_task_ids=("task-root",),
            mappings=(
                DraftToPublishedMapping(
                    session_id="s1",
                    draft_tree_id=tree.draft_tree_id,
                    draft_task_id="root",
                    task_id="task-root",
                    publish_command_id="publish",
                ),
            ),
        )
    )
    bus = _MessageBus()
    service = _service(
        draft_store=draft_store,
        bus=bus,
        publisher=publisher,
        validator=DraftTaskTreeValidator(
            capability_catalog=StaticCapabilityCatalog(["general"])
        ),
    )
    command = PublishDraftTaskTreeCommand(
        command_id="publish",
        session_id="s1",
        draft_tree_id=tree.draft_tree_id,
        expected_version=accepted.version,
        actor=_actor(),
        idempotency_key="publish-root",
    )
    batch = AuthoringCommandBatch(session_id="s1", actor=_actor(), commands=(command,))

    result = service.submit(batch)
    repeated = service.submit(batch)
    node = draft_store.get_node("s1", "root")

    assert result.ok
    assert repeated == result
    assert publisher.calls == [("s1", tree.draft_tree_id)]
    assert node is not None
    assert node.status == "published"
    assert draft_store.list_for_draft("s1", "root")[0].task_id == "task-root"
    assert result.object_refs[0].id == "task-root"
    assert result.emitted_message_ids == (bus.messages[0].message_id,)
    assert bus.messages[0].message_type == "informational"


def test_publish_rejects_unaccepted_tree_before_publisher_call() -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "s1",
        [
            _draft_node_payload(
                "root",
                title="Root",
                intent="Do work",
                capability="general",
            )
        ],
    )
    publisher = _Publisher(TaskPublishResult(root_task_ids=("task-root",)))
    service = _service(draft_store=draft_store, publisher=publisher)
    command = PublishDraftTaskTreeCommand(
        command_id="publish",
        session_id="s1",
        draft_tree_id=tree.draft_tree_id,
        actor=_actor(),
        idempotency_key="publish-root",
    )

    result = service.submit(
        AuthoringCommandBatch(session_id="s1", actor=_actor(), commands=(command,))
    )

    assert not result.ok
    assert "accepted" in result.errors[0].message
    assert publisher.calls == []


def test_publish_rejects_invalid_tree_before_publisher_call() -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "s1",
        [
            _draft_node_payload(
                "root",
                title="Root",
                intent="Do work",
                capability="unknown",
            )
        ],
    )
    accepted = draft_store.mark_accepted("s1", tree.draft_tree_id, expected_version=tree.version)
    publisher = _Publisher(TaskPublishResult(root_task_ids=("task-root",)))
    service = _service(
        draft_store=draft_store,
        publisher=publisher,
        validator=DraftTaskTreeValidator(
            capability_catalog=StaticCapabilityCatalog(["general"])
        ),
    )
    command = PublishDraftTaskTreeCommand(
        command_id="publish",
        session_id="s1",
        draft_tree_id=tree.draft_tree_id,
        expected_version=accepted.version,
        actor=_actor(),
        idempotency_key="publish-root",
    )

    result = service.submit(
        AuthoringCommandBatch(session_id="s1", actor=_actor(), commands=(command,))
    )

    assert not result.ok
    assert "validation failed" in result.errors[0].message
    assert publisher.calls == []


def test_publish_rejects_duplicate_publish_with_new_key() -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "s1",
        [
            _draft_node_payload(
                "root",
                title="Root",
                intent="Do work",
                capability="general",
            )
        ],
    )
    accepted = draft_store.mark_accepted("s1", tree.draft_tree_id, expected_version=tree.version)
    mapping = DraftToPublishedMapping(
        session_id="s1",
        draft_tree_id=tree.draft_tree_id,
        draft_task_id="root",
        task_id="task-root",
        publish_command_id="publish",
    )
    first_publisher = _Publisher(
        TaskPublishResult(root_task_ids=("task-root",), mappings=(mapping,))
    )
    service = _service(draft_store=draft_store, publisher=first_publisher)
    first = PublishDraftTaskTreeCommand(
        command_id="publish",
        session_id="s1",
        draft_tree_id=tree.draft_tree_id,
        expected_version=accepted.version,
        actor=_actor(),
        idempotency_key="publish-root",
    )

    assert service.submit(
        AuthoringCommandBatch(session_id="s1", actor=_actor(), commands=(first,))
    ).ok

    second_publisher = _Publisher(
        TaskPublishResult(root_task_ids=("other-root",), mappings=(mapping,))
    )
    service = _service(draft_store=draft_store, publisher=second_publisher)
    second = first.model_copy(update={"idempotency_key": "publish-root-again"})
    result = service.submit(
        AuthoringCommandBatch(session_id="s1", actor=_actor(), commands=(second,))
    )

    assert not result.ok
    assert "already published" in result.errors[0].message
    assert second_publisher.calls == []


def test_publish_rejects_publisher_rejection_without_marking_published() -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "s1",
        [
            _draft_node_payload(
                "root",
                title="Root",
                intent="Do work",
                capability="general",
            )
        ],
    )
    accepted = draft_store.mark_accepted("s1", tree.draft_tree_id, expected_version=tree.version)
    publisher = _Publisher(
        TaskPublishResult(root_task_ids=(), rejected_task_ids=("root",))
    )
    service = _service(draft_store=draft_store, publisher=publisher)
    command = PublishDraftTaskTreeCommand(
        command_id="publish",
        session_id="s1",
        draft_tree_id=tree.draft_tree_id,
        expected_version=accepted.version,
        actor=_actor(),
        idempotency_key="publish-root",
    )

    result = service.submit(
        AuthoringCommandBatch(session_id="s1", actor=_actor(), commands=(command,))
    )
    node = draft_store.get_node("s1", "root")

    assert not result.ok
    assert publisher.calls == [("s1", tree.draft_tree_id)]
    assert node is not None
    assert node.status == "accepted"


def _draft_node_payload(
    draft_task_id: str,
    *,
    title: str,
    intent: str,
    capability: str,
) -> DraftTaskNode:
    return DraftTaskNode(
        draft_task_id=draft_task_id,
        session_id="s1",
        draft_tree_id="placeholder",
        title=title,
        intent=intent,
        required_capability=capability,
    )
