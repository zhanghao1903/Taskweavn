"""SQLite-backed stores for RawTask and DraftTaskTree authoring facts."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Self, cast
from uuid import uuid4

from pydantic import ValidationError

from taskweavn.task.authoring import RawTask
from taskweavn.task.models import (
    DraftTaskNode,
    DraftTaskTree,
    DraftToPublishedMapping,
    TaskNodePatch,
)
from taskweavn.task.stores import TaskStoreError, VersionConflictError

_SCHEMA_VERSION = "1"

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS authoring_schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_tasks (
    session_id TEXT NOT NULL,
    raw_task_id TEXT NOT NULL,
    source_message_id TEXT NOT NULL,
    user_input TEXT NOT NULL,
    status TEXT NOT NULL,
    intent_summary TEXT,
    feasibility_json TEXT,
    asks_json TEXT NOT NULL,
    answers_json TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    assumptions_json TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT,
    replaced_by_raw_task_id TEXT,
    PRIMARY KEY (session_id, raw_task_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_tasks_session_updated
    ON raw_tasks(session_id, updated_at, raw_task_id);

CREATE TABLE IF NOT EXISTS draft_task_trees (
    session_id TEXT NOT NULL,
    draft_tree_id TEXT NOT NULL,
    source_raw_task_id TEXT,
    created_by TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT,
    replaced_by_draft_tree_id TEXT,
    PRIMARY KEY (session_id, draft_tree_id)
);

CREATE INDEX IF NOT EXISTS idx_draft_task_trees_session_updated
    ON draft_task_trees(session_id, updated_at, draft_tree_id);

CREATE TABLE IF NOT EXISTS draft_task_nodes (
    session_id TEXT NOT NULL,
    draft_tree_id TEXT NOT NULL,
    draft_task_id TEXT NOT NULL,
    parent_draft_task_id TEXT,
    order_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    intent TEXT NOT NULL,
    required_capability TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    rationale TEXT,
    status TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (session_id, draft_task_id)
);

CREATE INDEX IF NOT EXISTS idx_draft_task_nodes_tree_order
    ON draft_task_nodes(
        session_id,
        draft_tree_id,
        parent_draft_task_id,
        order_index,
        draft_task_id
    );

CREATE TABLE IF NOT EXISTS draft_to_published_mappings (
    session_id TEXT NOT NULL,
    draft_tree_id TEXT NOT NULL,
    draft_task_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    published_at TEXT NOT NULL,
    publish_command_id TEXT NOT NULL,
    PRIMARY KEY (session_id, draft_task_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_draft_mapping_task
    ON draft_to_published_mappings(session_id, task_id);
"""


class AuthoringStoreError(TaskStoreError):
    """Raised for durable authoring store failures."""


class _SqliteAuthoringStore:
    """Shared SQLite connection and schema initialization for authoring stores."""

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
        self._conn.execute(
            """
            INSERT INTO authoring_schema_meta(key, value, updated_at)
            VALUES('schema_version', ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (_SCHEMA_VERSION, _utcnow().isoformat()),
        )
        self._lock = RLock()

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
        with self._lock:
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


class SqliteRawTaskStore(_SqliteAuthoringStore):
    """SQLite-backed RawTaskStore implementation."""

    def create(self, raw_task: RawTask) -> RawTask:
        with self._lock:
            if self.get(raw_task.session_id, raw_task.raw_task_id) is not None:
                raise AuthoringStoreError(
                    f"RawTask {raw_task.raw_task_id!r} already exists"
                )
            try:
                with self._write_transaction():
                    self._insert_raw_task(raw_task)
            except sqlite3.Error as exc:
                raise AuthoringStoreError("failed to create RawTask") from exc
            return raw_task

    def get(self, session_id: str, raw_task_id: str) -> RawTask | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM raw_tasks
                WHERE session_id = ? AND raw_task_id = ?
                """,
                (session_id, raw_task_id),
            ).fetchone()
        if row is None:
            return None
        return _raw_task_from_row(row)

    def list_for_session(self, session_id: str) -> list[RawTask]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM raw_tasks
                WHERE session_id = ?
                ORDER BY created_at ASC, updated_at ASC, raw_task_id ASC
                """,
                (session_id,),
            ).fetchall()
        return [_raw_task_from_row(row) for row in rows]

    def save(self, raw_task: RawTask, *, expected_version: int) -> RawTask:
        with self._lock:
            current = self.get(raw_task.session_id, raw_task.raw_task_id)
            if current is None:
                raise LookupError(f"RawTask {raw_task.raw_task_id!r} not found")
            _check_version(current.version, expected_version, raw_task.raw_task_id)
            updated = _copy_raw_task(
                raw_task,
                version=current.version + 1,
                created_at=current.created_at,
                updated_at=_utcnow(),
            )
            try:
                with self._write_transaction():
                    self._update_raw_task(updated)
            except sqlite3.Error as exc:
                raise AuthoringStoreError("failed to save RawTask") from exc
            return updated

    def _insert_raw_task(self, raw_task: RawTask) -> None:
        self._conn.execute(
            """
            INSERT INTO raw_tasks(
                session_id,
                raw_task_id,
                source_message_id,
                user_input,
                status,
                intent_summary,
                feasibility_json,
                asks_json,
                answers_json,
                constraints_json,
                assumptions_json,
                version,
                created_by,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _raw_task_values(raw_task),
        )

    def _update_raw_task(self, raw_task: RawTask) -> None:
        self._conn.execute(
            """
            UPDATE raw_tasks
            SET
                source_message_id = ?,
                user_input = ?,
                status = ?,
                intent_summary = ?,
                feasibility_json = ?,
                asks_json = ?,
                answers_json = ?,
                constraints_json = ?,
                assumptions_json = ?,
                version = ?,
                created_by = ?,
                created_at = ?,
                updated_at = ?
            WHERE session_id = ? AND raw_task_id = ?
            """,
            (
                raw_task.source_message_id,
                raw_task.user_input,
                raw_task.status,
                raw_task.intent_summary,
                _model_json(raw_task.feasibility),
                _model_tuple_json(raw_task.asks),
                _model_tuple_json(raw_task.answers),
                _json_dumps(tuple(raw_task.constraints)),
                _json_dumps(tuple(raw_task.assumptions)),
                raw_task.version,
                raw_task.created_by,
                raw_task.created_at.isoformat(),
                raw_task.updated_at.isoformat(),
                raw_task.session_id,
                raw_task.raw_task_id,
            ),
        )


class SqliteDraftTaskStore(_SqliteAuthoringStore):
    """SQLite-backed DraftTaskStore implementation."""

    def create_tree(self, session_id: str, roots: list[DraftTaskNode]) -> DraftTaskTree:
        if not roots:
            raise ValueError("draft tree requires at least one root")
        draft_tree_id = uuid4().hex
        normalized_roots = tuple(
            _copy_node(
                root,
                session_id=session_id,
                draft_tree_id=draft_tree_id,
                parent_draft_task_id=None,
            )
            for root in roots
        )
        tree = DraftTaskTree(
            session_id=session_id,
            draft_tree_id=draft_tree_id,
            root_nodes=_sort_nodes(normalized_roots),
            created_by=normalized_roots[0].created_by,
        )
        with self._lock:
            try:
                with self._write_transaction():
                    self._insert_tree(tree)
                    for node in tree.root_nodes:
                        self._insert_node(node)
            except sqlite3.IntegrityError as exc:
                raise AuthoringStoreError("DraftTaskTree or DraftTaskNode already exists") from exc
            except sqlite3.Error as exc:
                raise AuthoringStoreError("failed to create DraftTaskTree") from exc
            return tree

    def get_tree(self, session_id: str, draft_tree_id: str) -> DraftTaskTree:
        with self._lock:
            row = self._tree_row(session_id, draft_tree_id)
            if row is None:
                raise LookupError(f"DraftTaskTree {draft_tree_id!r} not found")
            return self._tree_from_row(row)

    def list_trees(self, session_id: str) -> list[DraftTaskTree]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM draft_task_trees
                WHERE session_id = ?
                ORDER BY created_at ASC, draft_tree_id ASC
                """,
                (session_id,),
            ).fetchall()
            return [self._tree_from_row(row) for row in rows]

    def list_nodes(self, session_id: str, draft_tree_id: str) -> list[DraftTaskNode]:
        with self._lock:
            if self._tree_row(session_id, draft_tree_id) is None:
                raise LookupError(f"DraftTaskTree {draft_tree_id!r} not found")
            rows = self._conn.execute(
                """
                SELECT * FROM draft_task_nodes
                WHERE session_id = ? AND draft_tree_id = ?
                ORDER BY
                    COALESCE(parent_draft_task_id, '') ASC,
                    order_index ASC,
                    created_at ASC,
                    draft_task_id ASC
                """,
                (session_id, draft_tree_id),
            ).fetchall()
        return [_node_from_row(row) for row in rows]

    def list_children(
        self,
        session_id: str,
        draft_tree_id: str,
        parent_draft_task_id: str | None,
    ) -> list[DraftTaskNode]:
        with self._lock:
            if self._tree_row(session_id, draft_tree_id) is None:
                raise LookupError(f"DraftTaskTree {draft_tree_id!r} not found")
            if parent_draft_task_id is not None:
                parent = self.get_node(session_id, parent_draft_task_id)
                if parent is None or parent.draft_tree_id != draft_tree_id:
                    raise LookupError(f"DraftTaskNode {parent_draft_task_id!r} not found")
            return self._children(session_id, draft_tree_id, parent_draft_task_id)

    def get_node(self, session_id: str, draft_task_id: str) -> DraftTaskNode | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM draft_task_nodes
                WHERE session_id = ? AND draft_task_id = ?
                """,
                (session_id, draft_task_id),
            ).fetchone()
        if row is None:
            return None
        return _node_from_row(row)

    def add_node(
        self,
        session_id: str,
        draft_tree_id: str,
        node: DraftTaskNode,
        *,
        expected_tree_version: int,
    ) -> DraftTaskNode:
        now = _utcnow()
        with self._lock:
            row = self._tree_row(session_id, draft_tree_id)
            if row is None:
                raise LookupError(f"DraftTaskTree {draft_tree_id!r} not found")
            _check_version(int(row["version"]), expected_tree_version, draft_tree_id)
            if self.get_node(session_id, node.draft_task_id) is not None:
                raise AuthoringStoreError(
                    f"DraftTaskNode {node.draft_task_id!r} already exists"
                )
            if node.parent_draft_task_id is not None:
                parent = self.get_node(session_id, node.parent_draft_task_id)
                if parent is None or parent.draft_tree_id != draft_tree_id:
                    raise LookupError(
                        f"parent DraftTaskNode {node.parent_draft_task_id!r} not found"
                    )
            normalized = _copy_node(
                node,
                session_id=session_id,
                draft_tree_id=draft_tree_id,
                created_at=now,
                updated_at=now,
            )
            try:
                with self._write_transaction():
                    self._insert_node(normalized)
                    self._bump_tree(session_id, draft_tree_id)
            except sqlite3.IntegrityError as exc:
                raise AuthoringStoreError(
                    f"DraftTaskNode {node.draft_task_id!r} already exists"
                ) from exc
            except sqlite3.Error as exc:
                raise AuthoringStoreError("failed to add DraftTaskNode") from exc
            return normalized

    def update_node(
        self,
        session_id: str,
        draft_task_id: str,
        patch: TaskNodePatch,
        *,
        expected_version: int,
    ) -> DraftTaskNode:
        with self._lock:
            node = self.get_node(session_id, draft_task_id)
            if node is None:
                raise LookupError(f"DraftTaskNode {draft_task_id!r} not found")
            if node.status != "draft":
                raise AuthoringStoreError(
                    f"draft task cannot be edited while status is {node.status}"
                )
            if patch.children_ops:
                raise AuthoringStoreError(
                    "children_ops are handled by explicit tree operations"
                )
            if patch.status == "published":
                raise AuthoringStoreError(
                    "published status must be set through mark_published"
                )
            _check_version(node.version, expected_version, draft_task_id)
            updated = _copy_node(
                node,
                title=patch.title or node.title,
                intent=patch.intent or node.intent,
                required_capability=patch.required_capability or node.required_capability,
                constraints=_patched_constraints(node, patch),
                status=patch.status or node.status,
                version=node.version + 1,
                updated_at=_utcnow(),
            )
            try:
                with self._write_transaction():
                    self._update_node(updated)
                    self._bump_tree(session_id, node.draft_tree_id)
            except sqlite3.Error as exc:
                raise AuthoringStoreError("failed to update DraftTaskNode") from exc
            return updated

    def mark_accepted(
        self,
        session_id: str,
        draft_tree_id: str,
        *,
        expected_version: int,
    ) -> DraftTaskTree:
        with self._lock:
            row = self._tree_row(session_id, draft_tree_id)
            if row is None:
                raise LookupError(f"DraftTaskTree {draft_tree_id!r} not found")
            _check_version(int(row["version"]), expected_version, draft_tree_id)
            nodes = self.list_nodes(session_id, draft_tree_id)
            for node in nodes:
                if node.status not in {"draft", "accepted"}:
                    raise AuthoringStoreError(
                        f"cannot accept draft tree with {node.status} node "
                        f"{node.draft_task_id!r}"
                    )
            try:
                with self._write_transaction():
                    for node in nodes:
                        if node.status == "draft":
                            self._update_node(
                                _copy_node(
                                    node,
                                    status="accepted",
                                    version=node.version + 1,
                                    updated_at=_utcnow(),
                                )
                            )
                    return self._bump_tree(session_id, draft_tree_id)
            except sqlite3.Error as exc:
                raise AuthoringStoreError("failed to accept DraftTaskTree") from exc

    def mark_published(
        self,
        session_id: str,
        draft_tree_id: str,
        mappings: list[DraftToPublishedMapping],
        *,
        expected_version: int | None = None,
    ) -> DraftTaskTree:
        with self._lock:
            row = self._tree_row(session_id, draft_tree_id)
            if row is None:
                raise LookupError(f"DraftTaskTree {draft_tree_id!r} not found")
            if expected_version is not None:
                _check_version(int(row["version"]), expected_version, draft_tree_id)
            nodes = self.list_nodes(session_id, draft_tree_id)
            node_ids = {node.draft_task_id for node in nodes}
            for node in nodes:
                if node.status == "cancelled":
                    raise AuthoringStoreError(
                        f"cannot publish cancelled node {node.draft_task_id!r}"
                    )
            for mapping in mappings:
                if mapping.session_id != session_id or mapping.draft_tree_id != draft_tree_id:
                    raise ValueError("mapping session_id and draft_tree_id must match tree")
                if mapping.draft_task_id not in node_ids:
                    raise LookupError(
                        f"mapped DraftTaskNode {mapping.draft_task_id!r} not found"
                    )
            try:
                with self._write_transaction():
                    for node in nodes:
                        if node.status != "published":
                            self._update_node(
                                _copy_node(
                                    node,
                                    status="published",
                                    version=node.version + 1,
                                    updated_at=_utcnow(),
                                )
                            )
                    for mapping in mappings:
                        self._insert_mapping(mapping)
                    return self._bump_tree(session_id, draft_tree_id)
            except sqlite3.Error as exc:
                raise AuthoringStoreError("failed to publish DraftTaskTree") from exc

    def list_for_draft(
        self,
        session_id: str,
        draft_task_id: str,
    ) -> list[DraftToPublishedMapping]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM draft_to_published_mappings
                WHERE session_id = ? AND draft_task_id = ?
                ORDER BY published_at ASC, publish_command_id ASC, task_id ASC
                """,
                (session_id, draft_task_id),
            ).fetchall()
        return [_mapping_from_row(row) for row in rows]

    def list_for_task(
        self,
        session_id: str,
        task_id: str,
    ) -> list[DraftToPublishedMapping]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM draft_to_published_mappings
                WHERE session_id = ? AND task_id = ?
                ORDER BY published_at ASC, publish_command_id ASC, draft_task_id ASC
                """,
                (session_id, task_id),
            ).fetchall()
        return [_mapping_from_row(row) for row in rows]

    def _tree_row(self, session_id: str, draft_tree_id: str) -> sqlite3.Row | None:
        row = self._conn.execute(
            """
            SELECT * FROM draft_task_trees
            WHERE session_id = ? AND draft_tree_id = ?
            """,
            (session_id, draft_tree_id),
        ).fetchone()
        return cast("sqlite3.Row | None", row)

    def _tree_from_row(self, row: sqlite3.Row) -> DraftTaskTree:
        roots = self._children(str(row["session_id"]), str(row["draft_tree_id"]), None)
        return _tree_from_row(row, roots)

    def _children(
        self,
        session_id: str,
        draft_tree_id: str,
        parent_draft_task_id: str | None,
    ) -> list[DraftTaskNode]:
        if parent_draft_task_id is None:
            rows = self._conn.execute(
                """
                SELECT * FROM draft_task_nodes
                WHERE session_id = ?
                  AND draft_tree_id = ?
                  AND parent_draft_task_id IS NULL
                ORDER BY order_index ASC, created_at ASC, draft_task_id ASC
                """,
                (session_id, draft_tree_id),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM draft_task_nodes
                WHERE session_id = ?
                  AND draft_tree_id = ?
                  AND parent_draft_task_id = ?
                ORDER BY order_index ASC, created_at ASC, draft_task_id ASC
                """,
                (session_id, draft_tree_id, parent_draft_task_id),
            ).fetchall()
        return [_node_from_row(row) for row in rows]

    def _insert_tree(self, tree: DraftTaskTree) -> None:
        self._conn.execute(
            """
            INSERT INTO draft_task_trees(
                session_id,
                draft_tree_id,
                created_by,
                version,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                tree.session_id,
                tree.draft_tree_id,
                tree.created_by,
                tree.version,
                tree.created_at.isoformat(),
                tree.updated_at.isoformat(),
            ),
        )

    def _insert_node(self, node: DraftTaskNode) -> None:
        self._conn.execute(
            """
            INSERT INTO draft_task_nodes(
                session_id,
                draft_tree_id,
                draft_task_id,
                parent_draft_task_id,
                order_index,
                title,
                intent,
                required_capability,
                constraints_json,
                rationale,
                status,
                version,
                created_by,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _node_values(node),
        )

    def _update_node(self, node: DraftTaskNode) -> None:
        self._conn.execute(
            """
            UPDATE draft_task_nodes
            SET
                draft_tree_id = ?,
                parent_draft_task_id = ?,
                order_index = ?,
                title = ?,
                intent = ?,
                required_capability = ?,
                constraints_json = ?,
                rationale = ?,
                status = ?,
                version = ?,
                created_by = ?,
                created_at = ?,
                updated_at = ?
            WHERE session_id = ? AND draft_task_id = ?
            """,
            (
                node.draft_tree_id,
                node.parent_draft_task_id,
                node.order_index,
                node.title,
                node.intent,
                node.required_capability,
                _json_dumps(tuple(node.constraints)),
                node.rationale,
                node.status,
                node.version,
                node.created_by,
                node.created_at.isoformat(),
                node.updated_at.isoformat(),
                node.session_id,
                node.draft_task_id,
            ),
        )

    def _insert_mapping(self, mapping: DraftToPublishedMapping) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO draft_to_published_mappings(
                session_id,
                draft_tree_id,
                draft_task_id,
                task_id,
                published_at,
                publish_command_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                mapping.session_id,
                mapping.draft_tree_id,
                mapping.draft_task_id,
                mapping.task_id,
                mapping.published_at.isoformat(),
                mapping.publish_command_id,
            ),
        )

    def _bump_tree(self, session_id: str, draft_tree_id: str) -> DraftTaskTree:
        row = self._tree_row(session_id, draft_tree_id)
        if row is None:
            raise LookupError(f"DraftTaskTree {draft_tree_id!r} not found")
        updated_at = _utcnow()
        self._conn.execute(
            """
            UPDATE draft_task_trees
            SET version = ?, updated_at = ?
            WHERE session_id = ? AND draft_tree_id = ?
            """,
            (
                int(row["version"]) + 1,
                updated_at.isoformat(),
                session_id,
                draft_tree_id,
            ),
        )
        updated_row = self._tree_row(session_id, draft_tree_id)
        if updated_row is None:
            raise LookupError(f"DraftTaskTree {draft_tree_id!r} not found")
        return self._tree_from_row(updated_row)


def _raw_task_values(raw_task: RawTask) -> tuple[Any, ...]:
    return (
        raw_task.session_id,
        raw_task.raw_task_id,
        raw_task.source_message_id,
        raw_task.user_input,
        raw_task.status,
        raw_task.intent_summary,
        _model_json(raw_task.feasibility),
        _model_tuple_json(raw_task.asks),
        _model_tuple_json(raw_task.answers),
        _json_dumps(tuple(raw_task.constraints)),
        _json_dumps(tuple(raw_task.assumptions)),
        raw_task.version,
        raw_task.created_by,
        raw_task.created_at.isoformat(),
        raw_task.updated_at.isoformat(),
    )


def _node_values(node: DraftTaskNode) -> tuple[Any, ...]:
    return (
        node.session_id,
        node.draft_tree_id,
        node.draft_task_id,
        node.parent_draft_task_id,
        node.order_index,
        node.title,
        node.intent,
        node.required_capability,
        _json_dumps(tuple(node.constraints)),
        node.rationale,
        node.status,
        node.version,
        node.created_by,
        node.created_at.isoformat(),
        node.updated_at.isoformat(),
    )


def _raw_task_from_row(row: sqlite3.Row) -> RawTask:
    try:
        return RawTask.model_validate(
            {
                "session_id": row["session_id"],
                "raw_task_id": row["raw_task_id"],
                "source_message_id": row["source_message_id"],
                "user_input": row["user_input"],
                "status": row["status"],
                "intent_summary": row["intent_summary"],
                "feasibility": _json_load_optional(row["feasibility_json"]),
                "asks": _json_load_list(row["asks_json"]),
                "answers": _json_load_list(row["answers_json"]),
                "constraints": _json_load_list(row["constraints_json"]),
                "assumptions": _json_load_list(row["assumptions_json"]),
                "version": row["version"],
                "created_by": row["created_by"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise AuthoringStoreError("invalid RawTask row") from exc


def _node_from_row(row: sqlite3.Row) -> DraftTaskNode:
    try:
        return DraftTaskNode.model_validate(
            {
                "session_id": row["session_id"],
                "draft_tree_id": row["draft_tree_id"],
                "draft_task_id": row["draft_task_id"],
                "parent_draft_task_id": row["parent_draft_task_id"],
                "order_index": row["order_index"],
                "title": row["title"],
                "intent": row["intent"],
                "required_capability": row["required_capability"],
                "constraints": _json_load_list(row["constraints_json"]),
                "rationale": row["rationale"],
                "status": row["status"],
                "version": row["version"],
                "created_by": row["created_by"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise AuthoringStoreError("invalid DraftTaskNode row") from exc


def _tree_from_row(row: sqlite3.Row, roots: list[DraftTaskNode]) -> DraftTaskTree:
    try:
        return DraftTaskTree.model_validate(
            {
                "session_id": row["session_id"],
                "draft_tree_id": row["draft_tree_id"],
                "root_nodes": _sort_nodes(roots),
                "created_by": row["created_by"],
                "version": row["version"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise AuthoringStoreError("invalid DraftTaskTree row") from exc


def _mapping_from_row(row: sqlite3.Row) -> DraftToPublishedMapping:
    try:
        return DraftToPublishedMapping.model_validate(
            {
                "session_id": row["session_id"],
                "draft_tree_id": row["draft_tree_id"],
                "draft_task_id": row["draft_task_id"],
                "task_id": row["task_id"],
                "published_at": row["published_at"],
                "publish_command_id": row["publish_command_id"],
            }
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise AuthoringStoreError("invalid DraftToPublishedMapping row") from exc


def _model_json(model: Any | None) -> str | None:
    if model is None:
        return None
    return str(model.model_dump_json())


def _model_tuple_json(models: Iterable[Any]) -> str:
    return _json_dumps(tuple(model.model_dump(mode="json") for model in models))


def _json_dumps(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _json_load_optional(value: str | None) -> Any | None:
    if value is None:
        return None
    return json.loads(value)


def _json_load_list(value: str) -> list[Any]:
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        raise ValueError("stored JSON value must be a list")
    return loaded


def _check_version(current: int, expected: int, object_id: str) -> None:
    if current != expected:
        raise VersionConflictError(
            f"stale version for {object_id!r}: expected {expected}, current {current}"
        )


def _copy_raw_task(raw_task: RawTask, **updates: object) -> RawTask:
    return RawTask.model_validate({**raw_task.model_dump(), **updates})


def _copy_node(node: DraftTaskNode, **updates: object) -> DraftTaskNode:
    return DraftTaskNode.model_validate({**node.model_dump(), **updates})


def _sort_nodes(nodes: Iterable[DraftTaskNode]) -> tuple[DraftTaskNode, ...]:
    return tuple(
        sorted(
            nodes,
            key=lambda node: (
                node.parent_draft_task_id or "",
                node.order_index,
                node.created_at,
                node.draft_task_id,
            ),
        )
    )


def _patched_constraints(node: DraftTaskNode, patch: TaskNodePatch) -> tuple[str, ...]:
    removed = set(patch.constraints_remove)
    constraints = [
        constraint for constraint in node.constraints if constraint not in removed
    ]
    for constraint in patch.constraints_add:
        if constraint not in constraints:
            constraints.append(constraint)
    return tuple(constraints)


def _utcnow() -> datetime:
    return datetime.now(UTC)


__all__ = [
    "AuthoringStoreError",
    "SqliteDraftTaskStore",
    "SqliteRawTaskStore",
]
