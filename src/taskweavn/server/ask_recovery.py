"""Best-effort ASK continuation recovery for Main Page snapshots."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from taskweavn.interaction import AskRequest, AskStore
from taskweavn.observability.main_page_trace import main_page_trace
from taskweavn.task.authoring import RawTask
from taskweavn.task.bus import TaskBus
from taskweavn.task.collaborator_api import CollaboratorApiAdapter
from taskweavn.task.execution import ExecutionTriggerGateway
from taskweavn.task.models import TaskDomain
from taskweavn.task.stores import AuthoringStateStore, RawTaskStore


@dataclass(frozen=True)
class AskRecoveryResult:
    """Summary of a single best-effort ASK recovery pass."""

    authoring_raw_task_ids: tuple[str, ...] = ()
    execution_resumed_task_ids: tuple[str, ...] = ()
    execution_dispatch_ask_ids: tuple[str, ...] = ()

    @property
    def recovered_count(self) -> int:
        return (
            len(self.authoring_raw_task_ids)
            + len(self.execution_resumed_task_ids)
            + len(self.execution_dispatch_ask_ids)
        )


class DefaultAskRecoveryService:
    """Recover ASK answers that were persisted before continuation completed."""

    def __init__(
        self,
        *,
        raw_task_store: RawTaskStore | None = None,
        collaborator: CollaboratorApiAdapter | None = None,
        authoring_state_store: AuthoringStateStore | None = None,
        ask_store: AskStore | None = None,
        task_bus: TaskBus | None = None,
        execution_trigger_gateway: ExecutionTriggerGateway | None = None,
        on_task_lifecycle_committed: Callable[[TaskDomain], None] | None = None,
    ) -> None:
        self._raw_task_store = raw_task_store
        self._collaborator = collaborator
        self._authoring_state_store = authoring_state_store
        self._ask_store = ask_store
        self._task_bus = task_bus
        self._execution_trigger_gateway = execution_trigger_gateway
        self._on_task_lifecycle_committed = on_task_lifecycle_committed

    def recover_session(self, session_id: str) -> AskRecoveryResult:
        authoring = self._recover_authoring(session_id)
        execution_resumed, execution_dispatched = self._recover_execution(session_id)
        result = AskRecoveryResult(
            authoring_raw_task_ids=tuple(authoring),
            execution_resumed_task_ids=tuple(execution_resumed),
            execution_dispatch_ask_ids=tuple(execution_dispatched),
        )
        if result.recovered_count:
            main_page_trace(
                "ask_recovery.session_result",
                authoring_raw_task_ids=result.authoring_raw_task_ids,
                execution_dispatch_ask_ids=result.execution_dispatch_ask_ids,
                execution_resumed_task_ids=result.execution_resumed_task_ids,
                recovered_count=result.recovered_count,
                session_id=session_id,
            )
        return result

    def _recover_authoring(self, session_id: str) -> list[str]:
        if self._raw_task_store is None or self._collaborator is None:
            return []

        recovered: list[str] = []
        for raw_task in self._raw_task_store.list_for_session(session_id):
            if not _raw_task_needs_authoring_recovery(raw_task):
                continue
            if not self._raw_task_is_active_for_recovery(raw_task):
                continue
            result = self._collaborator.generate_task_tree(
                session_id=session_id,
                raw_task_id=raw_task.raw_task_id,
                idempotency_key=_authoring_recovery_idempotency_key(
                    session_id,
                    raw_task.raw_task_id,
                ),
            )
            main_page_trace(
                "ask_recovery.authoring_result",
                accepted=result.accepted,
                raw_task_id=raw_task.raw_task_id,
                result_message=result.message,
                result_status=result.status,
                session_id=session_id,
            )
            if result.accepted:
                recovered.append(raw_task.raw_task_id)
        return recovered

    def _raw_task_is_active_for_recovery(self, raw_task: RawTask) -> bool:
        if self._authoring_state_store is None:
            return True
        active = self._authoring_state_store.get_active(raw_task.session_id)
        return (
            active.active_state == "raw_task"
            and active.active_raw_task_id == raw_task.raw_task_id
        )

    def _recover_execution(self, session_id: str) -> tuple[list[str], list[str]]:
        if self._ask_store is None or self._task_bus is None:
            return [], []

        resumed_task_ids: list[str] = []
        dispatched_ask_ids: list[str] = []
        for ask in self._ask_store.list_for_session(
            session_id,
            statuses=("answered",),
        ):
            if not _ask_needs_execution_recovery(ask):
                continue
            assert ask.task_id is not None
            task = self._task_bus.get(session_id, ask.task_id)
            if task is None:
                continue
            should_dispatch = False
            if task.status == "waiting_for_user" and task.waiting_for_ask_id == ask.ask_id:
                resumed = self._task_bus.resume_after_user(
                    session_id,
                    task.task_id,
                    ask_id=ask.ask_id,
                )
                resumed_task_ids.append(resumed.task_id)
                should_dispatch = True
                if self._on_task_lifecycle_committed is not None:
                    self._on_task_lifecycle_committed(resumed)
            elif task.status == "pending" and task.waiting_for_ask_id is None:
                should_dispatch = True

            if should_dispatch and self._request_execution_dispatch(session_id, ask):
                dispatched_ask_ids.append(ask.ask_id)

        return resumed_task_ids, dispatched_ask_ids

    def _request_execution_dispatch(self, session_id: str, ask: AskRequest) -> bool:
        if self._execution_trigger_gateway is None:
            return False
        result = self._execution_trigger_gateway.request_dispatch(
            session_id,
            reason="startup_recovery",
            request_id=f"ask-recovery:{session_id}:{ask.ask_id}",
        )
        main_page_trace(
            "ask_recovery.execution_dispatch_result",
            accepted=result.accepted,
            ask_id=ask.ask_id,
            error_ref=result.error_ref,
            request_id=result.request_id,
            session_id=session_id,
            status=result.status,
        )
        return result.accepted


def _raw_task_needs_authoring_recovery(raw_task: RawTask) -> bool:
    return (
        raw_task.status == "assessing"
        and bool(raw_task.asks)
        and not raw_task.unanswered_ask_ids
    )


def _ask_needs_execution_recovery(ask: AskRequest) -> bool:
    return ask.status == "answered" and ask.blocking and ask.task_id is not None


def _authoring_recovery_idempotency_key(session_id: str, raw_task_id: str) -> str:
    return f"ask-recovery:{session_id}:{raw_task_id}:task-tree"


__all__ = ["AskRecoveryResult", "DefaultAskRecoveryService"]
