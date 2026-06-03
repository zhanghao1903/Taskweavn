"""SQLite-backed durable execution ASK store."""

from __future__ import annotations

import contextlib
import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Literal

from taskweavn.interaction.ask import (
    AskAnswer,
    AskCommandKind,
    AskOption,
    AskRequest,
    AskStatus,
    AskStoreCommandResult,
    AskStoreError,
    _answer_request,
    _transition_request,
)

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS asks (
    ask_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    task_id TEXT,
    agent_id TEXT NOT NULL,
    question TEXT NOT NULL,
    reason TEXT NOT NULL,
    suggested_options_json TEXT NOT NULL,
    answer_type TEXT NOT NULL,
    allow_free_text INTEGER NOT NULL,
    allow_no_option_with_text INTEGER NOT NULL,
    blocking INTEGER NOT NULL,
    attachments_supported INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    answer_id TEXT,
    resume_hint TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    answered_at TEXT,
    deferred_at TEXT,
    cancelled_at TEXT,
    expired_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_asks_session_status_created
    ON asks(session_id, status, created_at, ask_id);

CREATE INDEX IF NOT EXISTS idx_asks_session_task_status_created
    ON asks(session_id, task_id, status, created_at, ask_id);

CREATE TABLE IF NOT EXISTS ask_answers (
    answer_id TEXT PRIMARY KEY,
    ask_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    task_id TEXT,
    selected_option_ids_json TEXT NOT NULL,
    text TEXT,
    attachments_json TEXT NOT NULL,
    answered_by TEXT NOT NULL,
    idempotency_key TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(ask_id) REFERENCES asks(ask_id)
);

CREATE INDEX IF NOT EXISTS idx_ask_answers_session_ask
    ON ask_answers(session_id, ask_id);

CREATE TABLE IF NOT EXISTS ask_command_idempotency (
    session_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    command_kind TEXT NOT NULL,
    ask_id TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(session_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_ask_command_idempotency_session_created
    ON ask_command_idempotency(session_id, created_at, idempotency_key);
"""


class SqliteAskStore:
    """SQLite implementation of the execution ASK store."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            isolation_level=None,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA_DDL)
        self._lock = RLock()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def create(self, request: AskRequest) -> AskRequest:
        with self._lock:
            try:
                self._conn.execute(
                    """
                    INSERT INTO asks(
                        ask_id,
                        session_id,
                        task_id,
                        agent_id,
                        question,
                        reason,
                        suggested_options_json,
                        answer_type,
                        allow_free_text,
                        allow_no_option_with_text,
                        blocking,
                        attachments_supported,
                        status,
                        answer_id,
                        resume_hint,
                        created_by,
                        created_at,
                        answered_at,
                        deferred_at,
                        cancelled_at,
                        expired_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _request_to_row(request),
                )
            except sqlite3.IntegrityError as exc:
                raise AskStoreError(f"ASK {request.ask_id!r} already exists") from exc
            except sqlite3.Error as exc:
                raise AskStoreError("failed to create ASK") from exc
            return request

    def get(self, session_id: str, ask_id: str) -> AskRequest | None:
        with self._lock:
            return self._get_locked(session_id, ask_id)

    def list_for_session(
        self,
        session_id: str,
        *,
        statuses: Iterable[AskStatus] | None = None,
        task_id: str | None = None,
    ) -> list[AskRequest]:
        status_set = None if statuses is None else tuple(statuses)
        if status_set == ():
            return []
        clauses = ["session_id = ?"]
        params: list[Any] = [session_id]
        if task_id is not None:
            clauses.append("task_id = ?")
            params.append(task_id)
        if status_set is not None:
            clauses.append(f"status IN ({', '.join('?' * len(status_set))})")
            params.extend(status_set)
        sql = (
            "SELECT * FROM asks "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY created_at, ask_id"
        )
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [_request_from_row(row) for row in rows]

    def get_answer(self, session_id: str, ask_id: str) -> AskAnswer | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM ask_answers
                WHERE session_id = ? AND ask_id = ?
                """,
                (session_id, ask_id),
            ).fetchone()
        return None if row is None else _answer_from_row(row)

    def answer(
        self,
        session_id: str,
        ask_id: str,
        answer: AskAnswer,
        *,
        idempotency_key: str | None = None,
    ) -> AskStoreCommandResult:
        with self._lock:
            replay = self._idempotency_replay_locked(session_id, idempotency_key)
            if replay is not None:
                return replay
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                request = self._get_locked(session_id, ask_id)
                result = _answer_request(
                    request,
                    answer,
                    idempotency_key=idempotency_key,
                )
                if result.status == "accepted" and result.ask is not None:
                    assert result.answer is not None
                    self._insert_answer_locked(result.answer)
                    self._update_request_locked(result.ask)
                self._remember_locked(session_id, idempotency_key, result)
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise AskStoreError("failed to answer ASK") from exc
            else:
                self._conn.commit()
                return result

    def defer(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> AskStoreCommandResult:
        return self._transition(
            session_id,
            ask_id,
            status="deferred",
            command_kind="defer",
            reason=reason,
            idempotency_key=idempotency_key,
        )

    def cancel(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str,
        idempotency_key: str | None = None,
    ) -> AskStoreCommandResult:
        return self._transition(
            session_id,
            ask_id,
            status="cancelled",
            command_kind="cancel",
            reason=reason,
            idempotency_key=idempotency_key,
        )

    def expire(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> AskStoreCommandResult:
        return self._transition(
            session_id,
            ask_id,
            status="expired",
            command_kind="expire",
            reason=reason,
            idempotency_key=idempotency_key,
        )

    def close(self) -> None:
        with self._lock, contextlib.suppress(sqlite3.Error):
            self._conn.close()

    def __enter__(self) -> SqliteAskStore:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _transition(
        self,
        session_id: str,
        ask_id: str,
        *,
        status: Literal["deferred", "cancelled", "expired"],
        command_kind: AskCommandKind,
        reason: str | None,
        idempotency_key: str | None,
    ) -> AskStoreCommandResult:
        with self._lock:
            replay = self._idempotency_replay_locked(session_id, idempotency_key)
            if replay is not None:
                return replay
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                request = self._get_locked(session_id, ask_id)
                result = _transition_request(
                    request,
                    command_kind=command_kind,
                    status=status,
                    reason=reason,
                    idempotency_key=idempotency_key,
                )
                if result.status == "accepted" and result.ask is not None:
                    self._update_request_locked(result.ask)
                self._remember_locked(session_id, idempotency_key, result)
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise AskStoreError("failed to transition ASK") from exc
            else:
                self._conn.commit()
                return result

    def _get_locked(self, session_id: str, ask_id: str) -> AskRequest | None:
        row = self._conn.execute(
            "SELECT * FROM asks WHERE session_id = ? AND ask_id = ?",
            (session_id, ask_id),
        ).fetchone()
        return None if row is None else _request_from_row(row)

    def _insert_answer_locked(self, answer: AskAnswer) -> None:
        self._conn.execute(
            """
            INSERT INTO ask_answers(
                answer_id,
                ask_id,
                session_id,
                task_id,
                selected_option_ids_json,
                text,
                attachments_json,
                answered_by,
                idempotency_key,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _answer_to_row(answer),
        )

    def _update_request_locked(self, request: AskRequest) -> None:
        self._conn.execute(
            """
            UPDATE asks SET
                task_id = ?,
                agent_id = ?,
                question = ?,
                reason = ?,
                suggested_options_json = ?,
                answer_type = ?,
                allow_free_text = ?,
                allow_no_option_with_text = ?,
                blocking = ?,
                attachments_supported = ?,
                status = ?,
                answer_id = ?,
                resume_hint = ?,
                created_by = ?,
                created_at = ?,
                answered_at = ?,
                deferred_at = ?,
                cancelled_at = ?,
                expired_at = ?
            WHERE session_id = ? AND ask_id = ?
            """,
            (
                request.task_id,
                request.agent_id,
                request.question,
                request.reason,
                _options_json(request.suggested_options),
                request.answer_type,
                1 if request.allow_free_text else 0,
                1 if request.allow_no_option_with_text else 0,
                1 if request.blocking else 0,
                0,
                request.status,
                request.answer_id,
                request.resume_hint,
                request.created_by,
                request.created_at.isoformat(),
                _dt(request.answered_at),
                _dt(request.deferred_at),
                _dt(request.cancelled_at),
                _dt(request.expired_at),
                request.session_id,
                request.ask_id,
            ),
        )

    def _idempotency_replay_locked(
        self,
        session_id: str,
        idempotency_key: str | None,
    ) -> AskStoreCommandResult | None:
        if idempotency_key is None:
            return None
        row = self._conn.execute(
            """
            SELECT result_json FROM ask_command_idempotency
            WHERE session_id = ? AND idempotency_key = ?
            """,
            (session_id, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        result = AskStoreCommandResult.model_validate_json(str(row["result_json"]))
        if result.status == "rejected":
            return result
        return result.model_copy(update={"status": "replayed"})

    def _remember_locked(
        self,
        session_id: str,
        idempotency_key: str | None,
        result: AskStoreCommandResult,
    ) -> None:
        if idempotency_key is None:
            return
        self._conn.execute(
            """
            INSERT OR IGNORE INTO ask_command_idempotency(
                session_id,
                idempotency_key,
                command_kind,
                ask_id,
                result_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                idempotency_key,
                result.command_kind,
                result.ask.ask_id if result.ask is not None else "",
                result.model_dump_json(),
                datetime.now(UTC).isoformat(),
            ),
        )


def _request_to_row(request: AskRequest) -> tuple[Any, ...]:
    return (
        request.ask_id,
        request.session_id,
        request.task_id,
        request.agent_id,
        request.question,
        request.reason,
        _options_json(request.suggested_options),
        request.answer_type,
        1 if request.allow_free_text else 0,
        1 if request.allow_no_option_with_text else 0,
        1 if request.blocking else 0,
        0,
        request.status,
        request.answer_id,
        request.resume_hint,
        request.created_by,
        request.created_at.isoformat(),
        _dt(request.answered_at),
        _dt(request.deferred_at),
        _dt(request.cancelled_at),
        _dt(request.expired_at),
    )


def _request_from_row(row: sqlite3.Row) -> AskRequest:
    return AskRequest(
        ask_id=str(row["ask_id"]),
        session_id=str(row["session_id"]),
        task_id=_optional_str(row["task_id"]),
        agent_id=str(row["agent_id"]),
        question=str(row["question"]),
        reason=str(row["reason"]),
        suggested_options=_options_from_json(str(row["suggested_options_json"])),
        answer_type=str(row["answer_type"]),  # type: ignore[arg-type]
        allow_free_text=bool(row["allow_free_text"]),
        allow_no_option_with_text=bool(row["allow_no_option_with_text"]),
        blocking=bool(row["blocking"]),
        attachments_supported=False,
        status=str(row["status"]),  # type: ignore[arg-type]
        answer_id=_optional_str(row["answer_id"]),
        resume_hint=_optional_str(row["resume_hint"]),
        created_by=str(row["created_by"]),  # type: ignore[arg-type]
        created_at=datetime.fromisoformat(str(row["created_at"])),
        answered_at=_optional_dt(row["answered_at"]),
        deferred_at=_optional_dt(row["deferred_at"]),
        cancelled_at=_optional_dt(row["cancelled_at"]),
        expired_at=_optional_dt(row["expired_at"]),
    )


def _answer_to_row(answer: AskAnswer) -> tuple[Any, ...]:
    return (
        answer.answer_id,
        answer.ask_id,
        answer.session_id,
        answer.task_id,
        _json_dumps(list(answer.selected_option_ids)),
        answer.text,
        _json_dumps(list(answer.attachments)),
        answer.answered_by,
        answer.idempotency_key,
        answer.created_at.isoformat(),
    )


def _answer_from_row(row: sqlite3.Row) -> AskAnswer:
    selected_options = json.loads(str(row["selected_option_ids_json"]))
    attachments = json.loads(str(row["attachments_json"]))
    if not isinstance(selected_options, list) or not isinstance(attachments, list):
        raise AskStoreError("invalid ASK answer JSON row")
    return AskAnswer(
        answer_id=str(row["answer_id"]),
        ask_id=str(row["ask_id"]),
        session_id=str(row["session_id"]),
        task_id=_optional_str(row["task_id"]),
        selected_option_ids=tuple(str(value) for value in selected_options),
        text=_optional_str(row["text"]),
        attachments=tuple(attachments),
        answered_by=str(row["answered_by"]),  # type: ignore[arg-type]
        idempotency_key=_optional_str(row["idempotency_key"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _options_json(options: tuple[AskOption, ...]) -> str:
    return _json_dumps([option.model_dump(mode="json") for option in options])


def _options_from_json(raw: str) -> tuple[AskOption, ...]:
    loaded = json.loads(raw)
    if not isinstance(loaded, list):
        raise AskStoreError("invalid ASK options JSON row")
    return tuple(AskOption.model_validate(item) for item in loaded)


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))


def _dt(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


__all__ = ["SqliteAskStore"]
