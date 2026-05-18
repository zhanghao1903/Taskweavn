"""Tests for SQLite-backed publish control-plane stores."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from taskweavn.task import (
    DefaultTaskPublisher,
    InMemoryTaskBus,
    NormalizedTaskNode,
    NormalizedTaskTree,
    PublishAuditEvent,
    PublisherRef,
    PublishIdempotencyConflictError,
    PublishIdempotencyRecord,
    PublishIdempotencyStore,
    PublishRequest,
    PublishResult,
    PublishSource,
    PublishStoreError,
    ScheduledPublishConfig,
    ScheduledPublishState,
    ScheduledPublishStore,
    ScheduleExpression,
    SchedulerPublisher,
    SessionSelector,
    SqlitePublishIdempotencyStore,
    SqliteScheduledPublishStore,
    SqliteTaskBus,
    SqliteTaskPublishAuditSink,
    TaskPublishAuditSink,
    TaskPublishService,
    build_sqlite_publish_service,
)


def test_sqlite_publish_store_protocol_conformance(tmp_path: Path) -> None:
    idempotency_store = SqlitePublishIdempotencyStore(tmp_path / "publish.sqlite")
    audit_sink = SqliteTaskPublishAuditSink(tmp_path / "publish.sqlite")
    scheduled_store = SqliteScheduledPublishStore(tmp_path / "publish.sqlite")
    try:
        assert isinstance(idempotency_store, PublishIdempotencyStore)
        assert isinstance(audit_sink, TaskPublishAuditSink)
        assert isinstance(scheduled_store, ScheduledPublishStore)
    finally:
        idempotency_store.close()
        audit_sink.close()
        scheduled_store.close()


def test_idempotency_record_round_trip(tmp_path: Path) -> None:
    store = SqlitePublishIdempotencyStore(tmp_path / "publish.sqlite")
    record = _record()
    try:
        stored = store.put(record)
        loaded = store.get("s1", "custom_tree", "key-1")

        assert stored == record
        assert loaded == record
    finally:
        store.close()


def test_idempotency_record_persists_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "publish.sqlite"
    first = SqlitePublishIdempotencyStore(db)
    try:
        first.put(_record())
    finally:
        first.close()

    second = SqlitePublishIdempotencyStore(db)
    try:
        loaded = second.get("s1", "custom_tree", "key-1")

        assert loaded is not None
        assert loaded.publish_result.request_id == "req-1"
        assert loaded.publish_result.root_task_ids == ("task-root",)
    finally:
        second.close()


def test_idempotency_same_key_same_hash_returns_existing_record(tmp_path: Path) -> None:
    store = SqlitePublishIdempotencyStore(tmp_path / "publish.sqlite")
    first = _record(request_id="req-1")
    replay = _record(request_id="req-2")
    try:
        stored = store.put(first)
        loaded = store.put(replay)

        assert stored == first
        assert loaded == first
        assert loaded.publish_result.request_id == "req-1"
    finally:
        store.close()


def test_idempotency_same_key_different_hash_raises_conflict(tmp_path: Path) -> None:
    store = SqlitePublishIdempotencyStore(tmp_path / "publish.sqlite")
    try:
        store.put(_record(request_hash="hash-1"))

        with pytest.raises(PublishIdempotencyConflictError):
            store.put(_record(request_hash="hash-2"))
    finally:
        store.close()


def test_idempotency_corrupt_payload_raises_store_error(tmp_path: Path) -> None:
    db = tmp_path / "publish.sqlite"
    store = SqlitePublishIdempotencyStore(db)
    try:
        store.put(_record())
        store._conn.execute(  # noqa: SLF001 - test intentionally corrupts durable payload.
            """
            UPDATE publish_idempotency_records
            SET publish_result_json = ?
            WHERE session_id = ? AND publisher_kind = ? AND idempotency_key = ?
            """,
            ("not-json", "s1", "custom_tree", "key-1"),
        )

        with pytest.raises(PublishStoreError, match="invalid publish idempotency record"):
            store.get("s1", "custom_tree", "key-1")
    finally:
        store.close()


def test_audit_event_round_trip_and_queries(tmp_path: Path) -> None:
    sink = SqliteTaskPublishAuditSink(tmp_path / "publish.sqlite")
    event = PublishAuditEvent(
        event_id="event-1",
        kind="task_publish.published",
        request_id="req-1",
        session_id="s1",
        publisher_kind="custom_tree",
        actor_id="user-1",
        idempotency_key="key-1",
        root_task_ids=("root",),
        published_task_ids=("root", "child"),
        metadata={"task_count": 2, "nested": {"source": "test"}},
    )
    other = event.model_copy(
        update={
            "event_id": "event-2",
            "request_id": "req-2",
            "idempotency_key": "key-2",
        }
    )
    try:
        sink.record(event)
        sink.record(other)

        assert sink.list_for_session("s1") == (event, other)
        assert sink.list_for_session("s1", limit=1) == (event,)
        assert sink.list_for_request("req-1") == (event,)
        assert sink.list_for_idempotency("s1", "custom_tree", "key-1") == (event,)
    finally:
        sink.close()


def test_audit_event_persists_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "publish.sqlite"
    first = SqliteTaskPublishAuditSink(db)
    event = PublishAuditEvent(
        event_id="event-1",
        kind="task_publish.rejected",
        request_id="req-1",
        session_id="s1",
        publisher_kind="api",
        reason="preview failed",
    )
    try:
        first.record(event)
    finally:
        first.close()

    second = SqliteTaskPublishAuditSink(db)
    try:
        assert second.list_for_session("s1") == (event,)
    finally:
        second.close()


def test_audit_duplicate_event_id_raises_store_error(tmp_path: Path) -> None:
    sink = SqliteTaskPublishAuditSink(tmp_path / "publish.sqlite")
    event = PublishAuditEvent(
        event_id="event-1",
        kind="task_publish.previewed",
        request_id="req-1",
        session_id="s1",
        publisher_kind="custom_tree",
    )
    try:
        sink.record(event)
        with pytest.raises(PublishStoreError, match="failed to record publish audit event"):
            sink.record(event)
    finally:
        sink.close()


def test_context_manager_closes_connections(tmp_path: Path) -> None:
    with SqlitePublishIdempotencyStore(tmp_path / "publish.sqlite") as store:
        store.put(_record())

    with pytest.raises(sqlite3.ProgrammingError):
        store.get("s1", "custom_tree", "key-1")


def test_publish_service_replays_after_sqlite_store_reopen(tmp_path: Path) -> None:
    db = tmp_path / "publish.sqlite"
    bus = InMemoryTaskBus()
    first_store = SqlitePublishIdempotencyStore(db)
    first_sink = SqliteTaskPublishAuditSink(db)
    try:
        first_service = TaskPublishService(
            publisher=DefaultTaskPublisher(task_bus=bus),
            idempotency_store=first_store,
            audit_sink=first_sink,
        )
        first_result = first_service.publish(_request(request_id="req-1"))
    finally:
        first_store.close()
        first_sink.close()

    second_store = SqlitePublishIdempotencyStore(db)
    second_sink = SqliteTaskPublishAuditSink(db)
    try:
        second_service = TaskPublishService(
            publisher=DefaultTaskPublisher(task_bus=bus),
            idempotency_store=second_store,
            audit_sink=second_sink,
        )
        replay = second_service.publish(_request(request_id="req-2"))

        assert replay == first_result
        assert len(bus.list_for_session("s1")) == 1
        assert [event.kind for event in second_sink.list_for_session("s1")] == [
            "task_publish.validated",
            "task_publish.published",
            "task_publish.idempotent_replayed",
        ]
    finally:
        second_store.close()
        second_sink.close()


def test_build_sqlite_publish_service_wires_idempotency_and_audit(
    tmp_path: Path,
) -> None:
    publish_db = tmp_path / "publish.sqlite"
    bus = InMemoryTaskBus()
    service = build_sqlite_publish_service(
        task_bus=bus,
        publish_db_path=publish_db,
        publisher=_publisher(),
    )

    first = service.publish(_request(request_id="req-1"))
    replay = service.publish(_request(request_id="req-2"))

    audit_sink = SqliteTaskPublishAuditSink(publish_db)
    try:
        assert replay == first
        assert len(bus.list_for_session("s1")) == 1
        assert [event.kind for event in audit_sink.list_for_session("s1")] == [
            "task_publish.validated",
            "task_publish.published",
            "task_publish.idempotent_replayed",
        ]
    finally:
        audit_sink.close()


def test_sqlite_publish_service_recovers_existing_tasks_without_idempotency_record(
    tmp_path: Path,
) -> None:
    task_db = tmp_path / "tasks.sqlite"
    publish_db = tmp_path / "publish.sqlite"
    first_bus = SqliteTaskBus(task_db)
    try:
        DefaultTaskPublisher(task_bus=first_bus).publish(_request(request_id="req-1"))
    finally:
        first_bus.close()

    second_bus = SqliteTaskBus(task_db)
    try:
        service = build_sqlite_publish_service(
            task_bus=second_bus,
            publish_db_path=publish_db,
            publisher=_publisher(),
        )
        recovered = service.publish(_request(request_id="req-2"))

        assert recovered.accepted
        assert recovered.metadata["idempotent_existing_tasks"] is True
        assert len(second_bus.list_for_session("s1")) == 1
    finally:
        second_bus.close()

    idempotency_store = SqlitePublishIdempotencyStore(publish_db)
    try:
        record = idempotency_store.get("s1", "custom_tree", "key-1")
        assert record is not None
        assert record.publish_result.metadata["idempotent_existing_tasks"] is True
    finally:
        idempotency_store.close()


def test_scheduled_config_and_default_state_round_trip(tmp_path: Path) -> None:
    store = SqliteScheduledPublishStore(tmp_path / "publish.sqlite")
    config = _schedule_config()
    try:
        stored = store.upsert_config(config)
        loaded = store.get_config("daily-summary")
        state = store.get_state("daily-summary")

        assert stored == config
        assert loaded == config
        assert store.list_configs() == (config,)
        assert state is not None
        assert state.schedule_id == "daily-summary"
        assert state.enabled is True
        assert state.last_run_at is None
        assert state.next_run_at is None
    finally:
        store.close()


def test_scheduled_config_and_state_persist_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "publish.sqlite"
    first = SqliteScheduledPublishStore(db)
    run_at = _dt(2026, 5, 17, 9)
    next_run_at = run_at + timedelta(hours=1)
    try:
        first.upsert_config(_schedule_config())
        saved = first.save_state(
            ScheduledPublishState(
                schedule_id="daily-summary",
                last_run_at=run_at,
                next_run_at=next_run_at,
                last_result=_publish_result(),
            )
        )
    finally:
        first.close()

    second = SqliteScheduledPublishStore(db)
    try:
        assert second.get_config("daily-summary") == _schedule_config()
        assert second.get_state("daily-summary") == saved
    finally:
        second.close()


def test_scheduled_list_configs_is_sorted(tmp_path: Path) -> None:
    store = SqliteScheduledPublishStore(tmp_path / "publish.sqlite")
    try:
        store.upsert_config(_schedule_config(schedule_id="b"))
        store.upsert_config(_schedule_config(schedule_id="a"))

        assert [config.schedule_id for config in store.list_configs()] == ["a", "b"]
    finally:
        store.close()


def test_scheduled_set_enabled_updates_config_and_state(tmp_path: Path) -> None:
    store = SqliteScheduledPublishStore(tmp_path / "publish.sqlite")
    try:
        store.upsert_config(_schedule_config())
        updated = store.set_enabled("daily-summary", False)
        loaded = store.get_config("daily-summary")
        state = store.get_state("daily-summary")

        assert not updated.enabled
        assert loaded is not None
        assert not loaded.enabled
        assert state is not None
        assert not state.enabled
    finally:
        store.close()


def test_scheduled_save_state_requires_existing_config(tmp_path: Path) -> None:
    store = SqliteScheduledPublishStore(tmp_path / "publish.sqlite")
    try:
        with pytest.raises(LookupError, match="ScheduledPublishConfig 'missing' not found"):
            store.save_state(ScheduledPublishState(schedule_id="missing"))
    finally:
        store.close()


def test_scheduled_corrupt_config_raises_store_error(tmp_path: Path) -> None:
    store = SqliteScheduledPublishStore(tmp_path / "publish.sqlite")
    try:
        store.upsert_config(_schedule_config())
        store._conn.execute(  # noqa: SLF001 - test intentionally corrupts durable payload.
            """
            UPDATE scheduled_publish_configs
            SET config_json = ?
            WHERE schedule_id = ?
            """,
            ("not-json", "daily-summary"),
        )

        with pytest.raises(PublishStoreError, match="invalid scheduled publish config"):
            store.get_config("daily-summary")
    finally:
        store.close()


def test_scheduler_uses_persisted_next_run_after_reopen(tmp_path: Path) -> None:
    db = tmp_path / "publish.sqlite"
    now = _dt(2026, 5, 17, 9)
    bus = InMemoryTaskBus()
    first_store = SqliteScheduledPublishStore(db)
    first_idempotency = SqlitePublishIdempotencyStore(db)
    try:
        first_store.upsert_config(_schedule_config())
        first_scheduler = _scheduler(
            bus=bus,
            scheduled_store=first_store,
            idempotency_store=first_idempotency,
        )
        first = first_scheduler.tick(now=now)[0]

        assert first.published
        assert first.next_run_at == now + timedelta(hours=1)
        assert len(bus.list_for_session("s1")) == 1
    finally:
        first_store.close()
        first_idempotency.close()

    second_store = SqliteScheduledPublishStore(db)
    second_idempotency = SqlitePublishIdempotencyStore(db)
    try:
        second_scheduler = _scheduler(
            bus=bus,
            scheduled_store=second_store,
            idempotency_store=second_idempotency,
        )
        second = second_scheduler.tick(now=now)[0]

        assert not second.due
        assert second.reason == "not due"
        assert second.next_run_at == now + timedelta(hours=1)
        assert len(bus.list_for_session("s1")) == 1
    finally:
        second_store.close()
        second_idempotency.close()


def _record(
    *,
    request_id: str = "req-1",
    request_hash: str = "hash-1",
) -> PublishIdempotencyRecord:
    return PublishIdempotencyRecord(
        session_id="s1",
        publisher_kind="custom_tree",
        idempotency_key="key-1",
        request_hash=request_hash,
        publish_result=PublishResult(
            request_id=request_id,
            session_id="s1",
            publisher=_publisher(),
            published_task_ids=("task-root", "task-child"),
            root_task_ids=("task-root",),
            idempotency_key="key-1",
            metadata={"node_task_ids": {"root": "task-root"}},
        ),
    )


def _request(*, request_id: str) -> PublishRequest:
    publisher = _publisher()
    tree = NormalizedTaskTree(
        root_nodes=(
            NormalizedTaskNode(
                node_id="root",
                title="Root",
                intent="Do root",
                required_capability="general",
            ),
        ),
        source=publisher,
        source_ref="custom-tree-1",
    )
    return PublishRequest(
        request_id=request_id,
        session_id="s1",
        publisher=publisher,
        source=PublishSource(source_type="custom_tree", source_id="custom-tree-1"),
        task_tree=tree,
        idempotency_key="key-1",
    )


def _publisher() -> PublisherRef:
    return PublisherRef(kind="custom_tree", actor_id="user-1")


def _schedule_config(*, schedule_id: str = "daily-summary") -> ScheduledPublishConfig:
    return ScheduledPublishConfig(
        id=schedule_id,
        schedule=ScheduleExpression(type="interval", every_seconds=3600),
        session_selector=SessionSelector(mode="fixed", session_id="s1"),
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
        timezone="UTC",
    )


def _scheduler(
    *,
    bus: InMemoryTaskBus,
    scheduled_store: SqliteScheduledPublishStore,
    idempotency_store: SqlitePublishIdempotencyStore,
) -> SchedulerPublisher:
    service = TaskPublishService(
        publisher=DefaultTaskPublisher(task_bus=bus),
        idempotency_store=idempotency_store,
    )
    return SchedulerPublisher(store=scheduled_store, publish_service=service)


def _publish_result() -> PublishResult:
    return PublishResult(
        request_id="req-scheduled",
        session_id="s1",
        publisher=PublisherRef(kind="scheduler", name="daily-summary"),
        published_task_ids=("task-root",),
        root_task_ids=("task-root",),
        idempotency_key="schedule:daily-summary:s1:2026-05-17T09:00:00+00:00",
    )


def _dt(year: int, month: int, day: int, hour: int) -> datetime:
    return datetime(year, month, day, hour, 0, tzinfo=UTC)
