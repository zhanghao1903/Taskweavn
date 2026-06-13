"""Resident default-agent assembly for the Plato Main Page sidecar."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from taskweavn.context import (
    AskContextSource,
    ContextBuildRequest,
    ContextBuildResult,
    ControlContextSource,
    EventStreamContextSource,
    SessionAgentLoopContextProvider,
    SessionContextManager,
    SqliteContextStore,
    TaskContextSource,
)
from taskweavn.core import (
    LoopInterruptIntent,
    LoopResult,
    SqliteEventStream,
    WorkspaceLayout,
)
from taskweavn.interaction import AskStore
from taskweavn.runtime import LocalRuntime
from taskweavn.server.main_page_audit_events import (
    emit_agent_loop_audit_records_changed,
)
from taskweavn.server.ui_events import UiEventStore
from taskweavn.task import (
    AgentLoopResidentDefaultAgent,
    TaskBus,
    TaskDomain,
    TaskExecutionSummaryStore,
)
from taskweavn.tools import (
    AppendFileTool,
    AskUserTool,
    ListDirTool,
    ReadFileRangeTool,
    ReadFileTool,
    ReplaceFileRangeTool,
    RunCommandTool,
    SearchWorkspaceTool,
    Tool,
    Workspace,
    WriteFileTool,
)


def build_agent_loop_resident_default_agent(
    *,
    layout: WorkspaceLayout,
    llm: Any,
    task_bus: TaskBus | None = None,
    ask_store: AskStore | None = None,
    max_steps: int = 20,
    result_summary_store: TaskExecutionSummaryStore | None = None,
    ui_event_store: UiEventStore | None = None,
) -> AgentLoopResidentDefaultAgent:
    """Build the resident Default Agent used by the fixed-route sidecar bridge."""

    context_builder_factory: Callable[[TaskDomain], _SessionContextBuilder] | None = None
    if task_bus is not None:

        def build_context_builder(task: TaskDomain) -> _SessionContextBuilder:
            return _SessionContextBuilder(
                layout=layout,
                task_bus=task_bus,
                ask_store=ask_store,
                session_id=task.session_id,
            )

        context_builder_factory = build_context_builder

    return AgentLoopResidentDefaultAgent(
        loop_factory=lambda task: _SessionAgentLoopRunner(
            layout=layout,
            llm=llm,
            session_id=task.session_id,
            max_steps=max_steps,
            ui_event_store=ui_event_store,
            task_bus=task_bus,
            ask_store=ask_store,
            context_builder=(
                None if context_builder_factory is None else context_builder_factory(task)
            ),
        ),
        context_builder_factory=context_builder_factory,
        result_summary_store=result_summary_store,
    )


@dataclass(frozen=True)
class _SessionContextBuilder:
    """Build execution context from session-scoped durable sources."""

    layout: WorkspaceLayout
    task_bus: TaskBus
    ask_store: AskStore | None
    session_id: str

    def build(self, request: ContextBuildRequest) -> ContextBuildResult:
        self.layout.bootstrap_session(self.session_id)
        with (
            SqliteEventStream(self.layout.session_events_db(self.session_id)) as event_stream,
            SqliteContextStore(self.layout.session_context_db(self.session_id)) as context_store,
        ):
            manager = SessionContextManager(
                task_source=TaskContextSource(self.task_bus),
                event_source=EventStreamContextSource(
                    event_stream,
                    workspace_id=f"session:{self.session_id}",
                ),
                ask_source=(
                    None if self.ask_store is None else AskContextSource(self.ask_store)
                ),
                control_source=ControlContextSource(
                    allowed_tools=_allowed_tools(self.ask_store is not None),
                ),
                store=context_store,
            )
            return manager.build(request)


@dataclass(frozen=True)
class _SessionAgentLoopRunner:
    """Create one AgentLoop run with session-scoped workspace and events."""

    layout: WorkspaceLayout
    llm: Any
    session_id: str
    max_steps: int
    ui_event_store: UiEventStore | None = None
    task_bus: TaskBus | None = None
    ask_store: AskStore | None = None
    context_builder: _SessionContextBuilder | None = None

    def run(self, task: str, *, task_id: str | None = None) -> LoopResult:
        from taskweavn.core.loop import AgentLoop

        self.layout.bootstrap_session(self.session_id)
        workspace = Workspace(self.layout.session_project_dir(self.session_id))
        runtime = LocalRuntime()
        tools: list[Tool[Any, Any]] = [
            ReadFileTool(workspace),
            ReadFileRangeTool(
                workspace,
                workspace_id=f"session:{self.session_id}",
                inspection_db_path=self.layout.workspace_inspection_db,
            ),
            SearchWorkspaceTool(
                workspace,
                workspace_id=f"session:{self.session_id}",
                inspection_db_path=self.layout.workspace_inspection_db,
            ),
            ReplaceFileRangeTool(
                workspace,
                workspace_id=f"session:{self.session_id}",
                inspection_db_path=self.layout.workspace_inspection_db,
            ),
            AppendFileTool(
                workspace,
                workspace_id=f"session:{self.session_id}",
                inspection_db_path=self.layout.workspace_inspection_db,
            ),
            WriteFileTool(workspace),
            ListDirTool(workspace),
            RunCommandTool(workspace),
        ]
        if self.ask_store is not None and self.task_bus is not None and task_id is not None:
            tools.append(
                AskUserTool(
                    ask_store=self.ask_store,
                    task_bus=self.task_bus,
                    session_id=self.session_id,
                    task_id=task_id,
                )
            )
        for tool in tools:
            tool.register(runtime)

        event_stream = SqliteEventStream(self.layout.session_events_db(self.session_id))
        try:
            loop = AgentLoop(
                llm=self.llm,
                runtime=runtime,
                tools=tools,
                event_stream=event_stream,
                max_steps=self.max_steps,
                session_id=self.session_id,
                workspace_root=workspace.root,
                context_provider=(
                    None
                    if self.context_builder is None
                    else SessionAgentLoopContextProvider(self.context_builder)
                ),
                interrupt_checker=(
                    None
                    if self.task_bus is None
                    else _TaskBusInterruptChecker(
                        task_bus=self.task_bus,
                        session_id=self.session_id,
                    )
                ),
            )
            result = loop.run(task, task_id=task_id)
            if task_id is not None:
                emit_agent_loop_audit_records_changed(
                    self.ui_event_store,
                    session_id=self.session_id,
                    task_id=task_id,
                )
            return result
        finally:
            event_stream.close()


@dataclass(frozen=True)
class _TaskBusInterruptChecker:
    """Read the latest TaskBus interrupt intent for one running task."""

    task_bus: TaskBus
    session_id: str

    def interrupt_for_task(self, task_id: str) -> LoopInterruptIntent | None:
        task = self.task_bus.get(self.session_id, task_id)
        if task is None or task.status != "running" or not task.interrupt_requested:
            return None
        return LoopInterruptIntent(
            task_id=task.task_id,
            request_id=task.interrupt_request_id,
            reason=task.interrupt_reason,
            requested_by=task.interrupt_requested_by,
        )


def _allowed_tools(include_ask_user: bool) -> tuple[str, ...]:
    tools = (
        "read_file",
        "read_file_range",
        "search_workspace",
        "replace_file_range",
        "append_file",
        "write_file",
        "list_dir",
        "run_command",
    )
    if include_ask_user:
        return (*tools, "ask_user")
    return tools


__all__ = ["build_agent_loop_resident_default_agent"]
