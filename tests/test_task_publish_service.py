"""Tests for TaskPublishService idempotency and audit hooks."""

from __future__ import annotations

import pytest

from taskweavn.task import (
    DefaultTaskPublisher,
    InMemoryPublishIdempotencyStore,
    InMemoryTaskBus,
    InMemoryTaskPublishAuditSink,
    NormalizedTaskNode,
    NormalizedTaskTree,
    PublisherRef,
    PublishIdempotencyConflictError,
    PublishIdempotencyRecord,
    PublishIdempotencyStore,
    PublishRequest,
    PublishResult,
    PublishSource,
    TaskPublishAuditSink,
    TaskPublishService,
)


def test_idempotency_store_and_audit_sink_protocol_conformance() -> None:
    store = InMemoryPublishIdempotencyStore()
    sink = InMemoryTaskPublishAuditSink()

    assert isinstance(store, PublishIdempotencyStore)
    assert isinstance(sink, TaskPublishAuditSink)


def test_preview_delegates_without_writing_task_bus() -> None:
    bus = InMemoryTaskBus()
    sink = InMemoryTaskPublishAuditSink()
    service = TaskPublishService(
        publisher=DefaultTaskPublisher(task_bus=bus),
        audit_sink=sink,
    )

    preview = service.preview(_request())

    assert preview.ok
    assert preview.task_count == 1
    assert bus.list_for_session("s1") == []
    assert sink.list()[0].kind == "task_publish.previewed"


def test_publish_writes_tasks_and_preserves_publish_metadata() -> None:
    bus = InMemoryTaskBus()
    service = TaskPublishService(publisher=DefaultTaskPublisher(task_bus=bus))
    request = _request(idempotency_key="publish-1", source_metadata={"api_key": "test"})

    result = service.publish(request)
    task = bus.list_for_session("s1")[0]

    assert result.accepted
    assert task.dispatch_constraints is not None
    assert task.dispatch_constraints.metadata["publish_request_id"] == request.request_id
    assert task.dispatch_constraints.metadata["publish_idempotency_key"] == "publish-1"
    assert task.dispatch_constraints.metadata["publisher_kind"] == "custom_tree"
    assert task.dispatch_constraints.metadata["source_metadata"] == {"api_key": "test"}


def test_idempotent_replay_same_key_same_payload_returns_original_result() -> None:
    bus = InMemoryTaskBus()
    sink = InMemoryTaskPublishAuditSink()
    service = TaskPublishService(
        publisher=DefaultTaskPublisher(task_bus=bus),
        audit_sink=sink,
    )
    first = _request(request_id="req-1", idempotency_key="same-key")
    replay = _request(request_id="req-2", idempotency_key="same-key")

    first_result = service.publish(first)
    replay_result = service.publish(replay)

    assert replay_result == first_result
    assert len(bus.list_for_session("s1")) == 1
    assert [event.kind for event in sink.list()] == [
        "task_publish.validated",
        "task_publish.published",
        "task_publish.idempotent_replayed",
    ]


def test_idempotency_conflict_same_key_different_payload_does_not_publish() -> None:
    bus = InMemoryTaskBus()
    sink = InMemoryTaskPublishAuditSink()
    service = TaskPublishService(
        publisher=DefaultTaskPublisher(task_bus=bus),
        audit_sink=sink,
    )

    first_result = service.publish(_request(idempotency_key="same-key"))
    conflict = service.publish(
        _request(
            request_id="req-2",
            idempotency_key="same-key",
            intent="Do a different thing",
        )
    )

    assert first_result.accepted
    assert conflict.skipped
    assert conflict.reason == "idempotency conflict"
    assert len(bus.list_for_session("s1")) == 1
    assert sink.list()[-1].kind == "task_publish.idempotency_conflict"


def test_publish_without_idempotency_key_allows_repeated_publish() -> None:
    bus = InMemoryTaskBus()
    service = TaskPublishService(publisher=DefaultTaskPublisher(task_bus=bus))

    first = service.publish(_request(request_id="req-1", idempotency_key=None))
    second = service.publish(_request(request_id="req-2", idempotency_key=None))

    assert first.accepted
    assert second.accepted
    assert len(bus.list_for_session("s1")) == 2


def test_publish_rejects_invalid_preview_and_records_audit() -> None:
    bus = InMemoryTaskBus()
    sink = InMemoryTaskPublishAuditSink()
    service = TaskPublishService(
        publisher=DefaultTaskPublisher(task_bus=bus),
        audit_sink=sink,
    )
    request = PublishRequest(
        session_id="s1",
        publisher=_publisher(),
        source=PublishSource(source_type="natural_language"),
        natural_language_input="please do something",
        idempotency_key="nl-1",
    )

    result = service.publish(request)

    assert result.skipped
    assert "natural-language publish requires authoring" in (result.reason or "")
    assert bus.list_for_session("s1") == []
    assert sink.list()[0].kind == "task_publish.rejected"


def test_idempotency_store_rejects_conflicting_record() -> None:
    store = InMemoryPublishIdempotencyStore()
    record = PublishIdempotencyRecord(
        session_id="s1",
        publisher_kind="custom_tree",
        idempotency_key="key",
        request_hash="hash-1",
        publish_result=PublishResult(
            request_id="req-1",
            session_id="s1",
            publisher=_publisher(),
        ),
    )

    stored = store.put(record)

    assert stored == record
    with pytest.raises(PublishIdempotencyConflictError):
        store.put(record.model_copy(update={"request_hash": "hash-2"}))


def test_audit_sink_failure_does_not_block_publish() -> None:
    bus = InMemoryTaskBus()
    service = TaskPublishService(
        publisher=DefaultTaskPublisher(task_bus=bus),
        audit_sink=_BrokenAuditSink(),
    )

    result = service.publish(_request())

    assert result.accepted
    assert len(bus.list_for_session("s1")) == 1


class _BrokenAuditSink:
    def record(self, event: object) -> None:  # noqa: ARG002
        raise RuntimeError("audit sink failed")


def _request(
    *,
    request_id: str = "req-1",
    idempotency_key: str | None = "publish-1",
    intent: str = "Do root",
    source_metadata: dict[str, object] | None = None,
) -> PublishRequest:
    publisher = _publisher()
    tree = NormalizedTaskTree(
        root_nodes=(
            NormalizedTaskNode(
                node_id="root",
                title="Root",
                intent=intent,
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
        source=PublishSource(
            source_type="custom_tree",
            source_id="custom-tree-1",
            metadata=dict(source_metadata or {}),
        ),
        task_tree=tree,
        idempotency_key=idempotency_key,
    )


def _publisher() -> PublisherRef:
    return PublisherRef(kind="custom_tree", actor_id="user-1")
