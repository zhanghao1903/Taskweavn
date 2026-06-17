from __future__ import annotations

from dataclasses import dataclass, field

from taskweavn.context import ContextBuildRequest
from taskweavn.contract_revision import (
    ContractGuidanceContextSource,
    ContractInteractionCommandOutcome,
    ContractRevisionCommandService,
    ContractTaskNodeCommandOutcome,
    InMemoryContractCommandIdempotencyStore,
    InMemoryGuidanceFactStore,
    SqliteContractCommandIdempotencyStore,
    SqliteGuidanceFactStore,
)
from taskweavn.contract_revision.models import ContractCommandRequest
from taskweavn.server.ui_contract import CommandResponse, CommandResult


def test_record_guidance_persists_fact_and_result_metadata() -> None:
    guidance_store = InMemoryGuidanceFactStore()
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=guidance_store,
        workspace_id="workspace-1",
    )

    result = service.execute(_guidance_request())

    assert result.status == "accepted"
    assert result.side_effect == "context_effect"
    assert result.guidance_id is not None
    assert result.activity is not None
    assert result.activity.title == "Guidance recorded"
    assert result.diagnostics is not None
    assert result.diagnostics.preview == "Keep the implementation small."
    facts = guidance_store.list_for_scope(session_id="session-1")
    assert len(facts) == 1
    assert facts[0].guidance_text == "Keep the implementation small."
    assert facts[0].source_router_decision_id == "rir-1"


def test_record_guidance_idempotent_replay_does_not_duplicate_fact() -> None:
    guidance_store = InMemoryGuidanceFactStore()
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=guidance_store,
        workspace_id="workspace-1",
    )
    request = _guidance_request()

    first = service.execute(request)
    second = service.execute(request)

    assert second == first
    assert len(guidance_store.list_for_scope(session_id="session-1")) == 1


def test_record_guidance_idempotency_conflict_does_not_mutate() -> None:
    guidance_store = InMemoryGuidanceFactStore()
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=guidance_store,
        workspace_id="workspace-1",
    )

    first = service.execute(_guidance_request())
    conflict = service.execute(
        _guidance_request(payload={"guidanceText": "Use a different constraint."})
    )

    assert first.status == "accepted"
    assert conflict.status == "conflict"
    assert conflict.reason_code == "idempotency_conflict"
    assert len(guidance_store.list_for_scope(session_id="session-1")) == 1


def test_sqlite_contract_revision_stores_round_trip(tmp_path) -> None:
    db = tmp_path / "contract_revision.sqlite"
    idempotency_store = SqliteContractCommandIdempotencyStore(db)
    guidance_store = SqliteGuidanceFactStore(db)
    try:
        service = ContractRevisionCommandService(
            idempotency_store=idempotency_store,
            guidance_store=guidance_store,
            workspace_id="workspace-1",
        )
        result = service.execute(_guidance_request())
        assert result.guidance_id is not None
    finally:
        idempotency_store.close()
        guidance_store.close()

    reopened_guidance_store = SqliteGuidanceFactStore(db)
    reopened_idempotency_store = SqliteContractCommandIdempotencyStore(db)
    try:
        facts = reopened_guidance_store.list_for_scope(session_id="session-1")
        assert len(facts) == 1
        assert facts[0].guidance_text == "Keep the implementation small."
        cached = reopened_idempotency_store.get("session-1", "idem-1")
        assert cached is not None
        assert cached.result is not None
        assert cached.result.guidance_id == result.guidance_id
    finally:
        reopened_idempotency_store.close()
        reopened_guidance_store.close()


def test_contract_guidance_context_source_maps_guidance_to_execution_guidance() -> None:
    guidance_store = InMemoryGuidanceFactStore()
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=guidance_store,
        workspace_id="workspace-1",
    )
    service.execute(_guidance_request(task_node_id="task-1"))
    source = ContractGuidanceContextSource(guidance_store)

    guidance = source.collect(
        ContextBuildRequest(
            session_id="session-1",
            task_id="task-1",
            agent_id="agent",
            agent_run_id="run-1",
            purpose="execution_step",
            turn_index=1,
        )
    )

    assert guidance.project_rules == (
        "[task/instruction] Keep the implementation small.",
    )


def test_contract_guidance_context_source_includes_session_guidance_for_task() -> None:
    guidance_store = InMemoryGuidanceFactStore()
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=guidance_store,
        workspace_id="workspace-1",
    )
    service.execute(_guidance_request())
    service.execute(
        _guidance_request(
            payload={"guidanceText": "Use compact HTML."},
            task_node_id="task-1",
            command_id="cmd-2",
            idempotency_key="idem-2",
        )
    )
    source = ContractGuidanceContextSource(guidance_store)

    guidance = source.collect(
        ContextBuildRequest(
            session_id="session-1",
            task_id="task-1",
            agent_id="agent",
            agent_run_id="run-1",
            purpose="execution_step",
            turn_index=1,
        )
    )

    assert guidance.project_rules == (
        "[session/instruction] Keep the implementation small.",
        "[task/instruction] Use compact HTML.",
    )


def test_resolve_ask_delegates_to_interaction_handler_and_is_idempotent() -> None:
    handler = _InteractionHandler()
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=InMemoryGuidanceFactStore(),
        workspace_id="workspace-1",
        interaction_handler=handler,
    )
    request = _ask_request()

    first = service.execute(request)
    replay = service.execute(request)

    assert first.status == "accepted"
    assert first.side_effect == "resume_effect"
    assert first.ask_id == "ask-1"
    assert first.activity is not None
    assert first.activity.title == "ASK answered"
    assert first.command_response is not None
    assert replay == first
    assert handler.calls == [("ask", "ask-1", "Use Vercel.")]


def test_resolve_confirmation_delegates_to_interaction_handler() -> None:
    handler = _InteractionHandler()
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=InMemoryGuidanceFactStore(),
        workspace_id="workspace-1",
        interaction_handler=handler,
    )

    result = service.execute(_confirmation_request())

    assert result.status == "accepted"
    assert result.side_effect == "authorization_effect"
    assert result.confirmation_id == "confirm-1"
    assert result.activity is not None
    assert result.activity.title == "Confirmation resolved"
    assert handler.calls == [("confirmation", "confirm-1", "confirmed")]


def test_resolve_ask_rejection_is_structured() -> None:
    handler = _InteractionHandler(accepted=False)
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=InMemoryGuidanceFactStore(),
        workspace_id="workspace-1",
        interaction_handler=handler,
    )

    result = service.execute(_ask_request())

    assert result.status == "rejected"
    assert result.side_effect == "no_effect"
    assert result.reason_code == "command_rejected"
    assert result.diagnostics is not None
    assert result.diagnostics.reason_code == "command_rejected"


def test_patch_task_node_delegates_to_task_node_handler_and_is_idempotent() -> None:
    handler = _TaskNodeHandler()
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=InMemoryGuidanceFactStore(),
        workspace_id="workspace-1",
        task_node_handler=handler,
    )
    request = _patch_task_node_request()

    first = service.execute(request)
    replay = service.execute(request)

    assert first.status == "accepted"
    assert first.side_effect == "state_effect"
    assert first.task_node_id == "task-1"
    assert first.activity is not None
    assert first.activity.title == "Task changed"
    assert first.command_response is not None
    assert replay == first
    assert handler.calls == [("task-1", "Use responsive cards.")]


def test_patch_task_node_rejection_is_structured() -> None:
    handler = _TaskNodeHandler(accepted=False)
    service = ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=InMemoryGuidanceFactStore(),
        workspace_id="workspace-1",
        task_node_handler=handler,
    )

    result = service.execute(_patch_task_node_request())

    assert result.status == "rejected"
    assert result.side_effect == "no_effect"
    assert result.reason_code == "command_rejected"
    assert result.diagnostics is not None
    assert result.diagnostics.reason_code == "command_rejected"


def _guidance_request(
    *,
    payload: dict[str, object] | None = None,
    task_node_id: str | None = None,
    command_id: str = "cmd-1",
    idempotency_key: str = "idem-1",
) -> ContractCommandRequest:
    return ContractCommandRequest(
        command_id=command_id,
        idempotency_key=idempotency_key,
        command_kind="record_guidance",
        workspace_id="workspace-1",
        session_id="session-1",
        scope_kind="task" if task_node_id is not None else "session",
        task_node_id=task_node_id,
        source="runtime_input",
        router_decision_id="rir-1",
        payload=payload or {"guidanceText": "Keep the implementation small."},
    )


def _ask_request() -> ContractCommandRequest:
    return ContractCommandRequest(
        command_id="cmd-ask",
        idempotency_key="idem-ask",
        command_kind="resolve_ask",
        workspace_id="workspace-1",
        session_id="session-1",
        scope_kind="ask",
        ask_id="ask-1",
        source="runtime_input",
        router_decision_id="rir-ask",
        payload={"text": "Use Vercel."},
    )


def _confirmation_request() -> ContractCommandRequest:
    return ContractCommandRequest(
        command_id="cmd-confirm",
        idempotency_key="idem-confirm",
        command_kind="resolve_confirmation",
        workspace_id="workspace-1",
        session_id="session-1",
        scope_kind="confirmation",
        confirmation_id="confirm-1",
        source="runtime_input",
        router_decision_id="rir-confirm",
        payload={"value": "confirmed", "note": "yes"},
    )


def _patch_task_node_request() -> ContractCommandRequest:
    return ContractCommandRequest(
        command_id="cmd-patch-task",
        idempotency_key="idem-patch-task",
        command_kind="patch_task_node",
        workspace_id="workspace-1",
        session_id="session-1",
        scope_kind="task",
        task_node_id="task-1",
        source="runtime_input",
        router_decision_id="rir-patch",
        expected_version=1,
        payload={"intent": "Use responsive cards."},
    )


@dataclass
class _InteractionHandler:
    accepted: bool = True
    calls: list[tuple[str, str, str]] = field(default_factory=list)

    def resolve_ask(self, request, payload) -> ContractInteractionCommandOutcome:
        self.calls.append(("ask", request.ask_id, payload.text or ""))
        return _interaction_outcome(request.command_id, self.accepted)

    def resolve_confirmation(
        self,
        request,
        payload,
    ) -> ContractInteractionCommandOutcome:
        self.calls.append(("confirmation", request.confirmation_id, payload.value))
        return _interaction_outcome(request.command_id, self.accepted)


@dataclass
class _TaskNodeHandler:
    accepted: bool = True
    calls: list[tuple[str, str]] = field(default_factory=list)

    def patch_task_node(self, request, payload) -> ContractTaskNodeCommandOutcome:
        self.calls.append((request.task_node_id, payload.intent or payload.full_intent))
        if not self.accepted:
            return ContractTaskNodeCommandOutcome(
                accepted=False,
                message="Command rejected.",
                reason_code="command_rejected",
            )
        return ContractTaskNodeCommandOutcome(
            accepted=True,
            message="Command accepted.",
            command_response=_accepted_command_response(request.command_id),
        )


def _interaction_outcome(
    command_id: str,
    accepted: bool,
) -> ContractInteractionCommandOutcome:
    if not accepted:
        return ContractInteractionCommandOutcome(
            accepted=False,
            message="Command rejected.",
            reason_code="command_rejected",
        )
    return ContractInteractionCommandOutcome(
        accepted=True,
        message="Command accepted.",
        command_response=_accepted_command_response(command_id),
    )


def _accepted_command_response(command_id: str) -> CommandResponse:
    return CommandResponse(
        request_id=command_id,
        ok=True,
        result=CommandResult(
            command_id=command_id,
            status="accepted",
            message="Command accepted.",
        ),
    )
