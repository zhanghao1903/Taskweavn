"""Tests for the Product 1.0 fixed-route Task execution bridge."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from taskweavn.context import InMemoryContextStore, SessionContextManager, TaskContextSource
from taskweavn.context.models import ContextBuildRequest, ContextBuildResult
from taskweavn.core.loop import LoopResult
from taskweavn.interaction import AgentMessage, MessageStream, Subscription
from taskweavn.task import (
    AgentLoopResidentDefaultAgent,
    FixedRouteExecutionDispatcher,
    FixedRouteTaskExecutor,
    FixedRouteTaskExecutorConfig,
    InMemoryTaskBus,
    InMemoryTaskExecutionSummaryStore,
    TaskDispatchConstraints,
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
    bus = InMemoryTaskBus(
        [
            _task("root", status="running"),
            _task("child", parent_id="root", root_id="root"),
        ]
    )
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


def test_fixed_route_executor_waits_for_in_place_parent_retry() -> None:
    bus = InMemoryTaskBus(
        [
            _task("root", status="failed"),
            _task("child", parent_id="root", root_id="root"),
        ]
    )
    agent = _SequencedAgent()
    executor = FixedRouteTaskExecutor(
        task_bus=bus,
        default_agent=agent,
        config=FixedRouteTaskExecutorConfig(session_id="s1"),
    )

    result = executor.tick()

    assert result.status == "idle"
    assert agent.seen == []

    bus.retry("s1", "root")
    retry_result = executor.tick()
    child_result = executor.tick()

    assert retry_result.status == "completed"
    assert retry_result.completed_task_id == "root"
    assert child_result.status == "completed"
    assert child_result.completed_task_id == "child"
    assert agent.seen == ["root", "child"]
    root = bus.get("s1", "root")
    child = bus.get("s1", "child")
    assert root is not None
    assert root.status == "done"
    assert child is not None
    assert child.status == "done"
    assert child.result_ref == "result:child"


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
    assert loop.seen_task_ids == ["task-1"]


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
    assert result.error_ref == "agent_loop_failed:s1:task-1:max_steps"


def test_agent_loop_resident_default_agent_stores_finished_result_summary() -> None:
    store = InMemoryTaskExecutionSummaryStore()
    loop = _FakeLoop(
        LoopResult(
            final_answer="Built the requested artifact.",
            steps=1,
            finished=True,
            stop_reason="agent_finish",
        )
    )
    agent = AgentLoopResidentDefaultAgent(loop=loop, result_summary_store=store)

    result = agent.run(_task("task-1"))

    assert result.result_ref == "agent_loop:s1:task-1:agent_finish"
    assert result.result_ref is not None
    summary = store.get(result.result_ref)
    assert summary is not None
    assert summary.kind == "result"
    assert summary.summary == "Built the requested artifact."
    assert summary.final_answer == "Built the requested artifact."


def test_agent_loop_resident_default_agent_stores_unfinished_error_summary() -> None:
    store = InMemoryTaskExecutionSummaryStore()
    loop = _FakeLoop(
        LoopResult(
            final_answer="Partial answer",
            steps=20,
            finished=False,
            stop_reason="max_steps",
        )
    )
    agent = AgentLoopResidentDefaultAgent(loop=loop, result_summary_store=store)

    result = agent.run(_task("task-1"))

    assert result.error_ref == "agent_loop_failed:s1:task-1:max_steps"
    assert result.error_ref is not None
    summary = store.get(result.error_ref)
    assert summary is not None
    assert summary.kind == "error"
    assert summary.error_type == "agent_loop_failed"
    assert summary.stop_reason == "max_steps"


def test_agent_loop_resident_default_agent_uses_task_scoped_runner_factory() -> None:
    seen_tasks: list[str] = []

    def factory(task: TaskDomain) -> _FakeLoop:
        seen_tasks.append(task.task_id)
        return _FakeLoop(
            LoopResult(
                final_answer="Done",
                steps=1,
                finished=True,
                stop_reason="agent_finish",
            )
        )

    agent = AgentLoopResidentDefaultAgent(loop_factory=factory)

    result = agent.run(_task("task-1"))

    assert result.ok is True
    assert result.result_ref == "agent_loop:s1:task-1:agent_finish"
    assert seen_tasks == ["task-1"]


def test_agent_loop_resident_default_agent_uses_context_builder_for_run_input() -> None:
    bus = InMemoryTaskBus([_task("task-1")])
    store = InMemoryContextStore()
    manager = SessionContextManager(
        task_source=TaskContextSource(bus),
        store=store,
    )
    loop = _FakeLoop(
        LoopResult(
            final_answer="Done",
            steps=1,
            finished=True,
            stop_reason="agent_finish",
        )
    )
    agent = AgentLoopResidentDefaultAgent(
        loop=loop,
        context_builder_factory=lambda task: manager,
    )

    result = agent.run(_task("task-1"))

    assert result.ok is True
    assert loop.seen_task_ids == ["task-1"]
    assert len(loop.seen) == 1
    assert loop.seen[0] != "Do task-1"
    assert "# Task Execution Context" in loop.seen[0]
    assert "Do task-1" in loop.seen[0]
    snapshots = store.list_snapshots_for_task("s1", "task-1")
    assert len(snapshots) == 1


def test_agent_loop_resident_default_agent_reports_context_build_failure() -> None:
    class FailingContextBuilder:
        def build(self, request: ContextBuildRequest) -> ContextBuildResult:
            del request
            raise RuntimeError("context unavailable")

    store = InMemoryTaskExecutionSummaryStore()
    loop = _FakeLoop(
        LoopResult(
            final_answer="Done",
            steps=1,
            finished=True,
            stop_reason="agent_finish",
        )
    )
    agent = AgentLoopResidentDefaultAgent(
        loop=loop,
        context_builder_factory=lambda task: FailingContextBuilder(),
        result_summary_store=store,
    )

    result = agent.run(_task("task-1"))

    assert result.error_ref == "context_build_failed:s1:task-1:RuntimeError"
    assert loop.seen == []
    summary = store.get(result.error_ref)
    assert summary is not None
    assert summary.kind == "error"
    assert summary.error_type == "RuntimeError"


def test_fixed_route_executor_can_use_agent_loop_resident_default_agent() -> None:
    bus = InMemoryTaskBus([_task("task-1")])
    loop = _FakeLoop(
        LoopResult(
            final_answer="Done",
            steps=1,
            finished=True,
            stop_reason="no_tool_calls",
        )
    )
    agent = AgentLoopResidentDefaultAgent(loop=loop)
    executor = FixedRouteTaskExecutor(
        task_bus=bus,
        default_agent=agent,
        config=FixedRouteTaskExecutorConfig(session_id="s1"),
    )

    result = executor.tick()

    assert result.status == "completed"
    assert result.result_ref == "agent_loop:s1:task-1:no_tool_calls"
    assert loop.seen_task_ids == ["task-1"]

    task = bus.get("s1", "task-1")
    assert task is not None
    assert task.status == "done"
    assert task.result_ref == "agent_loop:s1:task-1:no_tool_calls"


def test_fixed_route_executor_stores_exception_error_summary_when_store_is_available() -> None:
    store = InMemoryTaskExecutionSummaryStore()
    bus = InMemoryTaskBus([_task("task-1")])
    executor = FixedRouteTaskExecutor(
        task_bus=bus,
        default_agent=_FakeAgent(raises=RuntimeError("boom")),
        config=FixedRouteTaskExecutorConfig(session_id="s1"),
        result_summary_store=store,
    )

    result = executor.tick()

    assert result.status == "failed"
    assert result.error_ref == "agent_execution_failed:s1:task-1:RuntimeError"
    assert result.error_ref is not None
    summary = store.get(result.error_ref)
    assert summary is not None
    assert summary.kind == "error"
    assert summary.error_type == "RuntimeError"


def test_fixed_route_executor_stores_completed_summary_when_agent_omits_ref() -> None:
    store = InMemoryTaskExecutionSummaryStore()
    bus = InMemoryTaskBus([_task("task-1")])
    executor = FixedRouteTaskExecutor(
        task_bus=bus,
        default_agent=_FakeAgent(TaskRunResult()),
        config=FixedRouteTaskExecutorConfig(session_id="s1"),
        result_summary_store=store,
    )

    result = executor.tick()

    assert result.status == "completed"
    assert result.result_ref == "task_result:s1:task-1:completed"
    summary = store.get("task_result:s1:task-1:completed")
    assert summary is not None
    assert summary.kind == "result"
    assert summary.source == "execution_bridge"
    assert summary.summary == "Task completed."


def test_fixed_route_executor_publishes_completion_message() -> None:
    store = InMemoryTaskExecutionSummaryStore()
    messages = _MessageBus()
    bus = InMemoryTaskBus([_task("task-1")])
    executor = FixedRouteTaskExecutor(
        task_bus=bus,
        default_agent=_FakeAgent(TaskRunResult(result_ref="result:task-1")),
        config=FixedRouteTaskExecutorConfig(session_id="s1"),
        result_summary_store=store,
        message_bus=messages,
    )

    result = executor.tick()

    assert result.status == "completed"
    assert len(messages.published) == 1
    message = messages.published[0]
    assert message.task_id == "task-1"
    assert message.message_type == "informational"
    assert message.content == "Task completed. Result reference: result:task-1."
    assert message.context["title"] == "Task completed"
    assert message.context["result_ref"] == "result:task-1"


def test_fixed_route_executor_publishes_failure_message() -> None:
    store = InMemoryTaskExecutionSummaryStore()
    messages = _MessageBus()
    bus = InMemoryTaskBus([_task("task-1")])
    executor = FixedRouteTaskExecutor(
        task_bus=bus,
        default_agent=_FakeAgent(TaskRunResult(error_ref="agent:error")),
        config=FixedRouteTaskExecutorConfig(session_id="s1"),
        result_summary_store=store,
        message_bus=messages,
    )

    result = executor.tick()

    assert result.status == "failed"
    assert len(messages.published) == 1
    message = messages.published[0]
    assert message.task_id == "task-1"
    assert message.content == "Task execution failed. Error reference: agent:error."
    assert message.context["title"] == "Task failed"
    assert message.context["ui_kind"] == "error"
    assert message.context["error_ref"] == "agent:error"


def test_fixed_route_dispatcher_queues_and_completes_pending_task() -> None:
    bus = InMemoryTaskBus([_task("task-1")])
    dispatcher = FixedRouteExecutionDispatcher(
        task_bus=bus,
        default_agent=_FakeAgent(TaskRunResult(result_ref="result:task-1")),
    )
    try:
        request = dispatcher.request_dispatch(
            "s1",
            reason="manual_control_route",
            request_id="dispatch-1",
        )

        assert request.status == "queued"
        assert request.accepted is True
        assert _wait_for(lambda: _task_has_status(bus, "task-1", "done"))
        task = bus.get("s1", "task-1")
        assert task is not None
        assert task.result_ref == "result:task-1"
    finally:
        dispatcher.stop()


def test_fixed_route_dispatcher_drains_multiple_completed_tasks() -> None:
    bus = InMemoryTaskBus([_task("task-1"), _task("task-2")])
    dispatcher = FixedRouteExecutionDispatcher(
        task_bus=bus,
        default_agent=_SequencedAgent(),
        max_ticks_per_trigger=2,
    )
    try:
        request = dispatcher.request_dispatch("s1", reason="manual_control_route")

        assert request.status == "queued"
        assert _wait_for(
            lambda: [task.status for task in bus.list_for_session("s1")] == ["done", "done"]
        )
    finally:
        dispatcher.stop()


def test_fixed_route_dispatcher_coalesces_duplicate_running_trigger() -> None:
    bus = InMemoryTaskBus([_task("task-1")])
    agent = _BlockingAgent()
    dispatcher = FixedRouteExecutionDispatcher(task_bus=bus, default_agent=agent)
    try:
        first = dispatcher.request_dispatch("s1", reason="manual_control_route")
        assert first.status == "queued"
        assert agent.started.wait(timeout=2.0)

        duplicate = dispatcher.request_dispatch("s1", reason="manual_control_route")

        assert duplicate.status == "already_running"
        agent.release.set()
        assert _wait_for(lambda: _task_has_status(bus, "task-1", "done"))
    finally:
        agent.release.set()
        dispatcher.stop()


def test_fixed_route_dispatcher_disabled_does_not_claim() -> None:
    bus = InMemoryTaskBus([_task("task-1")])
    dispatcher = FixedRouteExecutionDispatcher(
        task_bus=bus,
        default_agent=_FakeAgent(TaskRunResult(result_ref="result:task-1")),
        enabled=False,
    )
    try:
        request = dispatcher.request_dispatch("s1", reason="manual_control_route")
        task = bus.get("s1", "task-1")
    finally:
        dispatcher.stop()

    assert request.status == "disabled"
    assert request.accepted is False
    assert task is not None
    assert task.status == "pending"
    assert task.claimed_by is None


def test_fixed_route_dispatcher_reports_missing_default_agent() -> None:
    bus = InMemoryTaskBus([_task("task-1")])
    dispatcher = FixedRouteExecutionDispatcher(task_bus=bus, default_agent=None)
    try:
        request = dispatcher.request_dispatch("s1", reason="manual_control_route")
        task = bus.get("s1", "task-1")
    finally:
        dispatcher.stop()

    assert request.status == "health_error"
    assert request.error_ref == "default_agent_unavailable"
    assert task is not None
    assert task.status == "pending"
    assert task.claimed_by is None


def test_fixed_route_dispatcher_stop_rejects_later_triggers() -> None:
    bus = InMemoryTaskBus([_task("task-1")])
    dispatcher = FixedRouteExecutionDispatcher(
        task_bus=bus,
        default_agent=_FakeAgent(TaskRunResult(result_ref="result:task-1")),
    )

    dispatcher.stop()
    request = dispatcher.request_dispatch("s1", reason="manual_control_route")

    assert request.status == "closed"
    assert request.accepted is False


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
class _SequencedAgent:
    seen: list[str] = field(default_factory=list)

    def run(self, task: TaskDomain) -> TaskRunResult:
        self.seen.append(task.task_id)
        return TaskRunResult(result_ref=f"result:{task.task_id}")


@dataclass
class _BlockingAgent:
    started: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)

    def run(self, task: TaskDomain) -> TaskRunResult:
        self.started.set()
        self.release.wait(timeout=2.0)
        return TaskRunResult(result_ref=f"result:{task.task_id}")


@dataclass
class _MessageBus:
    published: list[AgentMessage] = field(default_factory=list)

    def publish(self, message: AgentMessage) -> None:
        self.published.append(message)

    def subscribe(
        self,
        session_id: str,
        *,
        types: Iterable[str] | None = None,
    ) -> Subscription:
        raise NotImplementedError

    def wait_for_response(
        self,
        message_id: str,
        timeout: float | None,
    ) -> AgentMessage | None:
        raise NotImplementedError

    @property
    def stream(self) -> MessageStream:
        raise NotImplementedError


@dataclass
class _FakeLoop:
    result: LoopResult
    seen: list[str] = field(default_factory=list)
    seen_task_ids: list[str | None] = field(default_factory=list)

    def run(self, task: str, *, task_id: str | None = None) -> LoopResult:
        self.seen.append(task)
        self.seen_task_ids.append(task_id)
        return self.result


def _task(
    task_id: str,
    *,
    status: TaskStatus = "pending",
    parent_id: str | None = None,
    root_id: str | None = None,
    required_capability: str = "general",
    metadata: dict[str, object] | None = None,
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
        dispatch_constraints=(
            TaskDispatchConstraints(metadata=metadata) if metadata is not None else None
        ),
    )


def _wait_for(predicate: Callable[[], bool], *, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def _task_has_status(
    bus: InMemoryTaskBus,
    task_id: str,
    status: TaskStatus,
) -> bool:
    task = bus.get("s1", task_id)
    return task is not None and task.status == status
