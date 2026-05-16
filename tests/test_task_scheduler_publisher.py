"""Tests for scheduled Task publisher adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from taskweavn.task import (
    DefaultTaskPublisher,
    IdempotencyPolicy,
    InMemoryPublishIdempotencyStore,
    InMemoryScheduledPublishStore,
    InMemoryTaskBus,
    ScheduledPublishConfig,
    ScheduledPublishState,
    ScheduledPublishStore,
    ScheduleExpression,
    SchedulerPublisher,
    SessionSelector,
    TaskPublishService,
)


def test_scheduled_publish_store_protocol_conformance() -> None:
    store = InMemoryScheduledPublishStore([_config()])

    assert isinstance(store, ScheduledPublishStore)
    assert store.get_config("daily-summary") is not None


def test_interval_schedule_due_tick_publishes_task_and_updates_state() -> None:
    now = _dt(2026, 5, 16, 9)
    bus = InMemoryTaskBus()
    store = InMemoryScheduledPublishStore([_config()])
    scheduler = _scheduler(bus=bus, store=store)

    results = scheduler.tick(now=now)
    tasks = bus.list_for_session("s1")
    state = store.get_state("daily-summary")

    assert len(results) == 1
    assert results[0].due
    assert results[0].published
    assert results[0].next_run_at == now + timedelta(hours=1)
    assert len(tasks) == 1
    assert tasks[0].dispatch_constraints is not None
    assert tasks[0].dispatch_constraints.metadata["publisher_kind"] == "scheduler"
    assert tasks[0].dispatch_constraints.metadata["schedule_id"] == "daily-summary"
    assert state is not None
    assert state.last_run_at == now
    assert state.next_run_at == now + timedelta(hours=1)
    assert state.last_result is not None
    assert state.last_result.accepted


def test_repeated_tick_before_next_run_does_not_duplicate_publish() -> None:
    now = _dt(2026, 5, 16, 9)
    bus = InMemoryTaskBus()
    store = InMemoryScheduledPublishStore([_config()])
    scheduler = _scheduler(bus=bus, store=store)

    first = scheduler.tick(now=now)
    second = scheduler.tick(now=now)

    assert first[0].published
    assert not second[0].due
    assert second[0].reason == "not due"
    assert len(bus.list_for_session("s1")) == 1


def test_next_interval_tick_publishes_again_with_distinct_idempotency_key() -> None:
    now = _dt(2026, 5, 16, 9)
    bus = InMemoryTaskBus()
    store = InMemoryScheduledPublishStore([_config()])
    scheduler = _scheduler(bus=bus, store=store)

    first = scheduler.tick(now=now)[0]
    second = scheduler.tick(now=now + timedelta(hours=1))[0]

    assert first.published
    assert second.published
    assert len(bus.list_for_session("s1")) == 2


def test_disabled_schedule_is_skipped_and_can_be_enabled() -> None:
    now = _dt(2026, 5, 16, 9)
    bus = InMemoryTaskBus()
    store = InMemoryScheduledPublishStore([_config(enabled=False)])
    scheduler = _scheduler(bus=bus, store=store)

    skipped = scheduler.tick(now=now)[0]
    store.set_enabled("daily-summary", True)
    published = scheduler.tick(now=now)[0]

    assert skipped.reason == "disabled"
    assert not skipped.due
    assert published.published
    assert len(bus.list_for_session("s1")) == 1


def test_current_session_selector_requires_current_session_id() -> None:
    config = _config(
        session_selector=SessionSelector(mode="current"),
    )
    bus = InMemoryTaskBus()
    store = InMemoryScheduledPublishStore([config])
    scheduler = _scheduler(bus=bus, store=store)

    missing = scheduler.tick(now=_dt(2026, 5, 16, 9))[0]
    published = scheduler.tick(now=_dt(2026, 5, 16, 9), current_session_id="current-s")[0]

    assert missing.reason == "current session selector requires current_session_id"
    assert published.published
    assert bus.list_for_session("current-s")


def test_daily_schedule_before_time_is_not_due() -> None:
    config = _config(
        schedule=ScheduleExpression(type="daily", time_of_day="18:30"),
        timezone="Asia/Shanghai",
    )
    bus = InMemoryTaskBus()
    store = InMemoryScheduledPublishStore([config])
    scheduler = _scheduler(bus=bus, store=store)

    result = scheduler.tick(now=datetime(2026, 5, 16, 9, 0, tzinfo=UTC))[0]

    assert not result.due
    assert result.reason == "not due"
    assert result.next_run_at == datetime(
        2026, 5, 16, 18, 30, tzinfo=ZoneInfo("Asia/Shanghai")
    )
    assert bus.list_for_session("s1") == []


def test_daily_schedule_after_time_publishes_and_sets_next_day() -> None:
    config = _config(
        schedule=ScheduleExpression(type="daily", time_of_day="08:00"),
        timezone="Asia/Shanghai",
    )
    bus = InMemoryTaskBus()
    store = InMemoryScheduledPublishStore([config])
    scheduler = _scheduler(bus=bus, store=store)

    result = scheduler.tick(now=datetime(2026, 5, 16, 9, 0, tzinfo=UTC))[0]

    assert result.published
    assert result.next_run_at == datetime(
        2026, 5, 17, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai")
    )
    assert len(bus.list_for_session("s1")) == 1


def test_cron_schedule_is_reserved_but_not_executed() -> None:
    config = _config(schedule=ScheduleExpression(type="cron", cron="0 8 * * *"))
    bus = InMemoryTaskBus()
    store = InMemoryScheduledPublishStore([config])
    scheduler = _scheduler(bus=bus, store=store)

    result = scheduler.tick(now=_dt(2026, 5, 16, 9))[0]

    assert not result.due
    assert result.reason == "unsupported schedule type"
    assert bus.list_for_session("s1") == []


def test_custom_idempotency_template_is_used() -> None:
    bus = InMemoryTaskBus()
    store = InMemoryScheduledPublishStore(
        [
            _config(
                idempotency_policy=IdempotencyPolicy(
                    key_template="nightly:{session_id}:{date}"
                )
            )
        ]
    )
    scheduler = _scheduler(bus=bus, store=store)

    result = scheduler.tick(now=_dt(2026, 5, 16, 9))[0]

    assert result.result is not None
    assert result.result.idempotency_key == "nightly:s1:2026-05-16"


def test_schedule_state_can_be_seeded_for_future_run() -> None:
    now = _dt(2026, 5, 16, 9)
    store = InMemoryScheduledPublishStore(
        [_config()],
        [ScheduledPublishState(schedule_id="daily-summary", next_run_at=now + timedelta(hours=2))],
    )
    bus = InMemoryTaskBus()
    scheduler = _scheduler(bus=bus, store=store)

    result = scheduler.tick(now=now)[0]

    assert not result.due
    assert result.next_run_at == now + timedelta(hours=2)
    assert bus.list_for_session("s1") == []


def test_invalid_fixed_session_selector_is_rejected() -> None:
    with pytest.raises(ValueError, match="fixed session selector requires session_id"):
        SessionSelector(mode="fixed")


def _scheduler(
    *,
    bus: InMemoryTaskBus,
    store: InMemoryScheduledPublishStore,
) -> SchedulerPublisher:
    service = TaskPublishService(
        publisher=DefaultTaskPublisher(task_bus=bus),
        idempotency_store=InMemoryPublishIdempotencyStore(),
    )
    return SchedulerPublisher(store=store, publish_service=service)


def _config(
    *,
    enabled: bool = True,
    schedule: ScheduleExpression | None = None,
    session_selector: SessionSelector | None = None,
    idempotency_policy: IdempotencyPolicy | None = None,
    timezone: str = "UTC",
) -> ScheduledPublishConfig:
    return ScheduledPublishConfig(
        id="daily-summary",
        enabled=enabled,
        schedule=schedule or ScheduleExpression(type="interval", every_seconds=3600),
        session_selector=session_selector or SessionSelector(mode="fixed", session_id="s1"),
        task_tree={
            "tasks": [
                {
                    "id": "summary",
                    "title": "Summary",
                    "intent": "Summarize current session",
                    "capability": "summarize",
                }
            ]
        },
        idempotency_policy=idempotency_policy or IdempotencyPolicy(),
        timezone=timezone,
    )


def _dt(year: int, month: int, day: int, hour: int) -> datetime:
    return datetime(year, month, day, hour, 0, tzinfo=UTC)
