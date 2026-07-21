"""Durable idempotency records for external WeChat send effects."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Literal, Protocol, cast, runtime_checkable

from taskweavn.types.wechat_desktop import WeChatDesktopObservation

SendBoundaryState = Literal["in_progress", "completed", "unknown"]
SendBoundaryClaimStatus = Literal[
    "acquired",
    "replay",
    "conflict",
    "in_progress",
    "unknown",
]

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS wechat_send_boundary_records (
    scope_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    state TEXT NOT NULL,
    observation_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (scope_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_wechat_send_boundary_updated
    ON wechat_send_boundary_records(scope_id, updated_at, idempotency_key);

CREATE TABLE IF NOT EXISTS wechat_send_boundary_reconciliations (
    scope_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    reconciled_at TEXT NOT NULL,
    PRIMARY KEY (scope_id, idempotency_key)
);
"""


class SendBoundaryStoreError(RuntimeError):
    """Raised when a send-boundary record cannot be read or persisted."""


@dataclass(frozen=True)
class SendBoundaryReconciliationEvidence:
    """Operator evidence used to resolve one ambiguous external send."""

    source: Literal["manual_read_only_ui"]
    operator: str
    expected_contact: str
    message_sha256: str
    observed_outgoing_count: int
    exact_message_visible: bool
    chat_input_empty: bool
    observed_at: datetime
    note: str

    def __post_init__(self) -> None:
        if self.source != "manual_read_only_ui":
            raise ValueError("unsupported reconciliation evidence source")
        if not self.operator.strip():
            raise ValueError("reconciliation operator is required")
        if not self.expected_contact.strip():
            raise ValueError("reconciliation expected_contact is required")
        digest = self.message_sha256.removeprefix("sha256:")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("reconciliation message_sha256 must be a lowercase SHA-256")
        if self.observed_outgoing_count != 1:
            raise ValueError("reconciliation requires exactly one matching outgoing message")
        if not self.exact_message_visible:
            raise ValueError("reconciliation requires the exact outgoing message to be visible")
        if not self.chat_input_empty:
            raise ValueError("reconciliation requires an empty chat input")
        if self.observed_at.tzinfo is None:
            raise ValueError("reconciliation observed_at must include a timezone")
        if not self.note.strip():
            raise ValueError("reconciliation note is required")


@dataclass(frozen=True)
class SendBoundaryRecord:
    scope_id: str
    idempotency_key: str
    request_hash: str
    state: SendBoundaryState
    observation: WeChatDesktopObservation | None
    created_at: datetime
    updated_at: datetime
    reconciliation: SendBoundaryReconciliationEvidence | None = None
    reconciled_at: datetime | None = None


@dataclass(frozen=True)
class SendBoundaryClaim:
    status: SendBoundaryClaimStatus
    record: SendBoundaryRecord


@runtime_checkable
class SendBoundaryStore(Protocol):
    def get(
        self,
        *,
        scope_id: str,
        idempotency_key: str,
    ) -> SendBoundaryRecord | None: ...

    def claim(
        self,
        *,
        scope_id: str,
        idempotency_key: str,
        request_hash: str,
    ) -> SendBoundaryClaim: ...

    def complete(
        self,
        *,
        scope_id: str,
        idempotency_key: str,
        request_hash: str,
        state: Literal["completed", "unknown"],
        observation: WeChatDesktopObservation,
    ) -> SendBoundaryRecord: ...

    def reconcile_unknown_to_completed(
        self,
        *,
        scope_id: str,
        idempotency_key: str,
        request_hash: str,
        evidence: SendBoundaryReconciliationEvidence,
    ) -> SendBoundaryRecord: ...

    def close(self) -> None: ...


class SqliteSendBoundaryStore:
    """SQLite effect ledger that fails closed after ambiguous interruption."""

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
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA_DDL)
        self._lock = RLock()
        self._closed = False

    def claim(
        self,
        *,
        scope_id: str,
        idempotency_key: str,
        request_hash: str,
    ) -> SendBoundaryClaim:
        now = _utcnow()
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._select(scope_id, idempotency_key)
                if row is None:
                    self._conn.execute(
                        """
                        INSERT INTO wechat_send_boundary_records(
                            scope_id,
                            idempotency_key,
                            request_hash,
                            state,
                            observation_json,
                            created_at,
                            updated_at
                        ) VALUES (?, ?, ?, 'in_progress', NULL, ?, ?)
                        """,
                        (
                            scope_id,
                            idempotency_key,
                            request_hash,
                            now.isoformat(),
                            now.isoformat(),
                        ),
                    )
                    self._conn.commit()
                    record = SendBoundaryRecord(
                        scope_id=scope_id,
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                        state="in_progress",
                        observation=None,
                        created_at=now,
                        updated_at=now,
                    )
                    return SendBoundaryClaim(status="acquired", record=record)
                self._conn.commit()
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise SendBoundaryStoreError("failed to claim WeChat send boundary") from exc

        record = _record_from_row(row)
        if record.request_hash != request_hash:
            return SendBoundaryClaim(status="conflict", record=record)
        if record.state == "completed":
            return SendBoundaryClaim(status="replay", record=record)
        return SendBoundaryClaim(status=record.state, record=record)

    def get(
        self,
        *,
        scope_id: str,
        idempotency_key: str,
    ) -> SendBoundaryRecord | None:
        with self._lock:
            try:
                row = self._select(scope_id, idempotency_key)
            except sqlite3.Error as exc:
                raise SendBoundaryStoreError("failed to read WeChat send boundary") from exc
        return None if row is None else _record_from_row(row)

    def complete(
        self,
        *,
        scope_id: str,
        idempotency_key: str,
        request_hash: str,
        state: Literal["completed", "unknown"],
        observation: WeChatDesktopObservation,
    ) -> SendBoundaryRecord:
        now = _utcnow()
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._select(scope_id, idempotency_key)
                if row is None:
                    raise SendBoundaryStoreError(
                        "cannot complete an unclaimed WeChat send boundary"
                    )
                current = _record_from_row(row)
                if current.request_hash != request_hash:
                    raise SendBoundaryStoreError(
                        "WeChat send boundary request hash changed after claim"
                    )
                if current.state != "in_progress":
                    self._conn.commit()
                    return current
                self._conn.execute(
                    """
                    UPDATE wechat_send_boundary_records
                    SET state = ?, observation_json = ?, updated_at = ?
                    WHERE scope_id = ? AND idempotency_key = ?
                    """,
                    (
                        state,
                        observation.model_dump_json(),
                        now.isoformat(),
                        scope_id,
                        idempotency_key,
                    ),
                )
                self._conn.commit()
            except SendBoundaryStoreError:
                self._conn.rollback()
                raise
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise SendBoundaryStoreError("failed to complete WeChat send boundary") from exc
        return SendBoundaryRecord(
            scope_id=scope_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            state=state,
            observation=observation,
            created_at=current.created_at,
            updated_at=now,
        )

    def reconcile_unknown_to_completed(
        self,
        *,
        scope_id: str,
        idempotency_key: str,
        request_hash: str,
        evidence: SendBoundaryReconciliationEvidence,
    ) -> SendBoundaryRecord:
        """Resolve one verified ambiguous send without issuing another send."""
        now = _utcnow()
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._select(scope_id, idempotency_key)
                if row is None:
                    raise SendBoundaryStoreError(
                        "cannot reconcile an unclaimed WeChat send boundary"
                    )
                current = _record_from_row(row)
                if current.request_hash != request_hash:
                    raise SendBoundaryStoreError(
                        "WeChat send boundary request hash does not match reconciliation"
                    )
                if current.state != "unknown":
                    raise SendBoundaryStoreError(
                        "only an unknown WeChat send boundary can be reconciled"
                    )
                _validate_reconciliation_observation(current.observation, evidence)
                cursor = self._conn.execute(
                    """
                    UPDATE wechat_send_boundary_records
                    SET state = 'completed', updated_at = ?
                    WHERE scope_id = ? AND idempotency_key = ?
                      AND request_hash = ? AND state = 'unknown'
                    """,
                    (
                        now.isoformat(),
                        scope_id,
                        idempotency_key,
                        request_hash,
                    ),
                )
                if cursor.rowcount != 1:
                    raise SendBoundaryStoreError(
                        "WeChat send boundary changed during reconciliation"
                    )
                self._conn.execute(
                    """
                    INSERT INTO wechat_send_boundary_reconciliations(
                        scope_id,
                        idempotency_key,
                        request_hash,
                        evidence_json,
                        reconciled_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        scope_id,
                        idempotency_key,
                        request_hash,
                        _reconciliation_to_json(evidence),
                        now.isoformat(),
                    ),
                )
                self._conn.commit()
            except SendBoundaryStoreError:
                self._conn.rollback()
                raise
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise SendBoundaryStoreError("failed to reconcile WeChat send boundary") from exc
        return SendBoundaryRecord(
            scope_id=current.scope_id,
            idempotency_key=current.idempotency_key,
            request_hash=current.request_hash,
            state="completed",
            observation=current.observation,
            created_at=current.created_at,
            updated_at=now,
            reconciliation=evidence,
            reconciled_at=now,
        )

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._conn.close()
            self._closed = True

    def _select(self, scope_id: str, idempotency_key: str) -> sqlite3.Row | None:
        return cast(
            sqlite3.Row | None,
            self._conn.execute(
                """
                SELECT records.*,
                       reconciliations.evidence_json AS reconciliation_json,
                       reconciliations.reconciled_at
                FROM wechat_send_boundary_records AS records
                LEFT JOIN wechat_send_boundary_reconciliations AS reconciliations
                  ON reconciliations.scope_id = records.scope_id
                 AND reconciliations.idempotency_key = records.idempotency_key
                WHERE records.scope_id = ? AND records.idempotency_key = ?
                """,
                (scope_id, idempotency_key),
            ).fetchone(),
        )

    def __enter__(self) -> SqliteSendBoundaryStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def managed_send_boundary_key(session_id: str, task_id: str) -> str:
    """Derive one stable external-message effect key from TaskBus identity."""
    if not session_id or not task_id:
        raise ValueError("session_id and task_id are required for a managed send key")
    return f"wechat-send:{session_id}:{task_id}"


def _record_from_row(row: sqlite3.Row) -> SendBoundaryRecord:
    try:
        state = str(row["state"])
        if state not in {"in_progress", "completed", "unknown"}:
            raise ValueError(f"unsupported send-boundary state: {state}")
        observation_json = row["observation_json"]
        observation = (
            None
            if observation_json is None
            else WeChatDesktopObservation.model_validate(json.loads(str(observation_json)))
        )
        reconciliation_json = row["reconciliation_json"]
        reconciliation = (
            None
            if reconciliation_json is None
            else _reconciliation_from_json(str(reconciliation_json))
        )
        reconciled_at = row["reconciled_at"]
        return SendBoundaryRecord(
            scope_id=str(row["scope_id"]),
            idempotency_key=str(row["idempotency_key"]),
            request_hash=str(row["request_hash"]),
            state=cast(SendBoundaryState, state),
            observation=observation,
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            reconciliation=reconciliation,
            reconciled_at=(
                None if reconciled_at is None else datetime.fromisoformat(str(reconciled_at))
            ),
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SendBoundaryStoreError("invalid WeChat send-boundary record") from exc


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _validate_reconciliation_observation(
    observation: WeChatDesktopObservation | None,
    evidence: SendBoundaryReconciliationEvidence,
) -> None:
    if observation is None:
        raise SendBoundaryStoreError("unknown send boundary has no original observation")
    if (
        observation.operation != "send_message"
        or observation.status != "unknown"
        or observation.success
    ):
        raise SendBoundaryStoreError("original observation is not an ambiguous WeChat send")
    package_observation = observation.metadata.get("observation")
    if not isinstance(package_observation, dict):
        raise SendBoundaryStoreError("original send observation is missing package evidence")
    if package_observation.get("submitted") is not True:
        raise SendBoundaryStoreError("original send observation did not record submission")
    if package_observation.get("focusedContact") != evidence.expected_contact:
        raise SendBoundaryStoreError("reconciliation contact does not match original send")
    expected_hash = f"sha256:{evidence.message_sha256.removeprefix('sha256:')}"
    if package_observation.get("messageHash") != expected_hash:
        raise SendBoundaryStoreError("reconciliation message hash does not match original send")


def _reconciliation_to_json(evidence: SendBoundaryReconciliationEvidence) -> str:
    return json.dumps(
        {
            "source": evidence.source,
            "operator": evidence.operator,
            "expectedContact": evidence.expected_contact,
            "messageSha256": evidence.message_sha256.removeprefix("sha256:"),
            "observedOutgoingCount": evidence.observed_outgoing_count,
            "exactMessageVisible": evidence.exact_message_visible,
            "chatInputEmpty": evidence.chat_input_empty,
            "observedAt": evidence.observed_at.isoformat(),
            "note": evidence.note,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _reconciliation_from_json(raw: str) -> SendBoundaryReconciliationEvidence:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("reconciliation evidence must be an object")
    return SendBoundaryReconciliationEvidence(
        source=cast(Literal["manual_read_only_ui"], payload["source"]),
        operator=str(payload["operator"]),
        expected_contact=str(payload["expectedContact"]),
        message_sha256=str(payload["messageSha256"]),
        observed_outgoing_count=int(payload["observedOutgoingCount"]),
        exact_message_visible=bool(payload["exactMessageVisible"]),
        chat_input_empty=bool(payload["chatInputEmpty"]),
        observed_at=datetime.fromisoformat(str(payload["observedAt"])),
        note=str(payload["note"]),
    )


__all__ = [
    "SendBoundaryClaim",
    "SendBoundaryClaimStatus",
    "SendBoundaryRecord",
    "SendBoundaryReconciliationEvidence",
    "SendBoundaryState",
    "SendBoundaryStore",
    "SendBoundaryStoreError",
    "SqliteSendBoundaryStore",
    "managed_send_boundary_key",
]
