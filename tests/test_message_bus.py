"""Tests for InProcessMessageBus (Phase 3.4).

Bus contract under test:

* publish persists, then notifies waiters and matching subscribers (in that
  order, under one lock — predicates re-check SQLite, not memory caches);
* wait_for_response returns the persisted response, ``None`` on timeout, and
  is robust to spurious wake (we don't simulate that directly, but the loop
  shape is exercised by the predicate-check-after-each-wait path);
* subscribe filters by session and optional types, blocks the iterator on
  empty, and unblocks on close;
* concurrent publishers from N threads lose no rows.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from code_agent.interaction import (
    AgentMessage,
    InProcessMessageBus,
    MessageBus,
    MessageStreamError,
    SqliteMessageStream,
    Subscription,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _msg(session_id: str = "s", **kwargs: object) -> AgentMessage:
    return AgentMessage(  # type: ignore[arg-type]
        session_id=session_id,
        message_type=kwargs.pop("message_type", "informational"),  # type: ignore[arg-type]
        content=kwargs.pop("content", "x"),  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


@pytest.fixture
def bus(tmp_path: Path) -> InProcessMessageBus:
    stream = SqliteMessageStream(tmp_path / "messages.sqlite")
    bus_ = InProcessMessageBus(stream)
    yield bus_
    bus_.close()
    stream.close()


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_protocol_conformance(bus: InProcessMessageBus) -> None:
    assert isinstance(bus, MessageBus)
    sub = bus.subscribe("s")
    try:
        assert isinstance(sub, Subscription)
    finally:
        sub.close()


def test_publish_persists_to_stream(bus: InProcessMessageBus) -> None:
    m = _msg(session_id="sess", content="hello")
    bus.publish(m)
    got = bus.stream.get(m.message_id)
    assert got is not None
    assert got.content == "hello"


def test_publish_propagates_stream_errors(bus: InProcessMessageBus) -> None:
    """Duplicate message_id should surface as MessageStreamError, not a leaked
    sqlite3.IntegrityError."""
    m = _msg()
    bus.publish(m)
    with pytest.raises(MessageStreamError):
        bus.publish(m)


def test_publish_after_close_raises(bus: InProcessMessageBus) -> None:
    bus.close()
    with pytest.raises(MessageStreamError):
        bus.publish(_msg())


def test_close_is_idempotent(bus: InProcessMessageBus) -> None:
    bus.close()
    bus.close()


# ---------------------------------------------------------------------------
# wait_for_response
# ---------------------------------------------------------------------------


def test_wait_for_response_returns_persisted_response(
    bus: InProcessMessageBus,
) -> None:
    parent = _msg(message_type="actionable", content="ok?", requires_response=True)
    bus.publish(parent)

    def reply() -> None:
        time.sleep(0.05)
        bus.publish(
            AgentMessage(
                session_id="s",
                message_type="response",
                content="yes",
                parent_message_id=parent.message_id,
                response_source="user",
                response_value="yes",
            )
        )

    t = threading.Thread(target=reply)
    t.start()
    try:
        got = bus.wait_for_response(parent.message_id, timeout=2.0)
    finally:
        t.join()
    assert got is not None
    assert got.response_value == "yes"
    assert got.parent_message_id == parent.message_id


def test_wait_for_response_returns_none_on_timeout(bus: InProcessMessageBus) -> None:
    parent = _msg(message_type="actionable", content="ok?", requires_response=True)
    bus.publish(parent)
    start = time.monotonic()
    got = bus.wait_for_response(parent.message_id, timeout=0.1)
    elapsed = time.monotonic() - start
    assert got is None
    # Must actually have waited — sub-millisecond returns mean we burned the
    # predicate without honoring the timeout.
    assert elapsed >= 0.05


def test_wait_for_response_zero_timeout_is_non_blocking(
    bus: InProcessMessageBus,
) -> None:
    parent = _msg(message_type="actionable", content="?", requires_response=True)
    bus.publish(parent)
    # Already-recorded response → returns immediately without parking.
    bus.publish(
        AgentMessage(
            session_id="s",
            message_type="response",
            content="ok",
            parent_message_id=parent.message_id,
            response_source="user",
            response_value="ok",
        )
    )
    start = time.monotonic()
    got = bus.wait_for_response(parent.message_id, timeout=0.0)
    assert got is not None
    assert (time.monotonic() - start) < 0.05


def test_wait_for_response_no_response_timeout_zero(
    bus: InProcessMessageBus,
) -> None:
    parent = _msg(message_type="actionable", content="?", requires_response=True)
    bus.publish(parent)
    assert bus.wait_for_response(parent.message_id, timeout=0.0) is None


def test_wait_for_response_negative_timeout_rejected(
    bus: InProcessMessageBus,
) -> None:
    with pytest.raises(ValueError):
        bus.wait_for_response("nope", timeout=-1.0)


def test_wait_for_response_unblocks_on_close(bus: InProcessMessageBus) -> None:
    """Closing the bus while a thread waits returns ``None`` instead of
    deadlocking — important for clean shutdown."""
    parent = _msg(message_type="actionable", content="?", requires_response=True)
    bus.publish(parent)

    result: list[AgentMessage | None] = []

    def waiter() -> None:
        result.append(bus.wait_for_response(parent.message_id, timeout=None))

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.05)
    bus.close()
    t.join(timeout=2.0)
    assert not t.is_alive()
    assert result == [None]


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


def test_subscribe_filters_by_session(bus: InProcessMessageBus) -> None:
    seen: list[str] = []

    def reader() -> None:
        with bus.subscribe("sess1") as sub:
            for m in sub:
                seen.append(m.content)
                if m.content == "stop":
                    return

    t = threading.Thread(target=reader)
    t.start()
    time.sleep(0.05)  # let the reader park on __next__
    bus.publish(_msg(session_id="other", content="ignored"))
    bus.publish(_msg(session_id="sess1", content="kept"))
    bus.publish(_msg(session_id="sess1", content="stop"))
    t.join(timeout=2.0)
    assert seen == ["kept", "stop"]


def test_subscribe_filters_by_type(bus: InProcessMessageBus) -> None:
    seen: list[str] = []

    def reader() -> None:
        with bus.subscribe("s", types=["actionable"]) as sub:
            for m in sub:
                seen.append(m.message_type)
                if len(seen) == 2:
                    return

    t = threading.Thread(target=reader)
    t.start()
    time.sleep(0.05)
    bus.publish(_msg(message_type="informational", content="info"))
    bus.publish(_msg(message_type="actionable", content="a1", requires_response=True))
    bus.publish(_msg(message_type="informational", content="more info"))
    bus.publish(_msg(message_type="actionable", content="a2", requires_response=True))
    t.join(timeout=2.0)
    assert seen == ["actionable", "actionable"]


def test_subscribe_does_not_replay_old_messages(bus: InProcessMessageBus) -> None:
    """Subscriptions are *future-only*. Use stream.list_for_session() for replay.

    This is the spelled-out contract in the design doc — publishing-before-
    subscribe must NOT show up.
    """
    bus.publish(_msg(content="before"))
    with bus.subscribe("s") as sub:
        bus.publish(_msg(content="after"))
        m = next(iter(sub))
        assert m.content == "after"


def test_subscribe_close_unblocks_iterator(bus: InProcessMessageBus) -> None:
    sub = bus.subscribe("s")
    seen: list[AgentMessage] = []

    def reader() -> None:
        for m in sub:
            seen.append(m)

    t = threading.Thread(target=reader)
    t.start()
    time.sleep(0.05)
    sub.close()
    t.join(timeout=2.0)
    assert not t.is_alive()
    assert seen == []


def test_subscribe_after_close_raises(bus: InProcessMessageBus) -> None:
    bus.close()
    with pytest.raises(MessageStreamError):
        bus.subscribe("s")


def test_close_unblocks_active_subscribers(bus: InProcessMessageBus) -> None:
    sub = bus.subscribe("s")

    def reader() -> None:
        list(sub)

    t = threading.Thread(target=reader)
    t.start()
    time.sleep(0.05)
    bus.close()
    t.join(timeout=2.0)
    assert not t.is_alive()


def test_subscribe_is_unregistered_on_close(bus: InProcessMessageBus) -> None:
    sub = bus.subscribe("s")
    assert len(bus._subs) == 1  # noqa: SLF001 — internal invariant under test
    sub.close()
    assert bus._subs == []  # noqa: SLF001


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


def test_concurrent_publish_no_lost_messages(bus: InProcessMessageBus) -> None:
    """N producers, single subscriber — every publish must be visible."""
    n_threads = 4
    per_thread = 25
    expected = n_threads * per_thread
    seen: list[str] = []
    done = threading.Event()

    def reader() -> None:
        with bus.subscribe("s") as sub:
            for m in sub:
                seen.append(m.content)
                if len(seen) >= expected:
                    done.set()
                    return

    reader_thread = threading.Thread(target=reader)
    reader_thread.start()
    time.sleep(0.05)  # ensure reader is parked before producers start

    def producer(tid: int) -> None:
        for i in range(per_thread):
            bus.publish(_msg(content=f"t{tid}-{i}"))

    producers = [threading.Thread(target=producer, args=(i,)) for i in range(n_threads)]
    for p in producers:
        p.start()
    for p in producers:
        p.join()
    assert done.wait(timeout=5.0), f"only saw {len(seen)} of {expected}"
    reader_thread.join(timeout=2.0)
    assert len(seen) == expected
    assert len(set(seen)) == expected  # no duplicates either


def test_concurrent_waiters_each_resolved(bus: InProcessMessageBus) -> None:
    """Two threads wait on the same actionable; one response wakes both."""
    parent = _msg(message_type="actionable", content="?", requires_response=True)
    bus.publish(parent)

    results: list[AgentMessage | None] = []
    lock = threading.Lock()

    def waiter() -> None:
        r = bus.wait_for_response(parent.message_id, timeout=2.0)
        with lock:
            results.append(r)

    waiters = [threading.Thread(target=waiter) for _ in range(2)]
    for w in waiters:
        w.start()
    time.sleep(0.05)

    bus.publish(
        AgentMessage(
            session_id="s",
            message_type="response",
            content="ok",
            parent_message_id=parent.message_id,
            response_source="user",
            response_value="ok",
        )
    )

    for w in waiters:
        w.join(timeout=2.0)
    assert len(results) == 2
    assert all(r is not None and r.response_value == "ok" for r in results)
