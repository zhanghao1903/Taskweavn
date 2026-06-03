"""Derived ``Session.status`` (Phase 3.8).

The stored ``status`` column on ``sessions`` is a hint, not the truth. It
drifts whenever someone forgets to call :meth:`SessionManager.mark_status`,
and there's no good way to keep every code path honest. The truth is
already in two places we trust:

* the per-session :class:`EventStream` — it has the AgentFinishObservation
  the moment a task wraps up, and any new Action after that flips the
  "finished" signal off automatically;
* the workspace :class:`MessageStream` — its ``pending_actionable`` query
  is exactly the "an open confirmation/actionable interaction is parked,
  waiting for the user" signal.

So we *derive* the live status from those two inputs. The stored column
survives only to record ``archived`` — a deliberate user act with no
natural signal — and as a fallback when the derivation has nothing to
look at.

Rules, in order (first match wins):

1. stored ``archived`` → ``archived`` (user override beats derivation)
2. message stream has a pending actionable → ``awaiting_user``
3. last event on the stream is :class:`AgentFinishObservation` → ``finished``
4. otherwise → ``active``

Rule 3 is "*last* event", not "*any* event" — that's intentional. A session
that finished one task and is now mid-way through a second task should read
as ``active``, not ``finished``. Walking the stream once and keeping the
last item gives us that for free.

Cost: O(events) for rule 3 and O(open actionables) for rule 2. The first
dominates; if we ever need to optimise, the right move is a SQL
``MAX(timestamp) WHERE kind = 'agent_finish_observation'`` against the
session's events table — but that's a Phase 3+ concern. Today every
session's event count is small enough to walk in memory.
"""

from __future__ import annotations

from taskweavn.core.event_stream import EventStream
from taskweavn.core.session import Session, SessionStatus
from taskweavn.interaction.message import MessageStream
from taskweavn.types.common import AgentFinishObservation


def derive_session_status(
    session: Session,
    *,
    event_stream: EventStream,
    message_stream: MessageStream,
) -> SessionStatus:
    """Compute the live status of ``session`` from its observable inputs.

    The stored ``session.status`` is consulted only for the ``archived``
    override; every other state is derived. See module docstring for the
    rule table.

    Args:
        session: The session metadata (used for id + stored status).
        event_stream: The per-session event stream. Must already be scoped
            to ``session`` — the layout gives each session its own SQLite
            file, so no further filtering is needed.
        message_stream: The workspace-wide message stream. Filtering on
            ``session.id`` happens inside the stream's queries.

    Returns:
        One of ``"active" | "awaiting_user" | "finished" | "archived"``.
    """
    # Rule 1 — archived is a sticky user override. Nothing on the streams
    # can flip a session out of archived; only an explicit unarchive call
    # (which we don't have yet) would.
    if session.status == "archived":
        return "archived"

    # Rule 2 — an open actionable means a user-facing confirmation/actionable
    # interaction is waiting for a reply. This wins over "finished" because a
    # finished task that asked one final question is, from the user's POV,
    # still waiting on them.
    if message_stream.pending_actionable(session.id):
        return "awaiting_user"

    # Rule 3 — finished iff the *last* event on the stream is the canonical
    # agent_finish observation. We iterate forward and remember the tail;
    # EventStream's Protocol doesn't promise reverse iteration, and the
    # forward walk is fine at our event scales.
    last_event = None
    for event in event_stream:
        last_event = event
    if isinstance(last_event, AgentFinishObservation):
        return "finished"

    # Rule 4 — default. Includes the "no events yet" case for a session
    # that was just created.
    return "active"


__all__ = ["derive_session_status"]
