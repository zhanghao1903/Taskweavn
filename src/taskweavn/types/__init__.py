"""Strongly-typed Action / Observation system.

Public surface:
    BaseEvent, BaseAction, BaseObservation — base classes for events.
    ActionRegistry, ObservationRegistry  — auto-collected subclass registries.

Concrete Action / Observation subclasses live alongside the modules that
produce them (tools, runtime, loop). Importing those modules registers their
kinds with the registries.
"""

from taskweavn.types.base import BaseAction, BaseEvent, BaseObservation
from taskweavn.types.code_action import (
    CodeAction,
    CodeExecutionObservation,
    FileChange,
    TrackingConfig,
)
from taskweavn.types.common import (
    AgentFinishAction,
    AgentFinishObservation,
    ErrorObservation,
)
from taskweavn.types.registry import ActionRegistry, ObservationRegistry

__all__ = [
    "ActionRegistry",
    "AgentFinishAction",
    "AgentFinishObservation",
    "BaseAction",
    "BaseEvent",
    "BaseObservation",
    "CodeAction",
    "CodeExecutionObservation",
    "ErrorObservation",
    "FileChange",
    "ObservationRegistry",
    "TrackingConfig",
]
