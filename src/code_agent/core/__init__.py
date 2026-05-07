"""Core agent runtime: EventStream, sessions, and the ReAct loop."""

from code_agent.core.event_stream import EventStream, InMemoryEventStream
from code_agent.core.loop import (
    DEFAULT_SYSTEM_PROMPT,
    FINISH_TOOL_NAME,
    AgentLoop,
    LoopError,
    LoopResult,
)
from code_agent.core.session import (
    Session,
    SessionStatus,
    new_session_id,
)
from code_agent.core.session_manager import (
    SessionManager,
    SessionManagerError,
)
from code_agent.core.sqlite_event_stream import SqliteEventStream
from code_agent.core.workspace_layout import WorkspaceLayout

__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "FINISH_TOOL_NAME",
    "AgentLoop",
    "EventStream",
    "InMemoryEventStream",
    "LoopError",
    "LoopResult",
    "Session",
    "SessionManager",
    "SessionManagerError",
    "SessionStatus",
    "SqliteEventStream",
    "WorkspaceLayout",
    "new_session_id",
]
