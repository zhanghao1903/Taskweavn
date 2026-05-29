"""Tests for the Product 1.0 fixed-route Task execution bridge."""

from __future__ import annotations

from dataclasses import dataclass, field

from taskweavn.core.loop import LoopResult
from taskweavn.task import (
    AgentLoopResidentDefaultAgent,
    FixedRouteTaskExecutor,
    FixedRouteTaskExecutorConfig,
    InMemoryTaskBus,
    TaskDomain,
    TaskRunResult,
    TaskStatus,
)


def test_fixed_route_executor_claims_and_completes_pending_task() -> None:
    bus = InMemoryTaskBus([_task("task-1")])
    agent = _FakeAgent(TaskRunResult(result_ref="result:task-1"))
    executor = FixedRouteTaskExecutor(
        task_bus=bus,
        default_agent=agent,
        config=FixedRouteTaskExecutorConfig(
            session_id="s1",
            default_agent_id="resident-default",
        ),
    )

    result = executor.tick()

    assert result.status == "completed"
    assert result.claimed_task_id == "task-1"
    assert result.completed_task_id == "task-1"
    assert result.result_ref == "result:task-1"
    assert agent.seen == ["task-1"]

    task = bus.get("s1", "task-1")
    assert task is not None
    assert task.status == "done"
    assert task.claimed_by == "resident-default"
    assert task.result_ref == "result:task-1"


def test_fixed_route_executor_fails_when_agent_returns_error() -> None:
    bus = InMemoryTaskBus([_task("task-1")])
    executor = FixedRouteTaskExecutor(
        task_bus=bus,
        default_agent=_FakeAgent(TaskRunResult(error_ref="agent:error")),
        config=FixedRouteTaskExecutorConfig(session_id="s1"),
    )

    result = executor.tick()

    assert result.status == "failed"
    assert result.failed_task_id == "task-1"
    assert result.error_ref == "agent:error"

    task = bus.get("s1", "task-1")
    assert task is not None
    assert task.status == "failed"
    assert task.error_ref == "agent:error"


def test_fixed_route_executor_fails_when_agent_raises() -> None:
    bus = InMemoryTaskBus([_task("task-1")])
    executor = FixedRouteTaskExecutor(
        task_bus=bus,
        default_agent=_FakeAgent(raises=RuntimeError("boom")),
        config=FixedRouteTaskExecutorConfig(session_id="s1"),
    )

    result = executor.tick()

    assert result.status == "failed"
    assert result.failed_task_id == "task-1"
    assert result.error_ref == "agent_execution_failed: RuntimeError"

    task = bus.get("s1", "task-1")
    assert task is not None
    assert task.status == "failed"
    assert task.error_ref == "agent_execution_failed: RuntimeError"


def test_fixed_route_executor_noops_when_no_task_is_eligible() -> None:
    bus = InMemoryTaskBus()
    executor = FixedRouteTaskExecutor(
        task_bus=bus,
        default_agent=_FakeAgent(TaskRunResult(result_ref="result:none")),
        config=FixedRouteTaskExecutorConfig(session_id="s1"),
    )

    result = executor.tick()

    assert result.status == "idle"
    assert result.skipped_reason == "no_eligible_task"


def test_fixed_route_executor_does_not_claim_when_default_agent_unavailable() -> None:
    bus = InMemoryTaskBus([_task("task-1")])
    executor = FixedRouteTaskExecutor(
        task_bus=bus,
        default_agent=None,
        config=FixedRouteTaskExecutorConfig(session_id="s1"),
    )

    result = executor.tick()

    assert result.status == "health_error"
    assert result.error_ref == "default_agent_unavailable"

    task = bus.get("s1", "task-1")
    assert task is not None
    assert task.status == "pending"
    assert task.claimed_by is None


def test_fixed_route_executor_respects_parent_dependency() -> None:
    bus = InMemoryTaskBus([
        _task("root", status="running"),
        _task("child", parent_id="root", root_id="root"),
    ])
    executor = FixedRouteTaskExecutor(
        task_bus=bus,
        default_agent=_FakeAgent(TaskRunResult(result_ref="result:child")),
        config=FixedRouteTaskExecutorConfig(session_id="s1"),
    )

    result = executor.tick()

    assert result.status == "idle"
    assert result.skipped_reason == "no_eligible_task"

    child = bus.get("s1", "child")
    assert child is not None
    assert child.status == "pending"
    assert child.claimed_by is None


def test_agent_loop_resident_default_agent_maps_finished_loop_to_result_ref() -> None:
    loop = _FakeLoop(
        LoopResult(
            final_answer="Done",
            steps=1,
            finished=True,
            stop_reason="agent_finish",
        )
    )
    agent = AgentLoopResidentDefaultAgent(loop=loop)

    result = agent.run(_task("task-1"))

    assert result.ok is True
    assert result.result_ref == "agent_loop:s1:task-1:agent_finish"
    assert loop.seen == ["Do task-1"]


def test_agent_loop_resident_default_agent_maps_unfinished_loop_to_error() -> None:
    loop = _FakeLoop(
        LoopResult(
            final_answer="",
            steps=20,
            finished=False,
            stop_reason="max_steps",
        )
    )
    agent = AgentLoopResidentDefaultAgent(loop=loop)

    result = agent.run(_task("task-1"))

    assert result.ok is False
    assert result.error_ref == "agent_loop_failed: max_steps"


def test_fixed_route_executor_can_use_agent_loop_resident_default_agent() -> None:
    bus = InMemoryTaskBus([_task("task-1")])
    agent = AgentLoopResidentDefaultAgent(
        loop=_FakeLoop(
            LoopResult(
                final_answer="Done",
                steps=1,
                finished=True,
                stop_reason="no_tool_calls",
            )
        )
    )
    executor = FixedRouteTaskExecutor(
        task_bus=bus,
        default_agent=agent,
        config=FixedRouteTaskExecutorConfig(session_id="s1"),
    )

    result = executor.tick()

    assert result.status == "completed"
    assert result.result_ref == "agent_loop:s1:task-1:no_tool_calls"

    task = bus.get("s1", "task-1")
    assert task is not None
    assert task.status == "done"
    assert task.result_ref == "agent_loop:s1:task-1:no_tool_calls"


@dataclass
class _FakeAgent:
    result: TaskRunResult | None = None
    raises: Exception | None = None
    seen: list[str] = field(default_factory=list)

    def run(self, task: TaskDomain) -> TaskRunResult:
        self.seen.append(task.task_id)
        if self.raises is not None:
            raise self.raises
        return self.result or TaskRunResult()


@dataclass
class _FakeLoop:
    result: LoopResult
    seen: list[str] = field(default_factory=list)

    def run(self, task: str) -> LoopResult:
        self.seen.append(task)
        return self.result


def _task(
    task_id: str,
    *,
    status: TaskStatus = "pending",
    parent_id: str | None = None,
    root_id: str | None = None,
    required_capability: str = "general",
) -> TaskDomain:
    return TaskDomain(
        task_id=task_id,
        session_id="s1",
        parent_id=parent_id,
        root_id=root_id or task_id,
        intent=f"Do {task_id}",
        required_capability=required_capability,
        status=status,
        created_by="tester",
    )
