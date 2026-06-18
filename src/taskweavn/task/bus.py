"""TaskBus publish and execution lifecycle boundary for published Task facts."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol, runtime_checkable
from uuid import uuid4

from taskweavn.observability.main_page_trace import main_page_trace
from taskweavn.task.models import TaskDomain, TaskInterruptRequestedBy
from taskweavn.task.stores import TaskStore, TaskStoreError


@runtime_checkable
class TaskBus(Protocol):
    """Published Task state authority.

    The bus owns published Task lifecycle transitions. It deliberately keeps
    the state machine small: pending -> running -> done/failed, with
    waiting_for_user as a cooperative blocking point for durable ASK or
    confirmation. Manual retry moves a failed Task back to pending on the same
    Task identity. Skip is represented as a failed terminal Task with a
    user-visible reason.
    """

    def publish(self, task: TaskDomain) -> TaskDomain: ...

    def claim_next(
        self,
        session_id: str,
        *,
        capability: str,
        agent_id: str,
    ) -> TaskDomain | None: ...

    def complete(
        self,
        session_id: str,
        task_id: str,
        *,
        result_ref: str | None = None,
    ) -> TaskDomain: ...

    def fail(
        self,
        session_id: str,
        task_id: str,
        *,
        error_ref: str,
    ) -> TaskDomain: ...

    def wait_for_user(
        self,
        session_id: str,
        task_id: str,
        *,
        ask_id: str,
    ) -> TaskDomain: ...

    def wait_for_confirmation(
        self,
        session_id: str,
        task_id: str,
        *,
        confirmation_id: str,
    ) -> TaskDomain: ...

    def resume_after_user(
        self,
        session_id: str,
        task_id: str,
        *,
        ask_id: str,
    ) -> TaskDomain: ...

    def resume_after_confirmation(
        self,
        session_id: str,
        task_id: str,
        *,
        confirmation_id: str,
    ) -> TaskDomain: ...

    def skip(
        self,
        session_id: str,
        task_id: str,
        *,
        reason: str,
    ) -> TaskDomain: ...

    def retry(
        self,
        session_id: str,
        task_id: str,
        *,
        instruction: str | None = None,
    ) -> TaskDomain: ...

    def request_interrupt(
        self,
        session_id: str,
        task_id: str,
        *,
        reason: str,
        requested_by: TaskInterruptRequestedBy = "user",
        request_id: str | None = None,
    ) -> TaskDomain: ...

    def recover_interrupted_running_tasks(self, session_id: str) -> list[TaskDomain]: ...

    def get(self, session_id: str, task_id: str) -> TaskDomain | None: ...

    def list_for_session(self, session_id: str) -> list[TaskDomain]: ...

    def list_children(self, session_id: str, parent_id: str | None) -> list[TaskDomain]: ...


class InMemoryTaskBus:
    """Process-local TaskBus materialized view for publisher tests."""

    def __init__(self, tasks: list[TaskDomain] | None = None) -> None:
        self._lock = RLock()
        self._tasks: dict[tuple[str, str], TaskDomain] = {}
        self._children: dict[tuple[str, str | None], list[str]] = defaultdict(list)
        for task in tasks or []:
            self._load(task)

    def publish(self, task: TaskDomain) -> TaskDomain:
        if task.status != "pending":
            raise TaskStoreError("published tasks must enter TaskBus as pending")
        return self._load(task)

    def claim_next(
        self,
        session_id: str,
        *,
        capability: str,
        agent_id: str,
    ) -> TaskDomain | None:
        if not capability.strip():
            raise TaskStoreError("claim capability must not be empty")
        if not agent_id.strip():
            raise TaskStoreError("claim agent_id must not be empty")
        with self._lock:
            candidates = sorted(
                (
                    task
                    for task in self._tasks.values()
                    if task.session_id == session_id
                    and task.status == "pending"
                    and task.required_capability == capability
                    and self._parent_is_done(task)
                ),
                key=lambda task: (task.created_at, task.order_index, task.task_id),
            )
            if not candidates:
                return None
            task = candidates[0]
            updated = task.model_copy(
                update={
                    "status": "running",
                    "claimed_by": agent_id,
                    "started_at": _utcnow(),
                }
            )
            self._tasks[(session_id, task.task_id)] = updated
            main_page_trace(
                "task_bus.claim",
                agent_id=agent_id,
                capability=capability,
                task=_task_trace_summary(updated),
            )
            return updated

    def complete(
        self,
        session_id: str,
        task_id: str,
        *,
        result_ref: str | None = None,
    ) -> TaskDomain:
        return self._transition_running(
            session_id,
            task_id,
            status="done",
            result_ref=result_ref,
            error_ref=None,
        )

    def fail(
        self,
        session_id: str,
        task_id: str,
        *,
        error_ref: str,
    ) -> TaskDomain:
        if not error_ref.strip():
            raise TaskStoreError("failed task requires error_ref")
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status not in {"running", "waiting_for_user"}:
                raise TaskStoreError(
                    "only running or waiting_for_user tasks can transition "
                    f"to failed; got {task.status}"
                )
            updated = task.model_copy(
                update={
                    "status": "failed",
                    "result_ref": None,
                    "error_ref": error_ref,
                    "waiting_for_ask_id": None,
                    "waiting_for_confirmation_id": None,
                    "waiting_for_user_since": None,
                    "completed_at": _utcnow(),
                }
            )
            self._tasks[(session_id, task_id)] = updated
            main_page_trace(
                "task_bus.fail",
                error_ref=error_ref,
                previous_status=task.status,
                task=_task_trace_summary(updated),
            )
            return updated

    def wait_for_user(
        self,
        session_id: str,
        task_id: str,
        *,
        ask_id: str,
    ) -> TaskDomain:
        ask_id = ask_id.strip()
        if not ask_id:
            raise TaskStoreError("waiting task requires ask_id")
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status != "running":
                raise TaskStoreError(
                    f"only running tasks can wait for user; got {task.status}"
                )
            updated = task.model_copy(update=_wait_for_user_updates(ask_id=ask_id))
            self._tasks[(session_id, task_id)] = updated
            main_page_trace(
                "task_bus.wait_for_user",
                ask_id=ask_id,
                previous_status=task.status,
                task=_task_trace_summary(updated),
            )
            return updated

    def wait_for_confirmation(
        self,
        session_id: str,
        task_id: str,
        *,
        confirmation_id: str,
    ) -> TaskDomain:
        confirmation_id = confirmation_id.strip()
        if not confirmation_id:
            raise TaskStoreError("waiting task requires confirmation_id")
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status != "running":
                raise TaskStoreError(
                    f"only running tasks can wait for user; got {task.status}"
                )
            updated = task.model_copy(
                update=_wait_for_user_confirmation_updates(
                    confirmation_id=confirmation_id
                )
            )
            self._tasks[(session_id, task_id)] = updated
            main_page_trace(
                "task_bus.wait_for_confirmation",
                confirmation_id=confirmation_id,
                previous_status=task.status,
                task=_task_trace_summary(updated),
            )
            return updated

    def resume_after_user(
        self,
        session_id: str,
        task_id: str,
        *,
        ask_id: str,
    ) -> TaskDomain:
        ask_id = ask_id.strip()
        if not ask_id:
            raise TaskStoreError("resume requires ask_id")
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status != "waiting_for_user":
                raise TaskStoreError(
                    f"only waiting_for_user tasks can resume; got {task.status}"
                )
            if task.waiting_for_ask_id != ask_id:
                raise TaskStoreError("resume ask_id does not match active ASK")
            updated = task.model_copy(update=_resume_after_user_updates())
            self._tasks[(session_id, task_id)] = updated
            main_page_trace(
                "task_bus.resume_after_user",
                ask_id=ask_id,
                previous_status=task.status,
                task=_task_trace_summary(updated),
            )
            return updated

    def resume_after_confirmation(
        self,
        session_id: str,
        task_id: str,
        *,
        confirmation_id: str,
    ) -> TaskDomain:
        confirmation_id = confirmation_id.strip()
        if not confirmation_id:
            raise TaskStoreError("resume requires confirmation_id")
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status != "waiting_for_user":
                raise TaskStoreError(
                    f"only waiting_for_user tasks can resume; got {task.status}"
                )
            if task.waiting_for_confirmation_id != confirmation_id:
                raise TaskStoreError(
                    "resume confirmation_id does not match active confirmation"
                )
            updated = task.model_copy(update=_resume_after_user_updates())
            self._tasks[(session_id, task_id)] = updated
            main_page_trace(
                "task_bus.resume_after_confirmation",
                confirmation_id=confirmation_id,
                previous_status=task.status,
                task=_task_trace_summary(updated),
            )
            return updated

    def skip(
        self,
        session_id: str,
        task_id: str,
        *,
        reason: str,
    ) -> TaskDomain:
        if not reason.strip():
            raise TaskStoreError("skipped task requires reason")
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status not in {"pending", "running"}:
                raise TaskStoreError(
                    f"only pending or running tasks can be skipped; got {task.status}"
                )
            updated = task.model_copy(
                update={
                    "status": "failed",
                    "error_ref": f"skipped: {reason}",
                    "completed_at": _utcnow(),
                }
            )
            self._tasks[(session_id, task_id)] = updated
            main_page_trace(
                "task_bus.skip",
                previous_status=task.status,
                reason=reason,
                task=_task_trace_summary(updated),
            )
            return updated

    def retry(
        self,
        session_id: str,
        task_id: str,
        *,
        instruction: str | None = None,
    ) -> TaskDomain:
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status != "failed":
                raise TaskStoreError(f"only failed tasks can be retried; got {task.status}")
            updated = task.model_copy(
                update=_retry_updates(task, instruction=instruction)
            )
            self._tasks[(session_id, task_id)] = updated
            main_page_trace(
                "task_bus.retry",
                instruction_present=instruction is not None and bool(instruction.strip()),
                previous_status=task.status,
                task=_task_trace_summary(updated),
            )
            return updated

    def request_interrupt(
        self,
        session_id: str,
        task_id: str,
        *,
        reason: str,
        requested_by: TaskInterruptRequestedBy = "user",
        request_id: str | None = None,
    ) -> TaskDomain:
        if not reason.strip():
            raise TaskStoreError("interrupt request requires reason")
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status not in {"pending", "running"}:
                raise TaskStoreError(
                    f"only pending or running tasks can be interrupted; got {task.status}"
                )
            updates = _interrupt_updates(
                reason=reason,
                requested_by=requested_by,
                request_id=request_id,
            )
            if task.status == "pending":
                updates.update(
                    {
                        "status": "failed",
                        "error_ref": f"cancelled: {reason.strip()}",
                        "completed_at": _utcnow(),
                    }
                )
            updated = task.model_copy(update=updates)
            self._tasks[(session_id, task_id)] = updated
            main_page_trace(
                "task_bus.interrupt_requested",
                previous_status=task.status,
                reason=reason.strip(),
                request_id=updated.interrupt_request_id,
                task=_task_trace_summary(updated),
            )
            return updated

    def recover_interrupted_running_tasks(self, session_id: str) -> list[TaskDomain]:
        with self._lock:
            recovered: list[TaskDomain] = []
            for task in self.list_for_session(session_id):
                if task.status != "running" or not task.interrupt_requested:
                    continue
                updated = task.model_copy(update=_recover_interrupted_running_updates(task))
                self._tasks[(session_id, task.task_id)] = updated
                recovered.append(updated)
                main_page_trace(
                    "task_bus.recover_interrupted_running",
                    previous_status=task.status,
                    task=_task_trace_summary(updated),
                )
            return recovered

    def _load(self, task: TaskDomain) -> TaskDomain:
        key = (task.session_id, task.task_id)
        with self._lock:
            if key in self._tasks:
                raise TaskStoreError(f"task {task.task_id!r} already exists")
            if task.parent_id is not None:
                parent = self._tasks.get((task.session_id, task.parent_id))
                if parent is None:
                    raise TaskStoreError(f"parent task {task.parent_id!r} not found")
                if parent.root_id != task.root_id:
                    raise TaskStoreError("child task root_id must match parent root_id")
            self._tasks[key] = task
            self._children[(task.session_id, task.parent_id)].append(task.task_id)
            return task

    def get(self, session_id: str, task_id: str) -> TaskDomain | None:
        with self._lock:
            return self._tasks.get((session_id, task_id))

    def list_for_session(self, session_id: str) -> list[TaskDomain]:
        with self._lock:
            return sorted(
                (task for task in self._tasks.values() if task.session_id == session_id),
                key=lambda task: (task.created_at, task.order_index, task.task_id),
            )

    def list_children(self, session_id: str, parent_id: str | None) -> list[TaskDomain]:
        with self._lock:
            task_ids = self._children.get((session_id, parent_id), [])
            return sorted(
                (self._tasks[(session_id, task_id)] for task_id in task_ids),
                key=lambda task: (task.order_index, task.created_at, task.task_id),
            )

    def _parent_is_done(self, task: TaskDomain) -> bool:
        if task.parent_id is None:
            return True
        parent = self._tasks.get((task.session_id, task.parent_id))
        if parent is None:
            return False
        return parent.status == "done"

    def _transition_running(
        self,
        session_id: str,
        task_id: str,
        *,
        status: str,
        result_ref: str | None,
        error_ref: str | None,
    ) -> TaskDomain:
        with self._lock:
            task = self._require_task(session_id, task_id)
            if task.status != "running":
                raise TaskStoreError(
                    f"only running tasks can transition to {status}; got {task.status}"
                )
            updated = task.model_copy(
                update={
                    "status": status,
                    "result_ref": result_ref,
                    "error_ref": error_ref,
                    "completed_at": _utcnow(),
                }
            )
            self._tasks[(session_id, task_id)] = updated
            main_page_trace(
                "task_bus.transition_running",
                previous_status=task.status,
                status=status,
                task=_task_trace_summary(updated),
            )
            return updated

    def _require_task(self, session_id: str, task_id: str) -> TaskDomain:
        task = self._tasks.get((session_id, task_id))
        if task is None:
            raise TaskStoreError(f"task {task_id!r} not found")
        return task


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _retry_updates(task: TaskDomain, *, instruction: str | None) -> dict[str, object]:
    updates: dict[str, object] = {
        "status": "pending",
        "result_ref": None,
        "error_ref": None,
        "claimed_by": None,
        "waiting_for_ask_id": None,
        "waiting_for_confirmation_id": None,
        "waiting_for_user_since": None,
        "started_at": None,
        "completed_at": None,
        "interrupt_requested": False,
        "interrupt_request_id": None,
        "interrupt_reason": None,
        "interrupt_requested_by": None,
        "interrupt_requested_at": None,
    }
    retry_instruction = instruction.strip() if instruction is not None else ""
    if retry_instruction:
        updates["intent"] = f"{task.intent.rstrip()}\n\nRetry instruction:\n{retry_instruction}"
    return updates


def _wait_for_user_updates(*, ask_id: str) -> dict[str, object]:
    return {
        "status": "waiting_for_user",
        "waiting_for_ask_id": ask_id,
        "waiting_for_confirmation_id": None,
        "waiting_for_user_since": _utcnow(),
        "result_ref": None,
        "error_ref": None,
        "completed_at": None,
    }


def _wait_for_user_confirmation_updates(*, confirmation_id: str) -> dict[str, object]:
    return {
        "status": "waiting_for_user",
        "waiting_for_ask_id": None,
        "waiting_for_confirmation_id": confirmation_id,
        "waiting_for_user_since": _utcnow(),
        "result_ref": None,
        "error_ref": None,
        "completed_at": None,
    }


def _resume_after_user_updates() -> dict[str, object]:
    return {
        "status": "pending",
        "result_ref": None,
        "error_ref": None,
        "claimed_by": None,
        "waiting_for_ask_id": None,
        "waiting_for_confirmation_id": None,
        "waiting_for_user_since": None,
        "started_at": None,
        "completed_at": None,
    }


def _interrupt_updates(
    *,
    reason: str,
    requested_by: TaskInterruptRequestedBy,
    request_id: str | None,
) -> dict[str, object]:
    return {
        "interrupt_requested": True,
        "interrupt_request_id": request_id or uuid4().hex,
        "interrupt_reason": reason.strip(),
        "interrupt_requested_by": requested_by,
        "interrupt_requested_at": _utcnow(),
    }


def _recover_interrupted_running_updates(task: TaskDomain) -> dict[str, object]:
    reason = (task.interrupt_reason or "user requested stop").strip()
    return {
        "status": "failed",
        "result_ref": None,
        "error_ref": f"cancelled: {reason}; safe_point=sidecar_recovery",
        "waiting_for_ask_id": None,
        "waiting_for_confirmation_id": None,
        "waiting_for_user_since": None,
        "completed_at": _utcnow(),
    }


def _task_trace_summary(task: TaskDomain) -> dict[str, object | None]:
    return {
        "claimed_by": task.claimed_by,
        "completed_at": task.completed_at,
        "error_ref": task.error_ref,
        "interrupt_reason": task.interrupt_reason,
        "interrupt_request_id": task.interrupt_request_id,
        "interrupt_requested": task.interrupt_requested,
        "result_ref": task.result_ref,
        "session_id": task.session_id,
        "started_at": task.started_at,
        "status": task.status,
        "task_id": task.task_id,
        "waiting_for_ask_id": task.waiting_for_ask_id,
        "waiting_for_confirmation_id": task.waiting_for_confirmation_id,
    }


__all__ = ["InMemoryTaskBus", "TaskBus", "TaskStore"]
