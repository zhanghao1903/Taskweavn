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
    InMemoryDraftTaskStore,
    InMemoryRawTaskStore,
    MutateDraftTaskTreeCommand,
    MutateRawTaskCommand,
    PublishDraftTaskTreeCommand,
    RawTask,
    RawTaskOperation,
)


class _MessageBus:
    def __init__(self) -> None:
        self.messages: list[AgentMessage] = []

    def publish(self, message: AgentMessage) -> None:
        self.messages.append(message)


def _actor() -> ActorRef:
    return ActorRef(actor_id="collaborator", kind="collaborator")


def _service(
    *,
    raw_store: InMemoryRawTaskStore | None = None,
    draft_store: InMemoryDraftTaskStore | None = None,
    bus: _MessageBus | None = None,
) -> DefaultAuthoringCommandService:
    return DefaultAuthoringCommandService(
        raw_task_store=raw_store or InMemoryRawTaskStore(),
        draft_store=draft_store or InMemoryDraftTaskStore(),
        message_bus=bus,  # type: ignore[arg-type]
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


def test_publish_command_is_explicitly_deferred_to_publish_slice() -> None:
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
    service = _service(draft_store=draft_store)
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
    assert result.errors[0].code == "not_implemented"


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
