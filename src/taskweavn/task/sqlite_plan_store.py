"""SQLite-backed durable Plan and TaskNode store."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Self

from pydantic import ValidationError

from taskweavn.task.models import TaskRef
from taskweavn.task.plan_models import (
    Plan,
    PlanContextPolicy,
    PlanFinalizationState,
    PlanOutcome,
    PlanTaskNode,
)
from taskweavn.task.plan_stores import PlanStoreError
from taskweavn.task.stores import VersionConflictError

_SCHEMA_VERSION = "2"

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS plan_schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    session_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    source_raw_task_id TEXT,
    source_draft_tree_id TEXT,
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL,
    context_policy_json TEXT NOT NULL,
    finalization_json TEXT NOT NULL,
    outcome_json TEXT,
    version INTEGER NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT,
    PRIMARY KEY (session_id, plan_id)
);

CREATE INDEX IF NOT EXISTS idx_plans_session_updated
    ON plans(session_id, updated_at, plan_id);

CREATE TABLE IF NOT EXISTS plan_task_nodes (
    session_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    task_node_id TEXT NOT NULL,
    task_index TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    intent TEXT NOT NULL,
    summary TEXT NOT NULL,
    instructions TEXT NOT NULL,
    required_capability TEXT,
    depends_on_json TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    acceptance_criteria_json TEXT NOT NULL,
    readiness TEXT NOT NULL,
    execution TEXT NOT NULL,
    draft_ref_json TEXT,
    published_ref_json TEXT,
    result_ref TEXT,
    error_ref TEXT,
    file_summary_ref TEXT,
    audit_ref TEXT,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (session_id, task_node_id),
    UNIQUE (session_id, plan_id, task_index),
    FOREIGN KEY(session_id, plan_id) REFERENCES plans(session_id, plan_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_plan_task_nodes_order
    ON plan_task_nodes(session_id, plan_id, order_index, task_node_id);
"""


class SqlitePlanStore:
    """SQLite-backed PlanStore implementation.

    This store can share the existing ``authoring.sqlite`` file with legacy
    authoring stores. It creates only Plan-specific tables and leaves
    DraftTaskTree tables and reads untouched.
    """

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
        self._migrate_schema()
        self._conn.execute(
            """
            INSERT INTO plan_schema_meta(key, value, updated_at)
            VALUES('schema_version', ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (_SCHEMA_VERSION, _utcnow().isoformat()),
        )
        self._lock = RLock()

    def _migrate_schema(self) -> None:
        node_columns = {
            str(row["name"])
            for row in self._conn.execute("PRAGMA table_info(plan_task_nodes)")
        }
        if "error_ref" not in node_columns:
            self._conn.execute("ALTER TABLE plan_task_nodes ADD COLUMN error_ref TEXT")

    def create_plan(
        self,
        plan: Plan,
        task_nodes: Sequence[PlanTaskNode] = (),
    ) -> Plan:
        ordered_nodes = _ordered_nodes(task_nodes)
        _validate_plan_nodes(plan, ordered_nodes)
        saved_plan = _copy_plan(
            plan,
            task_node_ids=tuple(node.task_node_id for node in ordered_nodes),
        )
        with self._lock:
            if self.get_plan(saved_plan.session_id, saved_plan.plan_id) is not None:
                raise PlanStoreError(f"Plan {saved_plan.plan_id!r} already exists")
            try:
                with self._write_transaction():
                    self._insert_plan(saved_plan)
                    for node in ordered_nodes:
                        self._insert_task_node(node)
            except sqlite3.IntegrityError as exc:
                raise PlanStoreError("Plan or PlanTaskNode already exists") from exc
            except sqlite3.Error as exc:
                raise PlanStoreError("failed to create Plan") from exc
        return saved_plan

    def get_plan(self, session_id: str, plan_id: str) -> Plan | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM plans
                WHERE session_id = ? AND plan_id = ?
                """,
                (session_id, plan_id),
            ).fetchone()
            if row is None:
                return None
            task_node_ids = self._task_node_ids(session_id, plan_id)
        return _plan_from_row(row, task_node_ids)

    def list_plans(self, session_id: str) -> list[Plan]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM plans
                WHERE session_id = ?
                ORDER BY created_at ASC, updated_at ASC, plan_id ASC
                """,
                (session_id,),
            ).fetchall()
            return [
                _plan_from_row(row, self._task_node_ids(session_id, str(row["plan_id"])))
                for row in rows
            ]

    def get_active_plan(self, session_id: str) -> Plan | None:
        """Return the newest non-archived Plan for the session.

        PTC-5 does not migrate ``authoring_active_sessions`` yet, so this is a
        conservative read-side convenience for early callers.
        """

        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM plans
                WHERE session_id = ?
                  AND archived_at IS NULL
                  AND status != 'archived'
                ORDER BY updated_at DESC, created_at DESC, plan_id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            task_node_ids = self._task_node_ids(session_id, str(row["plan_id"]))
        return _plan_from_row(row, task_node_ids)

    def save_plan(self, plan: Plan, *, expected_version: int) -> Plan:
        with self._lock:
            current = self.get_plan(plan.session_id, plan.plan_id)
            if current is None:
                raise LookupError(f"Plan {plan.plan_id!r} not found")
            _check_version(current.version, expected_version, plan.plan_id)
            updated = _copy_plan(
                plan,
                version=current.version + 1,
                task_node_ids=current.task_node_ids,
                created_at=current.created_at,
                updated_at=_utcnow(),
            )
            try:
                with self._write_transaction():
                    self._update_plan(updated)
            except sqlite3.Error as exc:
                raise PlanStoreError("failed to save Plan") from exc
        return updated

    def get_task_node(self, session_id: str, task_node_id: str) -> PlanTaskNode | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM plan_task_nodes
                WHERE session_id = ? AND task_node_id = ?
                """,
                (session_id, task_node_id),
            ).fetchone()
        if row is None:
            return None
        return _task_node_from_row(row)

    def list_task_nodes(self, session_id: str, plan_id: str) -> list[PlanTaskNode]:
        with self._lock:
            if self.get_plan(session_id, plan_id) is None:
                raise LookupError(f"Plan {plan_id!r} not found")
            rows = self._conn.execute(
                """
                SELECT * FROM plan_task_nodes
                WHERE session_id = ? AND plan_id = ?
                ORDER BY order_index ASC, task_index ASC, task_node_id ASC
                """,
                (session_id, plan_id),
            ).fetchall()
        return [_task_node_from_row(row) for row in rows]

    def add_task_node(
        self,
        node: PlanTaskNode,
        *,
        expected_plan_version: int | None = None,
    ) -> PlanTaskNode:
        with self._lock:
            plan = self.get_plan(node.session_id, node.plan_id)
            if plan is None:
                raise LookupError(f"Plan {node.plan_id!r} not found")
            if expected_plan_version is not None:
                _check_version(plan.version, expected_plan_version, node.plan_id)
            _validate_node_dependencies(
                (node, *self.list_task_nodes(node.session_id, node.plan_id)),
                allow_forward_refs=False,
            )
            try:
                with self._write_transaction():
                    self._insert_task_node(node)
                    self._update_plan(
                        _copy_plan(
                            plan,
                            version=plan.version + 1,
                            updated_at=_utcnow(),
                        )
                    )
            except sqlite3.IntegrityError as exc:
                raise PlanStoreError("PlanTaskNode already exists") from exc
            except sqlite3.Error as exc:
                raise PlanStoreError("failed to add PlanTaskNode") from exc
        return node

    def save_task_node(
        self,
        node: PlanTaskNode,
        *,
        expected_version: int,
    ) -> PlanTaskNode:
        with self._lock:
            current = self.get_task_node(node.session_id, node.task_node_id)
            if current is None:
                raise LookupError(f"PlanTaskNode {node.task_node_id!r} not found")
            _check_version(current.version, expected_version, node.task_node_id)
            updated = _copy_task_node(
                node,
                version=current.version + 1,
                created_at=current.created_at,
                updated_at=_utcnow(),
            )
            try:
                with self._write_transaction():
                    self._update_task_node(updated)
            except sqlite3.Error as exc:
                raise PlanStoreError("failed to save PlanTaskNode") from exc
        return updated

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

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

    def _task_node_ids(self, session_id: str, plan_id: str) -> tuple[str, ...]:
        rows = self._conn.execute(
            """
            SELECT task_node_id FROM plan_task_nodes
            WHERE session_id = ? AND plan_id = ?
            ORDER BY order_index ASC, task_index ASC, task_node_id ASC
            """,
            (session_id, plan_id),
        ).fetchall()
        return tuple(str(row["task_node_id"]) for row in rows)

    def _insert_plan(self, plan: Plan) -> None:
        self._conn.execute(
            """
            INSERT INTO plans(
                session_id,
                plan_id,
                source_raw_task_id,
                source_draft_tree_id,
                title,
                objective,
                summary,
                status,
                context_policy_json,
                finalization_json,
                outcome_json,
                version,
                created_by,
                created_at,
                updated_at,
                archived_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _plan_values(plan),
        )

    def _update_plan(self, plan: Plan) -> None:
        self._conn.execute(
            """
            UPDATE plans
            SET
                source_raw_task_id = ?,
                source_draft_tree_id = ?,
                title = ?,
                objective = ?,
                summary = ?,
                status = ?,
                context_policy_json = ?,
                finalization_json = ?,
                outcome_json = ?,
                version = ?,
                created_by = ?,
                created_at = ?,
                updated_at = ?,
                archived_at = ?
            WHERE session_id = ? AND plan_id = ?
            """,
            (
                plan.source_raw_task_id,
                plan.source_draft_tree_id,
                plan.title,
                plan.objective,
                plan.summary,
                plan.status,
                plan.context_policy.model_dump_json(),
                plan.finalization.model_dump_json(),
                _optional_model_json(plan.outcome),
                plan.version,
                plan.created_by,
                plan.created_at.isoformat(),
                plan.updated_at.isoformat(),
                _optional_datetime(plan.archived_at),
                plan.session_id,
                plan.plan_id,
            ),
        )

    def _insert_task_node(self, node: PlanTaskNode) -> None:
        self._conn.execute(
            """
            INSERT INTO plan_task_nodes(
                session_id,
                plan_id,
                task_node_id,
                task_index,
                order_index,
                title,
                intent,
                summary,
                instructions,
                required_capability,
                depends_on_json,
                constraints_json,
                acceptance_criteria_json,
                readiness,
                execution,
                draft_ref_json,
                published_ref_json,
                result_ref,
                error_ref,
                file_summary_ref,
                audit_ref,
                version,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _task_node_values(node),
        )

    def _update_task_node(self, node: PlanTaskNode) -> None:
        self._conn.execute(
            """
            UPDATE plan_task_nodes
            SET
                plan_id = ?,
                task_index = ?,
                order_index = ?,
                title = ?,
                intent = ?,
                summary = ?,
                instructions = ?,
                required_capability = ?,
                depends_on_json = ?,
                constraints_json = ?,
                acceptance_criteria_json = ?,
                readiness = ?,
                execution = ?,
                draft_ref_json = ?,
                published_ref_json = ?,
                result_ref = ?,
                error_ref = ?,
                file_summary_ref = ?,
                audit_ref = ?,
                version = ?,
                created_at = ?,
                updated_at = ?
            WHERE session_id = ? AND task_node_id = ?
            """,
            (
                node.plan_id,
                node.task_index,
                node.order_index,
                node.title,
                node.intent,
                node.summary,
                node.instructions,
                node.required_capability,
                _json_dumps(tuple(node.depends_on)),
                _json_dumps(tuple(node.constraints)),
                _json_dumps(tuple(node.acceptance_criteria)),
                node.readiness,
                node.execution,
                _optional_model_json(node.draft_ref),
                _optional_model_json(node.published_ref),
                node.result_ref,
                node.error_ref,
                node.file_summary_ref,
                node.audit_ref,
                node.version,
                node.created_at.isoformat(),
                node.updated_at.isoformat(),
                node.session_id,
                node.task_node_id,
            ),
        )


def _plan_values(plan: Plan) -> tuple[object, ...]:
    return (
        plan.session_id,
        plan.plan_id,
        plan.source_raw_task_id,
        plan.source_draft_tree_id,
        plan.title,
        plan.objective,
        plan.summary,
        plan.status,
        plan.context_policy.model_dump_json(),
        plan.finalization.model_dump_json(),
        _optional_model_json(plan.outcome),
        plan.version,
        plan.created_by,
        plan.created_at.isoformat(),
        plan.updated_at.isoformat(),
        _optional_datetime(plan.archived_at),
    )


def _task_node_values(node: PlanTaskNode) -> tuple[object, ...]:
    return (
        node.session_id,
        node.plan_id,
        node.task_node_id,
        node.task_index,
        node.order_index,
        node.title,
        node.intent,
        node.summary,
        node.instructions,
        node.required_capability,
        _json_dumps(tuple(node.depends_on)),
        _json_dumps(tuple(node.constraints)),
        _json_dumps(tuple(node.acceptance_criteria)),
        node.readiness,
        node.execution,
        _optional_model_json(node.draft_ref),
        _optional_model_json(node.published_ref),
        node.result_ref,
        node.error_ref,
        node.file_summary_ref,
        node.audit_ref,
        node.version,
        node.created_at.isoformat(),
        node.updated_at.isoformat(),
    )


def _plan_from_row(row: sqlite3.Row, task_node_ids: tuple[str, ...]) -> Plan:
    try:
        return Plan.model_validate(
            {
                "session_id": row["session_id"],
                "plan_id": row["plan_id"],
                "source_raw_task_id": row["source_raw_task_id"],
                "source_draft_tree_id": row["source_draft_tree_id"],
                "title": row["title"],
                "objective": row["objective"],
                "summary": row["summary"],
                "status": row["status"],
                "context_policy": PlanContextPolicy.model_validate_json(
                    str(row["context_policy_json"])
                ),
                "finalization": PlanFinalizationState.model_validate_json(
                    str(row["finalization_json"])
                ),
                "outcome": _optional_plan_outcome(row["outcome_json"]),
                "version": row["version"],
                "task_node_ids": task_node_ids,
                "created_by": row["created_by"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "archived_at": row["archived_at"],
            }
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise PlanStoreError("invalid Plan row") from exc


def _task_node_from_row(row: sqlite3.Row) -> PlanTaskNode:
    try:
        return PlanTaskNode.model_validate(
            {
                "session_id": row["session_id"],
                "plan_id": row["plan_id"],
                "task_node_id": row["task_node_id"],
                "task_index": row["task_index"],
                "order_index": row["order_index"],
                "title": row["title"],
                "intent": row["intent"],
                "summary": row["summary"],
                "instructions": row["instructions"],
                "required_capability": row["required_capability"],
                "depends_on": _json_load_tuple(row["depends_on_json"]),
                "constraints": _json_load_tuple(row["constraints_json"]),
                "acceptance_criteria": _json_load_tuple(row["acceptance_criteria_json"]),
                "readiness": row["readiness"],
                "execution": row["execution"],
                "draft_ref": _optional_task_ref(row["draft_ref_json"]),
                "published_ref": _optional_task_ref(row["published_ref_json"]),
                "result_ref": row["result_ref"],
                "error_ref": row["error_ref"],
                "file_summary_ref": row["file_summary_ref"],
                "audit_ref": row["audit_ref"],
                "version": row["version"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise PlanStoreError("invalid PlanTaskNode row") from exc


def _ordered_nodes(nodes: Sequence[PlanTaskNode]) -> tuple[PlanTaskNode, ...]:
    return tuple(
        sorted(
            nodes,
            key=lambda node: (node.order_index, node.task_index, node.task_node_id),
        )
    )


def _validate_plan_nodes(plan: Plan, nodes: Sequence[PlanTaskNode]) -> None:
    seen_ids: set[str] = set()
    seen_indexes: set[str] = set()
    for node in nodes:
        if node.session_id != plan.session_id:
            raise ValueError("PlanTaskNode session_id must match Plan session_id")
        if node.plan_id != plan.plan_id:
            raise ValueError("PlanTaskNode plan_id must match Plan plan_id")
        if node.task_node_id in seen_ids:
            raise ValueError("PlanTaskNode ids must be unique")
        if node.task_index in seen_indexes:
            raise ValueError("PlanTaskNode task_index values must be unique")
        seen_ids.add(node.task_node_id)
        seen_indexes.add(node.task_index)
    _validate_node_dependencies(nodes, allow_forward_refs=False)


def _validate_node_dependencies(
    nodes: Sequence[PlanTaskNode],
    *,
    allow_forward_refs: bool,
) -> None:
    known_ids = {node.task_node_id for node in nodes}
    for node in nodes:
        if not allow_forward_refs:
            unknown = sorted(set(node.depends_on) - known_ids)
            if unknown:
                raise ValueError(f"PlanTaskNode {node.task_node_id!r} has unknown depends_on")
        if node.task_node_id in node.depends_on:
            raise ValueError("PlanTaskNode must not depend on itself")


def _optional_plan_outcome(value: object) -> PlanOutcome | None:
    if value is None:
        return None
    return PlanOutcome.model_validate_json(str(value))


def _optional_task_ref(value: object) -> TaskRef | None:
    if value is None:
        return None
    return TaskRef.model_validate_json(str(value))


def _optional_model_json(model: Any | None) -> str | None:
    if model is None:
        return None
    return str(model.model_dump_json())


def _optional_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _json_dumps(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _json_load_tuple(value: object) -> tuple[str, ...]:
    loaded = json.loads(str(value))
    if not isinstance(loaded, list):
        raise ValueError("stored JSON value must be a list")
    return tuple(str(item) for item in loaded)


def _copy_plan(plan: Plan, **updates: object) -> Plan:
    return Plan.model_validate({**plan.model_dump(), **updates})


def _copy_task_node(node: PlanTaskNode, **updates: object) -> PlanTaskNode:
    return PlanTaskNode.model_validate({**node.model_dump(), **updates})


def _check_version(current: int, expected: int, object_id: str) -> None:
    if current != expected:
        raise VersionConflictError(
            f"stale version for {object_id!r}: expected {expected}, current {current}"
        )


def _utcnow() -> datetime:
    return datetime.now(UTC)


__all__ = ["SqlitePlanStore"]
