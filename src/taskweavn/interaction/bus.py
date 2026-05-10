"""MessageBus — the single writer for the message stream (Phase 3.4).

The bus owns three responsibilities the read-only stream can't:

* **Write path** — every message in the system goes through ``publish()``.
  The stream's ``_insert`` is private; tests excluded, no other code path is
  permitted to add rows.
* **Wait primitive** — ``wait_for_response(message_id, timeout)`` blocks the
  current thread until either the matching response lands or the timeout
  fires. Callers (the AgentLoop, mostly) don't poll.
* **Subscriptions** — a CLI / UI thread iterates over a :class:`Subscription`
  to render messages live. Old messages persisted on disk are visible via
  the read stream; the subscription only delivers messages published *after*
  it was opened, so the UI can replay history first and then attach.

Everything is coordinated by one :class:`threading.Condition`. The contract
is "publish acquires the condition, persists, then notify_all" — so anyone
waiting on a predicate (response arrival or subscription queue non-empty)
re-checks under the lock and either consumes or goes back to sleep. No
busy-waiting.

Phase 3 is single-process, multi-threaded. The bus's
:class:`InProcessMessageBus` is the only implementation; cross-process
variants (poll-based ``SqliteMessageBus`` or a Redis-backed one) reuse the
same Protocol — see design doc §5.2.2.
"""

from __future__ import annotations

import contextlib
import threading
from collections import deque
from collections.abc import Iterable, Iterator
from typing import Any, Protocol, runtime_checkable

from taskweavn.interaction.message import (
    AgentMessage,
    MessageStream,
    MessageStreamError,
)
from taskweavn.interaction.sqlite_message_stream import SqliteMessageStream

# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class Subscription(Protocol):
    """A live, ordered, filtered view over future ``publish()`` calls.

    Iteration blocks until a matching message arrives or :meth:`close` is
    called. Use as a context manager to guarantee cleanup; the bus removes
    the subscription from its registry on exit.
    """

    def __iter__(self) -> Iterator[AgentMessage]: ...
    def __next__(self) -> AgentMessage: ...
    def close(self) -> None: ...
    def __enter__(self) -> Subscription: ...
    def __exit__(self, *exc_info: Any) -> None: ...


@runtime_checkable
class MessageBus(Protocol):
    """Single-writer, multi-reader, blocking-aware message channel."""

    def publish(self, message: AgentMessage) -> None: ...

    def subscribe(
        self,
        session_id: str,
        *,
        types: Iterable[str] | None = None,
    ) -> Subscription: ...

    def wait_for_response(
        self,
        message_id: str,
        timeout: float | None,
    ) -> AgentMessage | None: ...

    @property
    def stream(self) -> MessageStream: ...


# ---------------------------------------------------------------------------
# In-process implementation
# ---------------------------------------------------------------------------


class InProcessMessageBus:
    """Default Phase 3 bus — single SQLite file + ``threading.Condition``.

    Designed so any consumer can be replaced by a cross-process equivalent
    without touching producers: the same Protocol works for a polling
    SQLite-only bus or a Redis-backed pub/sub.
    """

    def __init__(self, stream: SqliteMessageStream) -> None:
        self._stream = stream
        # One condition coordinates publishers, response-waiters, and
        # subscription iterators. ``notify_all`` is the cheap, correct choice
        # at this scale: a handful of subscribers, predicates that check
        # cheaply against an in-memory deque or a one-row SQLite query.
        self._cond = threading.Condition()
        self._subs: list[_InProcessSubscription] = []
        self._closed = False

    # ------------------------------------------------------------------
    # MessageBus Protocol
    # ------------------------------------------------------------------

    def publish(self, message: AgentMessage) -> None:
        """Persist ``message`` and wake everyone waiting on the bus.

        The SQL INSERT happens inside the bus's condition lock so a waiter's
        predicate (which queries SQLite) is guaranteed to see the row before
        being notified. Any IntegrityError from the stream surfaces here.
        """
        with self._cond:
            if self._closed:
                raise MessageStreamError("bus is closed")
            # ``_insert`` re-acquires its own internal lock, but that lock is
            # private to the stream and never held while the bus's condition
            # is, so there is no inversion risk.
            self._stream._insert(message)  # noqa: SLF001 — bus owns the writer

            # Fan out to matching subscribers under the same lock so a brand-
            # new subscriber that started just after the insert and just
            # before notify_all isn't surprised by a missed message: it
            # simply wasn't subscribed yet, and the read-stream replay path
            # is what catches it up.
            for sub in self._subs:
                if sub._matches(message):  # noqa: SLF001
                    sub._enqueue(message)  # noqa: SLF001

            self._cond.notify_all()

    def wait_for_response(
        self,
        message_id: str,
        timeout: float | None,
    ) -> AgentMessage | None:
        """Block until ``message_id`` has a recorded response, or timeout.

        ``timeout=None`` means wait forever; ``timeout=0`` is a non-blocking
        check. Returns ``None`` if the timeout fires before a response lands.
        """
        if timeout is not None and timeout < 0:
            raise ValueError(f"timeout must be >= 0 or None; got {timeout}")

        deadline = None if timeout is None else _monotonic() + timeout

        with self._cond:
            while True:
                response = self._stream.response_for(message_id)
                if response is not None:
                    return response
                if self._closed:
                    return None
                if deadline is None:
                    self._cond.wait()
                    continue
                remaining = deadline - _monotonic()
                if remaining <= 0:
                    return None
                # ``wait`` may return spuriously; the loop re-checks the
                # SQL predicate so an early wake costs only one query.
                self._cond.wait(timeout=remaining)

    def subscribe(
        self,
        session_id: str,
        *,
        types: Iterable[str] | None = None,
    ) -> Subscription:
        """Open a live view of messages on ``session_id``.

        ``types`` filters by ``message_type`` — pass e.g. ``["actionable"]``
        to render only confirmation prompts. The subscription does not see
        messages published before it was opened; combine with
        ``stream.list_for_session(...)`` for replay-then-attach.
        """
        type_set = None if types is None else frozenset(types)
        sub = _InProcessSubscription(
            bus=self,
            session_id=session_id,
            types=type_set,
        )
        with self._cond:
            if self._closed:
                raise MessageStreamError("bus is closed")
            self._subs.append(sub)
        return sub

    @property
    def stream(self) -> MessageStream:
        """Read interface; tests and CLI replay paths use this."""
        return self._stream

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the bus. All subscriptions stop iterating, all
        ``wait_for_response`` calls return ``None``. Idempotent."""
        with self._cond:
            if self._closed:
                return
            self._closed = True
            # Closing each sub flips its own flag and pops it from the list;
            # iterate over a snapshot to avoid mutation-during-iteration.
            for sub in list(self._subs):
                sub._mark_closed()  # noqa: SLF001
            self._cond.notify_all()

    def __enter__(self) -> InProcessMessageBus:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Subscription bookkeeping (called from the subscription's own close)
    # ------------------------------------------------------------------

    def _unregister(self, sub: _InProcessSubscription) -> None:
        with self._cond:
            with contextlib.suppress(ValueError):
                self._subs.remove(sub)
            self._cond.notify_all()


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------


class _InProcessSubscription:
    """Live queue + filter for one consumer.

    Shares the bus's :class:`threading.Condition` so a single ``notify_all``
    in ``publish()`` wakes both response waiters and subscription iterators.
    The deque is unbounded — Phase 3 producers and consumers run at human
    speed, so backpressure isn't a concern. If that changes, swap in a
    bounded queue and add a drop policy.
    """

    def __init__(
        self,
        *,
        bus: InProcessMessageBus,
        session_id: str,
        types: frozenset[str] | None,
    ) -> None:
        self._bus = bus
        self._session_id = session_id
        self._types = types
        self._queue: deque[AgentMessage] = deque()
        self._closed = False

    # ------------------------------------------------------------------
    # Filter
    # ------------------------------------------------------------------

    def _matches(self, message: AgentMessage) -> bool:
        if message.session_id != self._session_id:
            return False
        return self._types is None or message.message_type in self._types

    def _enqueue(self, message: AgentMessage) -> None:
        # Caller already holds the bus's condition lock.
        self._queue.append(message)

    def _mark_closed(self) -> None:
        # Caller already holds the bus's condition lock.
        self._closed = True

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[AgentMessage]:
        return self

    def __next__(self) -> AgentMessage:
        with self._bus._cond:  # noqa: SLF001
            while not self._queue:
                if self._closed:
                    raise StopIteration
                self._bus._cond.wait()  # noqa: SLF001
            return self._queue.popleft()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Stop iterating; safe to call multiple times."""
        with self._bus._cond:  # noqa: SLF001
            if self._closed:
                return
            self._closed = True
            # Also wake the iterator if it's currently parked in __next__.
            self._bus._cond.notify_all()  # noqa: SLF001
        self._bus._unregister(self)

    def __enter__(self) -> _InProcessSubscription:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _monotonic() -> float:
    # Indirection so tests can monkeypatch a deterministic clock without
    # touching the real ``time`` module.
    import time

    return time.monotonic()
