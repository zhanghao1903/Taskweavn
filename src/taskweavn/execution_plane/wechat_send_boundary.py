"""Durable send-boundary store for local WeChat send executions."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Literal, Protocol, Self, runtime_checkable

WeChatSendBoundaryStatus = Literal[
    "not_started",
    "drafted",
    "confirmation_requested",
    "confirmed",
    "send_attempted",
    "sent",
    "not_sent",
    "unknown",
]

_TERMINAL_STATUSES: frozenset[WeChatSendBoundaryStatus] = frozenset(
    {"sent", "not_sent", "unknown"}
)
_MANUAL_REVIEW_STATUSES: frozenset[WeChatSendBoundaryStatus] = frozenset(
    {"send_attempted", "unknown"}
)
_TRANSITIONS: dict[WeChatSendBoundaryStatus, frozenset[WeChatSendBoundaryStatus]] = {
    "not_started": frozenset({"drafted", "not_sent", "unknown"}),
    "drafted": frozenset({"confirmation_requested", "not_sent", "unknown"}),
    "confirmation_requested": frozenset({"confirmed", "not_sent", "unknown"}),
    "confirmed": frozenset({"send_attempted", "not_sent", "unknown"}),
    "send_attempted": frozenset({"sent", "unknown"}),
    "sent": frozenset(),
    "not_sent": frozenset(),
    "unknown": frozenset(),
}


class WeChatSendBoundaryStoreError(RuntimeError):
    """Base error for WeChat send-boundary persistence failures."""


class WeChatSendBoundaryConflictError(WeChatSendBoundaryStoreError):
    """Raised when an idempotency key or fingerprint is reused inconsistently."""


class WeChatSendBoundaryTransitionError(WeChatSendBoundaryStoreError):
    """Raised when a status transition would make the send boundary unsafe."""


@dataclass(frozen=True)
class WeChatSendBoundary:
    """Persistent identity and status for one WeChat send execution."""

    execution_id: str
    idempotency_key: str
    task_ref_kind: str
    task_ref_id: str
    contact_summary_hash: str
    message_hash: str
    action_fingerprint: str
    status: WeChatSendBoundaryStatus = "not_started"
    confirmation_id: str | None = None
    draft_observation_ref: str | None = None
    send_observation_ref: str | None = None
    result_ref: str | None = None
    error_ref: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "execution_id",
            "idempotency_key",
            "task_ref_kind",
            "task_ref_id",
            "contact_summary_hash",
            "message_hash",
            "action_fingerprint",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} is required")
        now = _utcnow()
        if self.created_at is None:
            object.__setattr__(self, "created_at", now)
        else:
            object.__setattr__(self, "created_at", _as_utc(self.created_at))
        if self.updated_at is None:
            object.__setattr__(self, "updated_at", self.created_at)
        else:
            object.__setattr__(self, "updated_at", _as_utc(self.updated_at))

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL_STATUSES

    @property
    def requires_manual_review(self) -> bool:
        return self.status in _MANUAL_REVIEW_STATUSES

    @property
    def can_recover_to_confirmation(self) -> bool:
        return self.status in {"drafted", "confirmation_requested"}


@runtime_checkable
class WeChatSendBoundaryStore(Protocol):
    def put(self, boundary: WeChatSendBoundary) -> WeChatSendBoundary: ...

    def get(self, execution_id: str) -> WeChatSendBoundary | None: ...

    def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> WeChatSendBoundary | None: ...

    def get_by_action_fingerprint(
        self,
        action_fingerprint: str,
    ) -> WeChatSendBoundary | None: ...

    def transition(
        self,
        execution_id: str,
        status: WeChatSendBoundaryStatus,
        *,
        confirmation_id: str | None = None,
        draft_observation_ref: str | None = None,
        send_observation_ref: str | None = None,
        result_ref: str | None = None,
        error_ref: str | None = None,
    ) -> WeChatSendBoundary: ...


_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS wechat_send_boundaries (
    execution_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    task_ref_kind TEXT NOT NULL,
    task_ref_id TEXT NOT NULL,
    contact_summary_hash TEXT NOT NULL,
    message_hash TEXT NOT NULL,
    action_fingerprint TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    confirmation_id TEXT,
    draft_observation_ref TEXT,
    send_observation_ref TEXT,
    result_ref TEXT,
    error_ref TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wechat_send_boundaries_status
    ON wechat_send_boundaries(status, updated_at);
"""


class SqliteWeChatSendBoundaryStore:
    """SQLite-backed send-boundary store for local WeChat send tasks."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            isolation_level=None,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA_DDL)
        self._lock = RLock()

    def put(self, boundary: WeChatSendBoundary) -> WeChatSendBoundary:
        with self._lock:
            try:
                with self._write_transaction():
                    self._conn.execute(
                        """
                        INSERT INTO wechat_send_boundaries(
                            execution_id,
                            idempotency_key,
                            task_ref_kind,
                            task_ref_id,
                            contact_summary_hash,
                            message_hash,
                            action_fingerprint,
                            status,
                            confirmation_id,
                            draft_observation_ref,
                            send_observation_ref,
                            result_ref,
                            error_ref,
                            created_at,
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        _to_row(boundary),
                    )
                return boundary
            except sqlite3.IntegrityError:
                existing = (
                    self.get(boundary.execution_id)
                    or self.get_by_idempotency_key(boundary.idempotency_key)
                    or self.get_by_action_fingerprint(boundary.action_fingerprint)
                )
                if existing is not None and _same_identity(existing, boundary):
                    return existing
                raise WeChatSendBoundaryConflictError(
                    "WeChat send idempotency key or action fingerprint was reused "
                    "for a different send boundary"
                ) from None
            except sqlite3.Error as exc:
                raise WeChatSendBoundaryStoreError(
                    f"failed to store WeChat send boundary: {exc}"
                ) from exc

    def get(self, execution_id: str) -> WeChatSendBoundary | None:
        return self._get("execution_id", execution_id)

    def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> WeChatSendBoundary | None:
        return self._get("idempotency_key", idempotency_key)

    def get_by_action_fingerprint(
        self,
        action_fingerprint: str,
    ) -> WeChatSendBoundary | None:
        return self._get("action_fingerprint", action_fingerprint)

    def transition(
        self,
        execution_id: str,
        status: WeChatSendBoundaryStatus,
        *,
        confirmation_id: str | None = None,
        draft_observation_ref: str | None = None,
        send_observation_ref: str | None = None,
        result_ref: str | None = None,
        error_ref: str | None = None,
    ) -> WeChatSendBoundary:
        with self._lock:
            current = self.get(execution_id)
            if current is None:
                raise WeChatSendBoundaryStoreError(
                    f"WeChat send boundary {execution_id!r} not found"
                )
            _validate_transition(current.status, status)
            updated = replace(
                current,
                status=status,
                confirmation_id=confirmation_id or current.confirmation_id,
                draft_observation_ref=(
                    draft_observation_ref or current.draft_observation_ref
                ),
                send_observation_ref=send_observation_ref
                or current.send_observation_ref,
                result_ref=result_ref or current.result_ref,
                error_ref=error_ref or current.error_ref,
                updated_at=_utcnow(),
            )
            updated_at = updated.updated_at
            if updated_at is None:
                raise WeChatSendBoundaryStoreError(
                    "updated boundary timestamp was not initialized"
                )
            try:
                with self._write_transaction():
                    self._conn.execute(
                        """
                        UPDATE wechat_send_boundaries
                        SET status = ?,
                            confirmation_id = ?,
                            draft_observation_ref = ?,
                            send_observation_ref = ?,
                            result_ref = ?,
                            error_ref = ?,
                            updated_at = ?
                        WHERE execution_id = ?
                        """,
                        (
                            updated.status,
                            updated.confirmation_id,
                            updated.draft_observation_ref,
                            updated.send_observation_ref,
                            updated.result_ref,
                            updated.error_ref,
                            updated_at.isoformat(),
                            updated.execution_id,
                        ),
                    )
            except sqlite3.Error as exc:
                raise WeChatSendBoundaryStoreError(
                    f"failed to transition WeChat send boundary: {exc}"
                ) from exc
            return updated

    def _get(self, column: str, value: str) -> WeChatSendBoundary | None:
        if column not in {"execution_id", "idempotency_key", "action_fingerprint"}:
            raise ValueError(f"unsupported lookup column: {column}")
        with self._lock:
            row = self._conn.execute(
                f"""
                SELECT
                    execution_id,
                    idempotency_key,
                    task_ref_kind,
                    task_ref_id,
                    contact_summary_hash,
                    message_hash,
                    action_fingerprint,
                    status,
                    confirmation_id,
                    draft_observation_ref,
                    send_observation_ref,
                    result_ref,
                    error_ref,
                    created_at,
                    updated_at
                FROM wechat_send_boundaries
                WHERE {column} = ?
                """,
                (value,),
            ).fetchone()
        if row is None:
            return None
        return _from_row(row)

    @contextmanager
    def _write_transaction(self) -> Iterator[None]:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            yield
        except Exception:
            self._conn.rollback()
            raise
        else:
            self._conn.commit()

    def close(self) -> None:
        with self._lock, contextlib.suppress(sqlite3.Error):
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _to_row(boundary: WeChatSendBoundary) -> tuple[object, ...]:
    if boundary.created_at is None or boundary.updated_at is None:
        raise ValueError("boundary timestamps must be initialized")
    return (
        boundary.execution_id,
        boundary.idempotency_key,
        boundary.task_ref_kind,
        boundary.task_ref_id,
        boundary.contact_summary_hash,
        boundary.message_hash,
        boundary.action_fingerprint,
        boundary.status,
        boundary.confirmation_id,
        boundary.draft_observation_ref,
        boundary.send_observation_ref,
        boundary.result_ref,
        boundary.error_ref,
        boundary.created_at.isoformat(),
        boundary.updated_at.isoformat(),
    )


def _from_row(row: sqlite3.Row) -> WeChatSendBoundary:
    status = str(row["status"])
    if status not in _TRANSITIONS:
        raise WeChatSendBoundaryStoreError(
            f"invalid WeChat send boundary status {status!r}"
        )
    return WeChatSendBoundary(
        execution_id=str(row["execution_id"]),
        idempotency_key=str(row["idempotency_key"]),
        task_ref_kind=str(row["task_ref_kind"]),
        task_ref_id=str(row["task_ref_id"]),
        contact_summary_hash=str(row["contact_summary_hash"]),
        message_hash=str(row["message_hash"]),
        action_fingerprint=str(row["action_fingerprint"]),
        status=status,
        confirmation_id=_optional_str(row["confirmation_id"]),
        draft_observation_ref=_optional_str(row["draft_observation_ref"]),
        send_observation_ref=_optional_str(row["send_observation_ref"]),
        result_ref=_optional_str(row["result_ref"]),
        error_ref=_optional_str(row["error_ref"]),
        created_at=_parse_datetime(str(row["created_at"])),
        updated_at=_parse_datetime(str(row["updated_at"])),
    )


def _same_identity(left: WeChatSendBoundary, right: WeChatSendBoundary) -> bool:
    return (
        left.execution_id == right.execution_id
        and left.idempotency_key == right.idempotency_key
        and left.task_ref_kind == right.task_ref_kind
        and left.task_ref_id == right.task_ref_id
        and left.contact_summary_hash == right.contact_summary_hash
        and left.message_hash == right.message_hash
        and left.action_fingerprint == right.action_fingerprint
    )


def _validate_transition(
    current: WeChatSendBoundaryStatus,
    next_status: WeChatSendBoundaryStatus,
) -> None:
    if current == next_status:
        return
    if next_status not in _TRANSITIONS[current]:
        raise WeChatSendBoundaryTransitionError(
            f"invalid WeChat send boundary transition: {current} -> {next_status}"
        )


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _parse_datetime(value: str) -> datetime:
    return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _utcnow() -> datetime:
    return datetime.now(UTC)


__all__ = [
    "SqliteWeChatSendBoundaryStore",
    "WeChatSendBoundary",
    "WeChatSendBoundaryConflictError",
    "WeChatSendBoundaryStatus",
    "WeChatSendBoundaryStore",
    "WeChatSendBoundaryStoreError",
    "WeChatSendBoundaryTransitionError",
]
