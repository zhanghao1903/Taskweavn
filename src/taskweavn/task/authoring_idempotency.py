"""Durable idempotency records for authoring command results."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from threading import RLock
from typing import ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from taskweavn.task.authoring import AuthoringCommandResult


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuthoringCommandIdempotencyRecord(BaseModel):
    """Cached terminal result for one authoring command idempotency key.

    The key is authoritative. Reusing the same key replays the first result so
    restart/retry flows cannot create duplicate RawTask, DraftTaskTree, or
    publish side effects.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )

    session_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    request_hash: str = Field(min_length=1)
    result: AuthoringCommandResult
    created_at: datetime = Field(default_factory=_utcnow)

    @property
    def key(self) -> tuple[str, str]:
        return (self.session_id, self.idempotency_key)


@runtime_checkable
class AuthoringCommandIdempotencyStore(Protocol):
    """Caches authoring command results by session and idempotency key."""

    def get(
        self,
        session_id: str,
        idempotency_key: str,
    ) -> AuthoringCommandIdempotencyRecord | None: ...

    def put(
        self,
        record: AuthoringCommandIdempotencyRecord,
    ) -> AuthoringCommandIdempotencyRecord: ...


class InMemoryAuthoringCommandIdempotencyStore:
    """Deterministic in-memory idempotency cache used by tests/defaults."""

    def __init__(
        self,
        records: Iterable[AuthoringCommandIdempotencyRecord] = (),
    ) -> None:
        self._lock = RLock()
        self._records = {record.key: record for record in records}

    def get(
        self,
        session_id: str,
        idempotency_key: str,
    ) -> AuthoringCommandIdempotencyRecord | None:
        with self._lock:
            return self._records.get((session_id, idempotency_key))

    def put(
        self,
        record: AuthoringCommandIdempotencyRecord,
    ) -> AuthoringCommandIdempotencyRecord:
        with self._lock:
            current = self._records.get(record.key)
            if current is not None:
                return current
            self._records[record.key] = record
            return record


__all__ = [
    "AuthoringCommandIdempotencyRecord",
    "AuthoringCommandIdempotencyStore",
    "InMemoryAuthoringCommandIdempotencyStore",
]
