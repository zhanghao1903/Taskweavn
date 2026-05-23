"""Tests for framework-neutral UI command gateway."""

from __future__ import annotations

from dataclasses import dataclass, field

from taskweavn.server.ui_contract import (
    AppendSessionInputPayload,
    AppendTaskInputPayload,
    CommandRequest,
    DefaultUiCommandGateway,
    GenerateTaskTreePayload,
    PublishTaskTreePayload,
    ResolveConfirmationPayload,
    TaskRefResolver,
    UiCommandGateway,
    UpdateTaskNodePayload,
)
from taskweavn.task import CommandResult as CoreCommandResult
from taskweavn.task import TaskNodePatch, TaskRef


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
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "append_session_message",
                {
                    "session_id": session_id,
                    "content": content,
                    "source_message_id": source_message_id,
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

    def generate_task_tree(
        self,
        *,
        session_id: str,
        raw_task_id: str | None = None,
    ) -> CoreCommandResult:
        self.calls.append(
            (
                "generate_task_tree",
                {"session_id": session_id, "raw_task_id": raw_task_id},
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
        raise NotImplementedError


@dataclass(frozen=True)
class _Resolver:
    refs: dict[str, TaskRef]

    def resolve(self, session_id: str, task_node_id: str) -> TaskRef:
        try:
            return self.refs[task_node_id]
        except KeyError as exc:
            raise LookupError(f"task node {task_node_id!r} not found") from exc


def _gateway(
    *,
    collaborator: _Collaborator | None = None,
    task_commands: _TaskCommands | None = None,
    resolver: _Resolver | None = None,
) -> DefaultUiCommandGateway:
    return DefaultUiCommandGateway(
        collaborator=collaborator or _Collaborator(),
        task_commands=task_commands or _TaskCommands(),
        task_ref_resolver=resolver
        or _Resolver({"draft-1": TaskRef.draft("draft-1"), "task-1": TaskRef.published("task-1")}),
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
        {"session_id": "session-1", "raw_task_id": "raw-1"},
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
            },
        ),
        ("generate_task_tree", {"session_id": "session-1", "raw_task_id": None}),
    ]


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
