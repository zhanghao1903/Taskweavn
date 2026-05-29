"""Fixed-route execution bridge for Product 1.0 published Tasks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from taskweavn.core.loop import LoopResult
from taskweavn.task.bus import TaskBus
from taskweavn.task.models import TaskDomain

DEFAULT_FIXED_ROUTE_AGENT_ID = "default_agent"

TaskExecutionTickStatus = Literal[
    "idle",
    "completed",
    "failed",
    "claim_not_available",
    "health_error",
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

    def run(self, task: str) -> LoopResult: ...


AgentLoopRunnerFactory = Callable[[TaskDomain], AgentLoopRunner]


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
    ) -> None:
        self._task_bus = task_bus
        self._default_agent = default_agent
        self._config = config

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
            error_ref = f"agent_execution_failed: {type(exc).__name__}"
            failed = self._task_bus.fail(
                claimed.session_id,
                claimed.task_id,
                error_ref=error_ref,
            )
            return TaskExecutionTickResult(
                status="failed",
                session_id=self._config.session_id,
                claimed_task_id=claimed.task_id,
                failed_task_id=failed.task_id,
                error_ref=failed.error_ref,
            )

        if run_result.ok:
            completed = self._task_bus.complete(
                claimed.session_id,
                claimed.task_id,
                result_ref=run_result.result_ref,
            )
            return TaskExecutionTickResult(
                status="completed",
                session_id=self._config.session_id,
                claimed_task_id=claimed.task_id,
                completed_task_id=completed.task_id,
                result_ref=completed.result_ref,
            )

        error_ref = (run_result.error_ref or "").strip() or "agent_execution_failed"
        failed = self._task_bus.fail(
            claimed.session_id,
            claimed.task_id,
            error_ref=error_ref,
        )
        return TaskExecutionTickResult(
            status="failed",
            session_id=self._config.session_id,
            claimed_task_id=claimed.task_id,
            failed_task_id=failed.task_id,
            error_ref=failed.error_ref,
        )


@dataclass(frozen=True)
class AgentLoopResidentDefaultAgent:
    """Resident Default Agent adapter backed by an AgentLoop-compatible runner."""

    loop: AgentLoopRunner | None = None
    result_ref_prefix: str = "agent_loop"
    loop_factory: AgentLoopRunnerFactory | None = None

    def __post_init__(self) -> None:
        if (self.loop is None) == (self.loop_factory is None):
            raise ValueError("provide exactly one of loop or loop_factory")

    def run(self, task: TaskDomain) -> TaskRunResult:
        runner = self.loop_factory(task) if self.loop_factory is not None else self.loop
        if runner is None:  # guarded by __post_init__, kept for type narrowing.
            return TaskRunResult(error_ref="agent_loop_unavailable")
        result = runner.run(task.intent)
        if result.finished:
            return TaskRunResult(
                result_ref=(
                    f"{self.result_ref_prefix}:"
                    f"{task.session_id}:{task.task_id}:{result.stop_reason}"
                )
            )
        return TaskRunResult(error_ref=f"agent_loop_failed: {result.stop_reason}")


def _select_next_eligible_pending_task(
    task_bus: TaskBus,
    session_id: str,
) -> TaskDomain | None:
    for task in task_bus.list_for_session(session_id):
        if task.status != "pending":
            continue
        if task.parent_id is None:
            return task
        parent = task_bus.get(session_id, task.parent_id)
        if parent is not None and parent.status == "done":
            return task
    return None


__all__ = [
    "AgentLoopResidentDefaultAgent",
    "AgentLoopRunner",
    "AgentLoopRunnerFactory",
    "DEFAULT_FIXED_ROUTE_AGENT_ID",
    "FixedRouteTaskExecutor",
    "FixedRouteTaskExecutorConfig",
    "ResidentDefaultAgent",
    "TaskExecutionTickResult",
    "TaskExecutionTickStatus",
    "TaskRunResult",
]
