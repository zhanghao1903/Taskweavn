"""Fixed-route execution bridge for Product 1.0 published Tasks."""

from __future__ import annotations

import contextlib
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from taskweavn.context.models import ContextBuildRequest, ContextBuildResult
from taskweavn.core.loop import LoopResult
from taskweavn.interaction import AgentMessage, MessageBus, MessageStreamError
from taskweavn.task.bus import TaskBus
from taskweavn.task.models import TaskDomain
from taskweavn.task.result_summary import (
    TaskExecutionSummary,
    TaskExecutionSummaryStore,
    build_agent_loop_error_summary,
    build_agent_loop_result_summary,
    build_execution_completed_summary,
    build_execution_exception_summary,
    build_external_error_ref_summary,
    build_external_result_ref_summary,
)
from taskweavn.task.retry import task_effectively_done

DEFAULT_FIXED_ROUTE_AGENT_ID = "default_agent"

TaskExecutionTickStatus = Literal[
    "idle",
    "completed",
    "failed",
    "claim_not_available",
    "health_error",
]

ExecutionDispatchRequestStatus = Literal[
    "queued",
    "already_pending",
    "already_running",
    "disabled",
    "health_error",
    "closed",
]

ExecutionDispatchTriggerReason = Literal[
    "publish_start_immediately",
    "retry_start_immediately",
    "manual_control_route",
    "startup_recovery",
]


@dataclass(frozen=True)
class FixedRouteTaskExecutorConfig:
    """Configuration for the Product 1.0 single-agent execution route."""

    session_id: str
    default_agent_id: str = DEFAULT_FIXED_ROUTE_AGENT_ID


@dataclass(frozen=True)
class TaskRunResult:
    """Resident Default Agent result for one claimed Task."""

    result_ref: str | None = None
    error_ref: str | None = None

    @property
    def ok(self) -> bool:
        return self.error_ref is None


@runtime_checkable
class ResidentDefaultAgent(Protocol):
    """Minimal resident Default Agent contract for Product 1.0."""

    def run(self, task: TaskDomain) -> TaskRunResult: ...


@runtime_checkable
class AgentLoopRunner(Protocol):
    """Small subset of AgentLoop used by the resident Default Agent adapter."""

    def run(self, task: str, *, task_id: str | None = None) -> LoopResult: ...


AgentLoopRunnerFactory = Callable[[TaskDomain], AgentLoopRunner]


@runtime_checkable
class ExecutionContextBuilder(Protocol):
    """Minimal context builder contract used by the resident Default Agent."""

    def build(self, request: ContextBuildRequest) -> ContextBuildResult: ...


ExecutionContextBuilderFactory = Callable[[TaskDomain], ExecutionContextBuilder]


@dataclass(frozen=True)
class TaskExecutionTickResult:
    """Outcome of one fixed-route executor tick."""

    status: TaskExecutionTickStatus
    session_id: str
    claimed_task_id: str | None = None
    completed_task_id: str | None = None
    failed_task_id: str | None = None
    skipped_reason: str | None = None
    result_ref: str | None = None
    error_ref: str | None = None


@dataclass(frozen=True)
class ExecutionDispatchRequestResult:
    """Outcome of requesting background fixed-route execution for a Session."""

    status: ExecutionDispatchRequestStatus
    session_id: str
    reason: ExecutionDispatchTriggerReason
    request_id: str | None = None
    message: str = ""
    error_ref: str | None = None

    @property
    def accepted(self) -> bool:
        return self.status in {"queued", "already_pending", "already_running"}


@runtime_checkable
class ExecutionTriggerGateway(Protocol):
    """Small boundary used by transports to enqueue fixed-route execution."""

    def request_dispatch(
        self,
        session_id: str,
        *,
        reason: ExecutionDispatchTriggerReason,
        request_id: str | None = None,
    ) -> ExecutionDispatchRequestResult: ...


class FixedRouteTaskExecutor:
    """Run the next eligible published Task through the resident Default Agent.

    Product 1.0 intentionally has no Router, Agent Manager, assignment field, or
    reassignment UI. The bridge only selects the next Task that TaskBus can claim,
    executes it through the resident Default Agent, and reports done/failed back
    through TaskBus lifecycle methods.
    """

    def __init__(
        self,
        *,
        task_bus: TaskBus,
        default_agent: ResidentDefaultAgent | None,
        config: FixedRouteTaskExecutorConfig,
        result_summary_store: TaskExecutionSummaryStore | None = None,
        message_bus: MessageBus | None = None,
    ) -> None:
        self._task_bus = task_bus
        self._default_agent = default_agent
        self._config = config
        self._result_summary_store = result_summary_store
        self._message_bus = message_bus

    def tick(self) -> TaskExecutionTickResult:
        if self._default_agent is None:
            return TaskExecutionTickResult(
                status="health_error",
                session_id=self._config.session_id,
                skipped_reason="default_agent_unavailable",
                error_ref="default_agent_unavailable",
            )

        candidate = _select_next_eligible_pending_task(
            self._task_bus,
            self._config.session_id,
        )
        if candidate is None:
            return TaskExecutionTickResult(
                status="idle",
                session_id=self._config.session_id,
                skipped_reason="no_eligible_task",
            )

        claimed = self._task_bus.claim_next(
            self._config.session_id,
            capability=candidate.required_capability,
            agent_id=self._config.default_agent_id,
        )
        if claimed is None:
            return TaskExecutionTickResult(
                status="claim_not_available",
                session_id=self._config.session_id,
                skipped_reason="claim_not_available",
            )

        try:
            run_result = self._default_agent.run(claimed)
        except Exception as exc:  # noqa: BLE001 - runtime bridge must fail the Task.
            error_ref = _store_execution_exception_summary(
                self._result_summary_store,
                claimed,
                exc,
            )
            failed = self._task_bus.fail(
                claimed.session_id,
                claimed.task_id,
                error_ref=error_ref,
            )
            _publish_execution_message(
                self._message_bus,
                failed,
                summary=_summary_for_ref(self._result_summary_store, failed.error_ref),
            )
            return TaskExecutionTickResult(
                status="failed",
                session_id=self._config.session_id,
                claimed_task_id=claimed.task_id,
                failed_task_id=failed.task_id,
                error_ref=failed.error_ref,
            )

        if run_result.ok:
            result_ref = _ensure_result_ref_readable(
                self._result_summary_store,
                claimed,
                run_result.result_ref,
            )
            completed = self._task_bus.complete(
                claimed.session_id,
                claimed.task_id,
                result_ref=result_ref,
            )
            _publish_execution_message(
                self._message_bus,
                completed,
                summary=_summary_for_ref(self._result_summary_store, completed.result_ref),
            )
            return TaskExecutionTickResult(
                status="completed",
                session_id=self._config.session_id,
                claimed_task_id=claimed.task_id,
                completed_task_id=completed.task_id,
                result_ref=completed.result_ref,
            )

        error_ref = (run_result.error_ref or "").strip() or "agent_execution_failed"
        error_ref = _ensure_error_ref_readable(
            self._result_summary_store,
            claimed,
            error_ref,
        )
        failed = self._task_bus.fail(
            claimed.session_id,
            claimed.task_id,
            error_ref=error_ref,
        )
        _publish_execution_message(
            self._message_bus,
            failed,
            summary=_summary_for_ref(self._result_summary_store, failed.error_ref),
        )
        return TaskExecutionTickResult(
            status="failed",
            session_id=self._config.session_id,
            claimed_task_id=claimed.task_id,
            failed_task_id=failed.task_id,
            error_ref=failed.error_ref,
        )


class FixedRouteExecutionDispatcher:
    """Sidecar-owned background dispatcher for fixed-route execution.

    The dispatcher coalesces duplicate triggers per Session and delegates all Task
    lifecycle mutation to ``FixedRouteTaskExecutor`` / ``TaskBus``. It does not
    keep AgentLoop instances alive between Task runs.
    """

    def __init__(
        self,
        *,
        task_bus: TaskBus,
        default_agent: ResidentDefaultAgent | None,
        default_agent_id: str = DEFAULT_FIXED_ROUTE_AGENT_ID,
        max_ticks_per_trigger: int = 10,
        enabled: bool = True,
        result_summary_store: TaskExecutionSummaryStore | None = None,
        message_bus: MessageBus | None = None,
    ) -> None:
        self._task_bus = task_bus
        self._default_agent = default_agent
        self._default_agent_id = default_agent_id
        self._max_ticks_per_trigger = max(1, max_ticks_per_trigger)
        self._enabled = enabled
        self._result_summary_store = result_summary_store
        self._message_bus = message_bus
        self._condition = threading.Condition()
        self._pending_session_ids: set[str] = set()
        self._pending_sessions: deque[str] = deque()
        self._running_session_ids: set[str] = set()
        self._closed = False
        self._worker: threading.Thread | None = None

    def request_dispatch(
        self,
        session_id: str,
        *,
        reason: ExecutionDispatchTriggerReason,
        request_id: str | None = None,
    ) -> ExecutionDispatchRequestResult:
        with self._condition:
            if self._closed:
                return _dispatch_result(
                    status="closed",
                    session_id=session_id,
                    reason=reason,
                    request_id=request_id,
                    error_ref="execution_dispatcher_closed",
                )
            if not self._enabled:
                return _dispatch_result(
                    status="disabled",
                    session_id=session_id,
                    reason=reason,
                    request_id=request_id,
                    error_ref="execution_dispatcher_disabled",
                )
            if self._default_agent is None:
                return _dispatch_result(
                    status="health_error",
                    session_id=session_id,
                    reason=reason,
                    request_id=request_id,
                    error_ref="default_agent_unavailable",
                )
            if session_id in self._pending_session_ids:
                return _dispatch_result(
                    status="already_pending",
                    session_id=session_id,
                    reason=reason,
                    request_id=request_id,
                )
            if session_id in self._running_session_ids:
                return _dispatch_result(
                    status="already_running",
                    session_id=session_id,
                    reason=reason,
                    request_id=request_id,
                )

            self._pending_session_ids.add(session_id)
            self._pending_sessions.append(session_id)
            self._ensure_worker_locked()
            self._condition.notify()
            return _dispatch_result(
                status="queued",
                session_id=session_id,
                reason=reason,
                request_id=request_id,
            )

    def stop(self, *, timeout: float | None = 5.0) -> None:
        with self._condition:
            self._closed = True
            self._pending_session_ids.clear()
            self._pending_sessions.clear()
            self._condition.notify_all()
            worker = self._worker

        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=timeout)

    def close(self) -> None:
        self.stop()

    def _ensure_worker_locked(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(
            target=self._run,
            name="taskweavn-fixed-route-dispatcher",
            daemon=True,
        )
        self._worker.start()

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._closed and not self._pending_sessions:
                    self._condition.wait()
                if self._closed or not self._pending_sessions:
                    return
                session_id = self._pending_sessions.popleft()
                self._pending_session_ids.discard(session_id)
                self._running_session_ids.add(session_id)

            try:
                self._drain_session(session_id)
            finally:
                with self._condition:
                    self._running_session_ids.discard(session_id)
                    self._condition.notify_all()

    def _drain_session(self, session_id: str) -> None:
        for _ in range(self._max_ticks_per_trigger):
            executor = FixedRouteTaskExecutor(
                task_bus=self._task_bus,
                default_agent=self._default_agent,
                config=FixedRouteTaskExecutorConfig(
                    session_id=session_id,
                    default_agent_id=self._default_agent_id,
                ),
                result_summary_store=self._result_summary_store,
                message_bus=self._message_bus,
            )
            result = executor.tick()
            if result.status != "completed":
                return


@dataclass(frozen=True)
class AgentLoopResidentDefaultAgent:
    """Resident Default Agent adapter backed by an AgentLoop-compatible runner."""

    loop: AgentLoopRunner | None = None
    result_ref_prefix: str = "agent_loop"
    error_ref_prefix: str = "agent_loop_failed"
    loop_factory: AgentLoopRunnerFactory | None = None
    context_builder_factory: ExecutionContextBuilderFactory | None = None
    result_summary_store: TaskExecutionSummaryStore | None = None

    def __post_init__(self) -> None:
        if (self.loop is None) == (self.loop_factory is None):
            raise ValueError("provide exactly one of loop or loop_factory")

    def run(self, task: TaskDomain) -> TaskRunResult:
        runner = self.loop_factory(task) if self.loop_factory is not None else self.loop
        if runner is None:  # guarded by __post_init__, kept for type narrowing.
            return TaskRunResult(error_ref="agent_loop_unavailable")
        run_input = task.intent
        if self.context_builder_factory is not None:
            try:
                context_result = self.context_builder_factory(task).build(
                    ContextBuildRequest(
                        session_id=task.session_id,
                        task_id=task.task_id,
                        agent_id=task.claimed_by or DEFAULT_FIXED_ROUTE_AGENT_ID,
                        purpose="execution_start",
                        writer=True,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - agent contract returns TaskRunResult.
                error_ref = _store_context_build_exception_summary(
                    self.result_summary_store,
                    task,
                    exc,
                )
                return TaskRunResult(error_ref=error_ref)
            run_input = context_result.rendered.user_content

        result = runner.run(run_input, task_id=task.task_id)
        if result.finished:
            result_ref = (
                f"{self.result_ref_prefix}:{task.session_id}:{task.task_id}:{result.stop_reason}"
            )
            if self.result_summary_store is not None:
                self.result_summary_store.put(
                    build_agent_loop_result_summary(
                        summary_id=result_ref,
                        task=task,
                        final_answer=result.final_answer,
                        stop_reason=result.stop_reason,
                    )
                )
            return TaskRunResult(result_ref=result_ref)
        error_ref = f"{self.error_ref_prefix}:{task.session_id}:{task.task_id}:{result.stop_reason}"
        if self.result_summary_store is not None:
            self.result_summary_store.put(
                build_agent_loop_error_summary(
                    summary_id=error_ref,
                    task=task,
                    stop_reason=result.stop_reason,
                    final_answer=result.final_answer,
                )
            )
        return TaskRunResult(error_ref=error_ref)


def _select_next_eligible_pending_task(
    task_bus: TaskBus,
    session_id: str,
) -> TaskDomain | None:
    tasks = task_bus.list_for_session(session_id)
    task_by_id = {task.task_id: task for task in tasks}
    for task in tasks:
        if task.status != "pending":
            continue
        if task.parent_id is None:
            return task
        parent = task_by_id.get(task.parent_id)
        if parent is not None and task_effectively_done(parent, tasks):
            return task
    return None


def _dispatch_result(
    *,
    status: ExecutionDispatchRequestStatus,
    session_id: str,
    reason: ExecutionDispatchTriggerReason,
    request_id: str | None,
    error_ref: str | None = None,
) -> ExecutionDispatchRequestResult:
    messages = {
        "queued": "execution dispatch queued",
        "already_pending": "execution dispatch already pending",
        "already_running": "execution dispatch already running",
        "disabled": "execution dispatcher is disabled",
        "health_error": "execution dispatcher is unavailable",
        "closed": "execution dispatcher is closed",
    }
    return ExecutionDispatchRequestResult(
        status=status,
        session_id=session_id,
        reason=reason,
        request_id=request_id,
        message=messages[status],
        error_ref=error_ref,
    )


def _store_execution_exception_summary(
    store: TaskExecutionSummaryStore | None,
    task: TaskDomain,
    exc: Exception,
) -> str:
    fallback = f"agent_execution_failed: {type(exc).__name__}"
    if store is None:
        return fallback
    error_ref = f"agent_execution_failed:{task.session_id}:{task.task_id}:{type(exc).__name__}"
    store.put(
        build_execution_exception_summary(
            summary_id=error_ref,
            task=task,
            exc=exc,
        )
    )
    return error_ref


def _store_context_build_exception_summary(
    store: TaskExecutionSummaryStore | None,
    task: TaskDomain,
    exc: Exception,
) -> str:
    error_ref = f"context_build_failed:{task.session_id}:{task.task_id}:{type(exc).__name__}"
    if store is not None:
        store.put(
            build_execution_exception_summary(
                summary_id=error_ref,
                task=task,
                exc=exc,
            )
        )
    return error_ref


def _ensure_result_ref_readable(
    store: TaskExecutionSummaryStore | None,
    task: TaskDomain,
    result_ref: str | None,
) -> str | None:
    if store is None:
        return result_ref
    if result_ref is None:
        result_ref = f"task_result:{task.session_id}:{task.task_id}:completed"
        store.put(build_execution_completed_summary(summary_id=result_ref, task=task))
        return result_ref
    if store.get(result_ref) is None:
        store.put(build_external_result_ref_summary(result_ref=result_ref, task=task))
    return result_ref


def _ensure_error_ref_readable(
    store: TaskExecutionSummaryStore | None,
    task: TaskDomain,
    error_ref: str,
) -> str:
    if store is None:
        return error_ref
    if store.get(error_ref) is None:
        store.put(build_external_error_ref_summary(error_ref=error_ref, task=task))
    return error_ref


def _summary_for_ref(
    store: TaskExecutionSummaryStore | None,
    summary_id: str | None,
) -> TaskExecutionSummary | None:
    if store is None or summary_id is None:
        return None
    return store.get(summary_id)


def _publish_execution_message(
    message_bus: MessageBus | None,
    task: TaskDomain,
    *,
    summary: TaskExecutionSummary | None,
) -> None:
    if message_bus is None:
        return
    is_error = task.status == "failed"
    title = "Task failed" if is_error else "Task completed"
    body = summary.summary if summary is not None else title + "."
    context: dict[str, object] = {
        "task_ref_kind": "published",
        "title": title,
        "execution_status": task.status,
    }
    if task.result_ref is not None:
        context["result_ref"] = task.result_ref
    if task.error_ref is not None:
        context["error_ref"] = task.error_ref
        context["ui_kind"] = "error"
    if summary is not None:
        context["summary_id"] = summary.summary_id
        context["summary_kind"] = summary.kind
        context["summary_source"] = summary.source

    message = AgentMessage(
        session_id=task.session_id,
        task_id=task.task_id,
        agent_id="agent",
        message_type="informational",
        content=body,
        context=context,
    )
    # MessageStream is a projection surface. A write failure must not overturn
    # the already-committed TaskBus lifecycle fact.
    with contextlib.suppress(MessageStreamError):
        message_bus.publish(message)


__all__ = [
    "AgentLoopResidentDefaultAgent",
    "AgentLoopRunner",
    "AgentLoopRunnerFactory",
    "DEFAULT_FIXED_ROUTE_AGENT_ID",
    "ExecutionContextBuilder",
    "ExecutionContextBuilderFactory",
    "ExecutionDispatchRequestResult",
    "ExecutionDispatchRequestStatus",
    "ExecutionDispatchTriggerReason",
    "ExecutionTriggerGateway",
    "FixedRouteExecutionDispatcher",
    "FixedRouteTaskExecutor",
    "FixedRouteTaskExecutorConfig",
    "ResidentDefaultAgent",
    "TaskExecutionTickResult",
    "TaskExecutionTickStatus",
    "TaskRunResult",
]
