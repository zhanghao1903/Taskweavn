from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

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
    UiGatewayContractTaskNodeCommandHandler,
)
from taskweavn.contract_revision.models import ContractCommandRequest
from taskweavn.server.ui_contract import CommandResponse, CommandResult
from taskweavn.task.plan_models import (
    Plan,
    PlanStatus,
    PlanTaskNode,
    PlanTaskNodeExecutionStatus,
)
from taskweavn.task.sqlite_plan_store import SqlitePlanStore


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


def test_sqlite_contract_revision_stores_round_trip(tmp_path: Path) -> None:
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
        task_node_handler=cast(Any, handler),
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
        task_node_handler=cast(Any, handler),
    )

    result = service.execute(_patch_task_node_request())

    assert result.status == "rejected"
    assert result.side_effect == "no_effect"
    assert result.reason_code == "command_rejected"
    assert result.diagnostics is not None
    assert result.diagnostics.reason_code == "command_rejected"


def test_create_task_node_appends_to_editable_plan_and_is_idempotent(
    tmp_path: Path,
) -> None:
    plan_store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        plan = plan_store.create_plan(_plan(), (_node("node-1", order_index=0),))
        service = _task_node_plan_service(plan_store)
        request = ContractCommandRequest(
            command_id="cmd-create-task",
            idempotency_key="idem-create-task",
            command_kind="create_task_node",
            workspace_id="workspace-1",
            session_id="session-1",
            scope_kind="plan",
            plan_id=plan.plan_id,
            source="runtime_input",
            router_decision_id="rir-create-task",
            expected_version=plan.version,
            payload={
                "title": "Add smoke test",
                "intent": "Add an Electron smoke test for the new command path.",
                "acceptanceCriteria": ("Smoke test passes.",),
            },
        )

        first = service.execute(request)
        replay = service.execute(request)

        assert first.status == "accepted"
        assert first.activity is not None
        assert first.activity.title == "Task created"
        assert first.plan_id == plan.plan_id
        assert first.task_node_id is not None
        assert replay == first
        nodes = plan_store.list_task_nodes("session-1", plan.plan_id)
        assert len(nodes) == 2
        created = [node for node in nodes if node.task_node_id == first.task_node_id][0]
        assert created.readiness == "draft"
        assert created.execution == "not_started"
        assert created.order_index == 1
        assert created.acceptance_criteria == ("Smoke test passes.",)
        saved_plan = plan_store.get_plan("session-1", plan.plan_id)
        assert saved_plan is not None
        assert saved_plan.version == 2
    finally:
        plan_store.close()


def test_create_task_node_version_conflict_is_structured(tmp_path: Path) -> None:
    plan_store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        plan = plan_store.create_plan(_plan(), (_node("node-1"),))
        service = _task_node_plan_service(plan_store)

        result = service.execute(
            ContractCommandRequest(
                command_id="cmd-create-conflict",
                idempotency_key="idem-create-conflict",
                command_kind="create_task_node",
                workspace_id="workspace-1",
                session_id="session-1",
                scope_kind="plan",
                plan_id=plan.plan_id,
                source="runtime_input",
                router_decision_id="rir-create-conflict",
                expected_version=99,
                payload={
                    "title": "Conflicting task",
                    "intent": "This should not be added.",
                },
            )
        )

        assert result.status == "conflict"
        assert result.reason_code == "version_conflict"
        assert result.side_effect == "no_effect"
        assert len(plan_store.list_task_nodes("session-1", plan.plan_id)) == 1
    finally:
        plan_store.close()


def test_delete_task_node_tombstones_unexecuted_node_and_noops_when_repeated(
    tmp_path: Path,
) -> None:
    plan_store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        node = _node("node-1")
        plan_store.create_plan(_plan(), (node,))
        service = _task_node_plan_service(plan_store)

        deleted = service.execute(
            ContractCommandRequest(
                command_id="cmd-delete-task",
                idempotency_key="idem-delete-task",
                command_kind="delete_task_node",
                workspace_id="workspace-1",
                session_id="session-1",
                scope_kind="task",
                plan_id="plan-1",
                task_node_id=node.task_node_id,
                source="runtime_input",
                router_decision_id="rir-delete-task",
                expected_version=1,
                payload={"reason": "No longer needed."},
            )
        )
        repeated = service.execute(
            ContractCommandRequest(
                command_id="cmd-delete-task-again",
                idempotency_key="idem-delete-task-again",
                command_kind="delete_task_node",
                workspace_id="workspace-1",
                session_id="session-1",
                scope_kind="task",
                plan_id="plan-1",
                task_node_id=node.task_node_id,
                source="runtime_input",
                router_decision_id="rir-delete-task-again",
                payload={},
            )
        )

        assert deleted.status == "accepted"
        assert deleted.activity is not None
        assert deleted.activity.title == "Task removed"
        saved = plan_store.get_task_node("session-1", node.task_node_id)
        assert saved is not None
        assert saved.readiness == "cancelled"
        assert saved.execution == "cancelled"
        assert repeated.status == "noop"
        assert repeated.side_effect == "no_effect"
    finally:
        plan_store.close()


def test_delete_task_node_rejects_execution_evidence(tmp_path: Path) -> None:
    plan_store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        node = _node("node-1", execution="done", result_ref="result-1")
        plan_store.create_plan(_plan(), (node,))
        service = _task_node_plan_service(plan_store)

        result = service.execute(
            ContractCommandRequest(
                command_id="cmd-delete-evidence",
                idempotency_key="idem-delete-evidence",
                command_kind="delete_task_node",
                workspace_id="workspace-1",
                session_id="session-1",
                scope_kind="task",
                plan_id="plan-1",
                task_node_id=node.task_node_id,
                source="runtime_input",
                router_decision_id="rir-delete-evidence",
                expected_version=1,
                payload={},
            )
        )

        assert result.status == "rejected"
        assert result.reason_code == "task_has_execution_evidence"
        assert result.side_effect == "no_effect"
        unchanged = plan_store.get_task_node("session-1", node.task_node_id)
        assert unchanged is not None
        assert unchanged.readiness == "draft"
        assert unchanged.execution == "done"
    finally:
        plan_store.close()


def test_create_execution_task_appends_approved_task_to_active_plan(
    tmp_path: Path,
) -> None:
    plan_store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        plan = plan_store.create_plan(_plan(status="approved"), (_node("node-1"),))
        service = _task_node_plan_service(plan_store)

        result = service.execute(
            ContractCommandRequest(
                command_id="cmd-exec-task",
                idempotency_key="idem-exec-task",
                command_kind="create_execution_task",
                workspace_id="workspace-1",
                session_id="session-1",
                scope_kind="session",
                source="runtime_input",
                router_decision_id="rir-exec-task",
                payload={
                    "intent": "Update README with the new release notes.",
                    "acceptanceCriteria": ("README documents the release.",),
                },
            )
        )

        assert result.status == "accepted"
        assert result.activity is not None
        assert result.activity.title == "Execution work created"
        assert result.plan_id == plan.plan_id
        nodes = plan_store.list_task_nodes("session-1", plan.plan_id)
        created = [node for node in nodes if node.task_node_id == result.task_node_id][
            0
        ]
        assert created.readiness == "approved"
        assert created.intent == "Update README with the new release notes."
        assert created.acceptance_criteria == ("README documents the release.",)
    finally:
        plan_store.close()


def test_create_execution_task_creates_approved_plan_without_active_plan(
    tmp_path: Path,
) -> None:
    plan_store = SqlitePlanStore(tmp_path / "authoring.sqlite")
    try:
        service = _task_node_plan_service(plan_store)

        result = service.execute(
            ContractCommandRequest(
                command_id="cmd-exec-new-plan",
                idempotency_key="idem-exec-new-plan",
                command_kind="create_execution_task",
                workspace_id="workspace-1",
                session_id="session-1",
                scope_kind="session",
                source="runtime_input",
                router_decision_id="rir-exec-new-plan",
                payload={"intent": "Create a changelog file for version 1.1."},
            )
        )

        assert result.status == "accepted"
        assert result.plan_id is not None
        plan = plan_store.get_plan("session-1", result.plan_id)
        assert plan is not None
        assert plan.status == "approved"
        assert plan.created_by == "runtime_input_router"
        nodes = plan_store.list_task_nodes("session-1", result.plan_id)
        assert len(nodes) == 1
        assert nodes[0].readiness == "approved"
        assert nodes[0].intent == "Create a changelog file for version 1.1."
    finally:
        plan_store.close()


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

    def resolve_ask(
        self,
        request: Any,
        payload: Any,
    ) -> ContractInteractionCommandOutcome:
        self.calls.append(("ask", request.ask_id, payload.text or ""))
        return _interaction_outcome(request.command_id, self.accepted)

    def resolve_confirmation(
        self,
        request: Any,
        payload: Any,
    ) -> ContractInteractionCommandOutcome:
        self.calls.append(("confirmation", request.confirmation_id, payload.value))
        return _interaction_outcome(request.command_id, self.accepted)


@dataclass
class _TaskNodeHandler:
    accepted: bool = True
    calls: list[tuple[str, str]] = field(default_factory=list)

    def patch_task_node(
        self,
        request: Any,
        payload: Any,
    ) -> ContractTaskNodeCommandOutcome:
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

    def create_task_node(
        self,
        request: Any,
        payload: Any,
    ) -> ContractTaskNodeCommandOutcome:
        raise AssertionError("create_task_node should not be called")

    def delete_task_node(
        self,
        request: Any,
        payload: Any,
    ) -> ContractTaskNodeCommandOutcome:
        raise AssertionError("delete_task_node should not be called")

    def create_execution_task(
        self,
        request: Any,
        payload: Any,
    ) -> ContractTaskNodeCommandOutcome:
        raise AssertionError("create_execution_task should not be called")


class _UnusedCommandGateway:
    def update_task_node(self, task_node_id: str, command: Any) -> CommandResponse:
        raise AssertionError("update_task_node should not be called")


def _task_node_plan_service(
    plan_store: SqlitePlanStore,
) -> ContractRevisionCommandService:
    return ContractRevisionCommandService(
        idempotency_store=InMemoryContractCommandIdempotencyStore(),
        guidance_store=InMemoryGuidanceFactStore(),
        workspace_id="workspace-1",
        plan_store=plan_store,
        task_node_handler=UiGatewayContractTaskNodeCommandHandler(
            cast(Any, _UnusedCommandGateway()),
            plan_store=plan_store,
        ),
    )


def _plan(
    *,
    plan_id: str = "plan-1",
    status: PlanStatus = "draft",
) -> Plan:
    return Plan(
        plan_id=plan_id,
        session_id="session-1",
        title="Test plan",
        objective="Test objective",
        summary="Test summary",
        status=status,
    )


def _node(
    task_node_id: str,
    *,
    order_index: int = 0,
    execution: PlanTaskNodeExecutionStatus = "not_started",
    result_ref: str | None = None,
) -> PlanTaskNode:
    return PlanTaskNode(
        task_node_id=task_node_id,
        plan_id="plan-1",
        session_id="session-1",
        task_index="1",
        order_index=order_index,
        title="Existing task",
        intent="Existing task intent",
        summary="Existing task summary",
        execution=execution,
        result_ref=result_ref,
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
