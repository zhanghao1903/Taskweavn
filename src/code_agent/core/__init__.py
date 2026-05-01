"""Core agent runtime: EventStream and the ReAct loop."""

from code_agent.core.event_stream import EventStream, InMemoryEventStream
from code_agent.core.loop import (
    DEFAULT_SYSTEM_PROMPT,
    FINISH_TOOL_NAME,
    AgentLoop,
    LoopError,
    LoopResult,
)

__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "FINISH_TOOL_NAME",
    "AgentLoop",
    "EventStream",
    "InMemoryEventStream",
    "LoopError",
    "LoopResult",
]
