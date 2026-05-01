"""Core agent runtime: EventStream and (later) the ReAct loop."""

from code_agent.core.event_stream import EventStream, InMemoryEventStream

__all__ = ["EventStream", "InMemoryEventStream"]
