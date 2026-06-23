"""Command boundary for durable Plan lifecycle operations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from taskweavn.interaction import AgentMessage, MessageBus
from taskweavn.task.commands import CommandResult
from taskweavn.task.plan_models import PlanStatus
from taskweavn.task.plan_stores import PlanStore, PlanStoreError
from taskweavn.task.stores import AuthoringStateStore, VersionConflictError

ARCHIVEABLE_PLAN_STATUSES: frozenset[PlanStatus] = frozenset(
    {
        "awaiting_acceptance",
        "accepted",
        "follow_up_needed",
        "failed",
        "cancelled",
    }
)


@runtime_checkable
class PlanLifecycleCommandService(Protocol):
    def archive_plan(
        self,
        session_id: str,
        plan_id: str,
        *,
        expected_version: int | None = None,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> CommandResult: ...


class DefaultPlanLifecycleCommandService:
    """Default command service for Plan-level lifecycle transitions."""

    def __init__(
        self,
        *,
        plan_store: PlanStore,
        authoring_state_store: AuthoringStateStore | None = None,
        message_bus: MessageBus | None = None,
    ) -> None:
        self._plan_store = plan_store
        self._authoring_state_store = authoring_state_store
        self._message_bus = message_bus

    def archive_plan(
        self,
        session_id: str,
        plan_id: str,
        *,
        expected_version: int | None = None,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> CommandResult:
        plan = self._plan_store.get_plan(session_id, plan_id)
        if plan is None:
            return _rejected(request_id, f"Plan {plan_id!r} not found")
        if plan.status == "archived" or plan.archived_at is not None:
            return _rejected(request_id, "Plan is already archived")
        if plan.status not in ARCHIVEABLE_PLAN_STATUSES:
            return _rejected(
                request_id,
                f"Plan status {plan.status!r} cannot be archived",
            )

        try:
            archived = self._plan_store.archive_plan(
                session_id,
                plan_id,
                expected_version=expected_version,
            )
        except LookupError as exc:
            return _rejected(request_id, str(exc))
        except VersionConflictError as exc:
            return _rejected(request_id, str(exc))
        except PlanStoreError as exc:
            return _rejected(request_id, str(exc))

        self._close_active_authoring_state(session_id, plan_id)
        message_ids = self._publish_archive_message(
            session_id=session_id,
            plan_id=plan_id,
            title=archived.title,
            reason=reason,
        )
        return CommandResult(
            command_id=request_id or archived.plan_id,
            status="accepted",
            message="Plan archived.",
            emitted_message_ids=message_ids,
        )

    def _close_active_authoring_state(self, session_id: str, plan_id: str) -> None:
        if self._authoring_state_store is None:
            return
        active = self._authoring_state_store.get_active(session_id)
        if active.active_plan_id == plan_id:
            self._authoring_state_store.cancel_active(session_id)

    def _publish_archive_message(
        self,
        *,
        session_id: str,
        plan_id: str,
        title: str,
        reason: str | None,
    ) -> tuple[str, ...]:
        if self._message_bus is None:
            return ()
        message = AgentMessage(
            session_id=session_id,
            agent_id="system",
            message_type="informational",
            content=f"Plan archived: {title}",
            context={
                "mode": "plan_archived",
                "plan_id": plan_id,
                **({} if reason is None else {"reason": reason}),
            },
        )
        self._message_bus.publish(message)
        return (message.message_id,)


def _rejected(request_id: str | None, message: str) -> CommandResult:
    return CommandResult(
        command_id=request_id or "archive-plan",
        status="rejected",
        message=message,
    )


__all__ = [
    "ARCHIVEABLE_PLAN_STATUSES",
    "DefaultPlanLifecycleCommandService",
    "PlanLifecycleCommandService",
]
