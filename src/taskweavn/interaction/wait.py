"""WaitCoordinator — translate a published actionable into a wait outcome
(Phase 3.5).

Once :class:`AutonomyGate` says EMIT and the loop calls
:meth:`MessageBus.publish` on an ``actionable``, *something* has to decide
how long to wait, what counts as a timeout, and what to do when one fires.
That logic is here, encapsulated so the AgentLoop reduces to a single
``handle_actionable(message)`` call.

Two strategies, four timeout actions, one outcome enum:

* ``wait_strategy="async"`` — never block. Always returns
  :attr:`WaitOutcome.PENDING`; the loop continues and the response, if any,
  gets folded into a future iteration via ``drain_pending_responses``
  (Phase 3.6).
* ``wait_strategy="sync"`` — block on :meth:`MessageBus.wait_for_response`.
  On reply, return :attr:`WaitOutcome.GOT_RESPONSE`. On timeout, dispatch
  on ``timeout_action``:

  * ``wait`` — keep waiting (re-enter ``wait_for_response`` with ``None``
    timeout). The user explicitly opted into "no time pressure".
  * ``proceed_default`` — pick the first option in ``action_options`` (or
    ``None`` if the actionable carried no options) and return
    :attr:`WaitOutcome.TIMED_OUT_PROCEED`. The caller treats this as a
    user-supplied response and runs the original action.
  * ``proceed_confident`` — Phase 3.7+ will read confidence; Phase 3 falls
    back to ``proceed_default`` so the slot is wired but inert.
  * ``skip`` — return :attr:`WaitOutcome.TIMED_OUT_SKIP`; the loop logs an
    ``ErrorObservation`` and moves on.

If ``notify_on_proceed`` is set, every timeout self-decision (proceed or
skip) is announced via a follow-up ``informational`` message so the user
sees what happened the next time they look.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from taskweavn.interaction.autonomy import AutonomyBehavior
from taskweavn.interaction.bus import MessageBus
from taskweavn.interaction.message import (
    AgentMessage,
    ResponseSource,
)

# ---------------------------------------------------------------------------
# Outcome types
# ---------------------------------------------------------------------------


class WaitOutcome(Enum):
    """How the wait resolved — one of four shapes the AgentLoop must handle."""

    GOT_RESPONSE = "got_response"
    """User (or another agent) replied within the timeout."""

    TIMED_OUT_PROCEED = "timed_out_proceed"
    """No reply; ``timeout_action`` is one of the proceed variants. The
    original action should still run, using the default-or-confident
    selection as the synthesized response."""

    TIMED_OUT_SKIP = "timed_out_skip"
    """No reply; ``timeout_action="skip"``. The loop should log an error and
    move on instead of running the action."""

    PENDING = "pending"
    """``wait_strategy="async"`` — the response will be folded back later
    via ``drain_pending_responses``. The action MUST NOT run yet."""


@dataclass(frozen=True)
class WaitResult:
    """Concrete wait outcome — picked apart by the AgentLoop.

    ``response`` is the persisted reply when present (genuine reply or the
    synthetic informational the coordinator publishes on timeout). For
    PENDING it is ``None`` because nothing has resolved yet.

    ``response_value`` and ``response_source`` are the *effective* answer
    the loop should treat as canonical — for GOT_RESPONSE they come from
    the user; for TIMED_OUT_PROCEED they come from the synthesized default.
    """

    outcome: WaitOutcome
    response_value: str | None
    response_source: ResponseSource | None
    response: AgentMessage | None = None
    notice: AgentMessage | None = None
    """The ``informational`` the coordinator emitted to announce a self-
    decision, if any. ``None`` when no notice was published."""


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class WaitCoordinator:
    """Glue between the bus's primitives and the autonomy contract."""

    def __init__(self, bus: MessageBus, behavior: AutonomyBehavior) -> None:
        self._bus = bus
        self._behavior = behavior

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_actionable(self, message: AgentMessage) -> WaitResult:
        """Wait (or don't) on ``message``; return what to do next.

        ``message`` must already have been published — this method does NOT
        publish it. Splitting publish from wait keeps the AgentLoop in
        control of "the actionable becomes visible to the user", a moment
        the loop sometimes wants to log around.
        """
        if message.message_type != "actionable":
            raise ValueError(
                f"WaitCoordinator only handles actionable messages; "
                f"got {message.message_type!r}"
            )

        if self._behavior.wait_strategy == "async":
            return WaitResult(
                outcome=WaitOutcome.PENDING,
                response_value=None,
                response_source=None,
            )

        # Sync path: per-message timeout overrides the behavior default.
        timeout = (
            message.timeout_seconds
            if message.timeout_seconds is not None
            else self._behavior.wait_timeout
        )
        response = self._bus.wait_for_response(
            message.message_id, timeout=timeout
        )
        if response is not None:
            return WaitResult(
                outcome=WaitOutcome.GOT_RESPONSE,
                response_value=response.response_value,
                response_source=response.response_source,
                response=response,
            )

        # Timeout — branch on ``timeout_action``.
        return self._on_timeout(message)

    # ------------------------------------------------------------------
    # Timeout dispatch
    # ------------------------------------------------------------------

    def _on_timeout(self, message: AgentMessage) -> WaitResult:
        action = self._behavior.timeout_action

        if action == "wait":
            # User said "no clock; keep going indefinitely". Re-enter the
            # bus wait with no timeout. If THAT returns None, the bus is
            # closing — surface as TIMED_OUT_SKIP so the loop stops cleanly.
            response = self._bus.wait_for_response(
                message.message_id, timeout=None
            )
            if response is not None:
                return WaitResult(
                    outcome=WaitOutcome.GOT_RESPONSE,
                    response_value=response.response_value,
                    response_source=response.response_source,
                    response=response,
                )
            # Bus closed mid-wait; treat as skip and let the loop unwind.
            return WaitResult(
                outcome=WaitOutcome.TIMED_OUT_SKIP,
                response_value=None,
                response_source="timeout_skip",
            )

        if action == "skip":
            notice = self._publish_notice(
                message,
                source="timeout_skip",
                value=None,
                summary="timed out; skipping action",
            )
            return WaitResult(
                outcome=WaitOutcome.TIMED_OUT_SKIP,
                response_value=None,
                response_source="timeout_skip",
                notice=notice,
            )

        # proceed_default / proceed_confident.
        # Phase 3 collapses both to "first option" until a ConfidenceProvider
        # is wired up — the difference becomes meaningful in 3.7+.
        source: ResponseSource = (
            "timeout_confident" if action == "proceed_confident"
            else "timeout_default"
        )
        chosen = message.action_options[0] if message.action_options else None
        chosen_label = repr(chosen) if chosen is not None else "no option"
        notice = self._publish_notice(
            message,
            source=source,
            value=chosen,
            summary=f"timed out; proceeding with {source} ({chosen_label})",
        )
        return WaitResult(
            outcome=WaitOutcome.TIMED_OUT_PROCEED,
            response_value=chosen,
            response_source=source,
            notice=notice,
        )

    # ------------------------------------------------------------------
    # Notice emission
    # ------------------------------------------------------------------

    def _publish_notice(
        self,
        actionable: AgentMessage,
        *,
        source: ResponseSource,
        value: str | None,
        summary: str,
    ) -> AgentMessage | None:
        """Emit an informational explaining a timeout self-decision.

        Returns the published message (so tests can inspect it) or ``None``
        if ``notify_on_proceed`` is off. The notice is *informational*, not
        a response — the audit trail still shows the original actionable as
        unanswered, which is what the design wants (see Q2).
        """
        if not self._behavior.notify_on_proceed:
            return None
        notice = AgentMessage(
            session_id=actionable.session_id,
            task_id=actionable.task_id,
            agent_id="system",
            parent_message_id=actionable.message_id,
            message_type="informational",
            content=summary,
            context={
                "auto_decision": source,
                "selected_value": value,
                "original_message_id": actionable.message_id,
            },
        )
        self._bus.publish(notice)
        return notice
