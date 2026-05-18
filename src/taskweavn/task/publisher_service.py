"""Task publish service with idempotency and audit hooks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from contextlib import suppress
from datetime import UTC, datetime
from threading import RLock
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from taskweavn.task.pipeline import PipelineTaskLoader
from taskweavn.task.publisher import (
    PublisherKind,
    PublishPreview,
    PublishRequest,
    PublishResult,
    TaskPublisher,
)

PublishAuditEventKind = Literal[
    "task_publish.previewed",
    "task_publish.validated",
    "task_publish.rejected",
    "task_publish.published",
    "task_publish.idempotent_replayed",
    "task_publish.idempotency_conflict",
]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


class _FrozenServiceModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class PublishIdempotencyConflictError(RuntimeError):
    """Raised when an idempotency key is reused for a different request."""


class PublishIdempotencyRecord(_FrozenServiceModel):
    """Stable publish result stored behind one idempotency key."""

    session_id: str = Field(min_length=1)
    publisher_kind: PublisherKind
    idempotency_key: str = Field(min_length=1)
    request_hash: str = Field(min_length=1)
    publish_result: PublishResult
    created_at: datetime = Field(default_factory=_utcnow)

    @property
    def key(self) -> tuple[str, PublisherKind, str]:
        return (self.session_id, self.publisher_kind, self.idempotency_key)


@runtime_checkable
class PublishIdempotencyStore(Protocol):
    """Persistence boundary for publish idempotency records."""

    def get(
        self,
        session_id: str,
        publisher_kind: PublisherKind,
        idempotency_key: str,
    ) -> PublishIdempotencyRecord | None: ...

    def put(self, record: PublishIdempotencyRecord) -> PublishIdempotencyRecord: ...


class InMemoryPublishIdempotencyStore:
    """Thread-safe process-local idempotency store for early publishers/tests."""

    def __init__(self, records: Iterable[PublishIdempotencyRecord] = ()) -> None:
        self._lock = RLock()
        self._records: dict[tuple[str, PublisherKind, str], PublishIdempotencyRecord] = {}
        for record in records:
            self.put(record)

    def get(
        self,
        session_id: str,
        publisher_kind: PublisherKind,
        idempotency_key: str,
    ) -> PublishIdempotencyRecord | None:
        with self._lock:
            return self._records.get((session_id, publisher_kind, idempotency_key))

    def put(self, record: PublishIdempotencyRecord) -> PublishIdempotencyRecord:
        with self._lock:
            current = self._records.get(record.key)
            if current is None:
                self._records[record.key] = record
                return record
            if current.request_hash != record.request_hash:
                raise PublishIdempotencyConflictError(
                    "idempotency key was already used with a different request"
                )
            return current


class PublishAuditEvent(_FrozenServiceModel):
    """Service-level publish audit event.

    This is intentionally not an EventStream event yet. It is a small hook
    boundary that can later be adapted into EventStream, MessageStream, or
    observability sinks without making publisher code depend on those stores.
    """

    event_id: str = Field(default_factory=_new_id, min_length=1)
    kind: PublishAuditEventKind
    request_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    publisher_kind: PublisherKind
    actor_id: str | None = Field(default=None, min_length=1)
    idempotency_key: str | None = Field(default=None, min_length=1)
    root_task_ids: tuple[str, ...] = ()
    published_task_ids: tuple[str, ...] = ()
    reason: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)


@runtime_checkable
class TaskPublishAuditSink(Protocol):
    """Append-only sink for TaskPublishService audit facts."""

    def record(self, event: PublishAuditEvent) -> None: ...


class InMemoryTaskPublishAuditSink:
    """Small deterministic audit sink used by tests and first adapters."""

    def __init__(self, events: Iterable[PublishAuditEvent] = ()) -> None:
        self._lock = RLock()
        self._events = list(events)

    def record(self, event: PublishAuditEvent) -> None:
        with self._lock:
            self._events.append(event)

    def list(self) -> tuple[PublishAuditEvent, ...]:
        with self._lock:
            return tuple(self._events)


class TaskPublishService:
    """Coordinates preview/publish, idempotency, and audit hooks."""

    def __init__(
        self,
        *,
        publisher: TaskPublisher,
        idempotency_store: PublishIdempotencyStore | None = None,
        audit_sink: TaskPublishAuditSink | None = None,
        pipeline_loader: PipelineTaskLoader | None = None,
    ) -> None:
        self._publisher = publisher
        self._idempotency_store = idempotency_store or InMemoryPublishIdempotencyStore()
        self._audit_sink = audit_sink
        self._pipeline_loader = pipeline_loader

    def preview(self, request: PublishRequest) -> PublishPreview:
        effective_request = self._expand_pipeline_or_none(request)
        if effective_request is None:
            preview = PublishPreview(
                request_id=request.request_id,
                session_id=request.session_id,
                publisher=request.publisher,
                valid=False,
                errors=("pipeline expansion failed",),
            )
            self._emit_from_preview("task_publish.rejected", request, preview)
            return preview
        preview = self._publisher.preview(effective_request)
        self._emit_from_preview("task_publish.previewed", effective_request, preview)
        return preview

    def publish(self, request: PublishRequest) -> PublishResult:
        effective_request = self._expand_pipeline_or_none(request)
        if effective_request is None:
            rejected = PublishResult(
                request_id=request.request_id,
                session_id=request.session_id,
                publisher=request.publisher,
                skipped=True,
                reason="pipeline expansion failed",
                idempotency_key=request.idempotency_key,
            )
            self._emit_from_result("task_publish.rejected", request, rejected)
            return rejected

        request_hash = _request_hash(effective_request)
        if effective_request.idempotency_key is not None:
            replay = self._check_idempotency(effective_request, request_hash)
            if replay is not None:
                return replay

        preview = self._publisher.preview(effective_request)
        if preview.ok:
            self._emit_preview_validated(effective_request, preview.task_count)
        else:
            rejected = PublishResult(
                request_id=effective_request.request_id,
                session_id=effective_request.session_id,
                publisher=effective_request.publisher,
                skipped=True,
                reason="; ".join(preview.errors) or "publish preview failed",
                idempotency_key=effective_request.idempotency_key,
            )
            self._emit_from_result("task_publish.rejected", effective_request, rejected)
            self._store_idempotency(effective_request, request_hash, rejected)
            return rejected

        result = self._publisher.publish(effective_request)
        self._store_idempotency(effective_request, request_hash, result)
        self._emit_from_result(
            "task_publish.published" if result.accepted else "task_publish.rejected",
            effective_request,
            result,
        )
        return result

    def _check_idempotency(
        self,
        request: PublishRequest,
        request_hash: str,
    ) -> PublishResult | None:
        idempotency_key = request.idempotency_key
        if idempotency_key is None:
            return None
        record = self._idempotency_store.get(
            request.session_id,
            request.publisher.kind,
            idempotency_key,
        )
        if record is None:
            return None
        if record.request_hash != request_hash:
            result = PublishResult(
                request_id=request.request_id,
                session_id=request.session_id,
                publisher=request.publisher,
                skipped=True,
                reason="idempotency conflict",
                idempotency_key=idempotency_key,
                metadata={
                    "existing_request_hash": record.request_hash,
                    "request_hash": request_hash,
                },
            )
            self._emit_from_result("task_publish.idempotency_conflict", request, result)
            return result
        result = record.publish_result
        self._emit_from_result("task_publish.idempotent_replayed", request, result)
        return result

    def _store_idempotency(
        self,
        request: PublishRequest,
        request_hash: str,
        result: PublishResult,
    ) -> None:
        if request.idempotency_key is None:
            return
        if result.metadata.get("skip_idempotency_record") is True:
            return
        record = PublishIdempotencyRecord(
            session_id=request.session_id,
            publisher_kind=request.publisher.kind,
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
            publish_result=result,
        )
        with suppress(PublishIdempotencyConflictError):
            self._idempotency_store.put(record)

    def _expand_pipeline_or_none(self, request: PublishRequest) -> PublishRequest | None:
        if self._pipeline_loader is None:
            return request
        try:
            return self._pipeline_loader.expand_for_publish(request)
        except Exception:  # noqa: BLE001 - publish service returns skipped/invalid results.
            return None

    def _emit_preview_validated(self, request: PublishRequest, task_count: int) -> None:
        self._emit(
            PublishAuditEvent(
                kind="task_publish.validated",
                request_id=request.request_id,
                session_id=request.session_id,
                publisher_kind=request.publisher.kind,
                actor_id=request.publisher.actor_id,
                idempotency_key=request.idempotency_key,
                metadata={"task_count": task_count},
            )
        )

    def _emit_from_preview(
        self,
        kind: PublishAuditEventKind,
        request: PublishRequest,
        preview: PublishPreview,
    ) -> None:
        self._emit(
            PublishAuditEvent(
                kind=kind,
                request_id=preview.request_id,
                session_id=preview.session_id,
                publisher_kind=request.publisher.kind,
                actor_id=request.publisher.actor_id,
                idempotency_key=request.idempotency_key,
                reason=None if preview.ok else "; ".join(preview.errors),
                metadata={
                    "root_count": preview.root_count,
                    "task_count": preview.task_count,
                    "valid": preview.valid,
                },
            )
        )

    def _emit_from_result(
        self,
        kind: PublishAuditEventKind,
        request: PublishRequest,
        result: PublishResult,
    ) -> None:
        self._emit(
            PublishAuditEvent(
                kind=kind,
                request_id=result.request_id,
                session_id=result.session_id,
                publisher_kind=request.publisher.kind,
                actor_id=request.publisher.actor_id,
                idempotency_key=result.idempotency_key,
                root_task_ids=result.root_task_ids,
                published_task_ids=result.published_task_ids,
                reason=result.reason,
                metadata=dict(result.metadata),
            )
        )

    def _emit(self, event: PublishAuditEvent) -> None:
        if self._audit_sink is None:
            return
        with suppress(Exception):
            self._audit_sink.record(event)


def _request_hash(request: PublishRequest) -> str:
    payload = request.model_dump(mode="json", exclude={"request_id"})
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


__all__ = [
    "InMemoryPublishIdempotencyStore",
    "InMemoryTaskPublishAuditSink",
    "PublishAuditEvent",
    "PublishAuditEventKind",
    "PublishIdempotencyConflictError",
    "PublishIdempotencyRecord",
    "PublishIdempotencyStore",
    "TaskPublishAuditSink",
    "TaskPublishService",
]
