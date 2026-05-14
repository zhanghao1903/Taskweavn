"""Tests for AuthoringCommandService handlers."""

from __future__ import annotations

from taskweavn.interaction import AgentMessage
from taskweavn.task import (
    ActorRef,
    AuthoringCommandBatch,
    AuthoringCommandService,
    DefaultAuthoringCommandService,
    DraftTaskNode,
    DraftTaskTreeOperation,
    DraftTaskTreeValidator,
    DraftToPublishedMapping,
    InMemoryDraftTaskStore,
    InMemoryRawTaskStore,
    MutateDraftTaskTreeCommand,
    MutateRawTaskCommand,
    PublishDraftTaskTreeCommand,
    RawTask,
    RawTaskOperation,
    StaticCapabilityCatalog,
    TaskPublishResult,
)


class _MessageBus:
    def __init__(self) -> None:
        self.messages: list[AgentMessage] = []

    def publish(self, message: AgentMessage) -> None:
        self.messages.append(message)


class _Publisher:
    def __init__(self, result: TaskPublishResult) -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

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


def _actor() -> ActorRef:
    return ActorRef(actor_id="collaborator", kind="collaborator")


def _service(
    *,
    raw_store: InMemoryRawTaskStore | None = None,
    draft_store: InMemoryDraftTaskStore | None = None,
    bus: _MessageBus | None = None,
    publisher: _Publisher | None = None,
    validator: DraftTaskTreeValidator | None = None,
) -> DefaultAuthoringCommandService:
    return DefaultAuthoringCommandService(
        raw_task_store=raw_store or InMemoryRawTaskStore(),
        draft_store=draft_store or InMemoryDraftTaskStore(),
        message_bus=bus,  # type: ignore[arg-type]
        task_publisher=publisher,
        draft_validator=validator,
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
