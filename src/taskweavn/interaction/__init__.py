"""Phase 3 interaction layer: risk, autonomy, messages, message bus.

The interaction layer decides when the agent should pause, ask the user, or
proceed on its own. It owes the rest of the system three things:

* a quantitative risk model (``risk``) — how dangerous is this action?
* an autonomy contract (``autonomy``) — what does the user want us to do
  about that risk?
* a structured message channel (``message`` / ``bus`` — landing in 3.3 / 3.4)
  for the resulting user-facing prompts and replies.

This module is the seam between the strongly-typed Action/Observation core
and the human / multi-agent collaboration story documented in
``docs/interaction_layer_design.md``.
"""

from taskweavn.interaction.ask import (
    AskAnswer,
    AskAnswerType,
    AskCommandKind,
    AskCommandResultStatus,
    AskOption,
    AskQuestion,
    AskRequest,
    AskStatus,
    AskStore,
    AskStoreCommandResult,
    AskStoreError,
    InMemoryAskStore,
)
from taskweavn.interaction.autonomy import (
    AUTONOMY_PRESETS,
    AutonomyBehavior,
    AutonomyPresetName,
    get_preset,
)
from taskweavn.interaction.bus import (
    InProcessMessageBus,
    MessageBus,
    Subscription,
)
from taskweavn.interaction.gate import (
    AutonomyGate,
    ConfidenceProvider,
    GateDecision,
    GateVerdict,
)
from taskweavn.interaction.message import (
    AgentMessage,
    MessageStream,
    MessageStreamError,
    MessageType,
    ResponseSource,
)
from taskweavn.interaction.risk import (
    AssessmentContext,
    BaselineOnlyAssessor,
    CompositeAssessor,
    LLMRiskAssessor,
    RiskAssessment,
    RiskAssessor,
    RiskScore,
)
from taskweavn.interaction.sqlite_ask_store import SqliteAskStore
from taskweavn.interaction.sqlite_message_stream import SqliteMessageStream
from taskweavn.interaction.wait import WaitCoordinator, WaitOutcome, WaitResult

__all__ = [
    "AUTONOMY_PRESETS",
    "AgentMessage",
    "AskAnswer",
    "AskAnswerType",
    "AskCommandKind",
    "AskCommandResultStatus",
    "AskOption",
    "AskQuestion",
    "AskRequest",
    "AskStatus",
    "AskStore",
    "AskStoreCommandResult",
    "AskStoreError",
    "AssessmentContext",
    "AutonomyBehavior",
    "AutonomyGate",
    "AutonomyPresetName",
    "BaselineOnlyAssessor",
    "CompositeAssessor",
    "ConfidenceProvider",
    "GateDecision",
    "GateVerdict",
    "InMemoryAskStore",
    "InProcessMessageBus",
    "LLMRiskAssessor",
    "MessageBus",
    "MessageStream",
    "MessageStreamError",
    "MessageType",
    "ResponseSource",
    "RiskAssessment",
    "RiskAssessor",
    "RiskScore",
    "SqliteAskStore",
    "SqliteMessageStream",
    "Subscription",
    "WaitCoordinator",
    "WaitOutcome",
    "WaitResult",
    "get_preset",
]
