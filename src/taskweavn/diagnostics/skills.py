"""Skill governance diagnostic projection."""

from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from taskweavn.context.models import ContextTrace

SKILL_GOVERNANCE_DIAGNOSTIC_SCHEMA_VERSION = (
    "plato.skill_governance.diagnostic_summary.v1"
)


def collect_skill_governance_summary(
    *,
    context_db_path: Path,
    session_id: str,
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Return redaction-ready skill activation metadata from context traces."""

    if not context_db_path.exists():
        return None, ("context store is not present",)
    try:
        traces = _read_context_traces(context_db_path, session_id)
    except sqlite3.Error as exc:
        return None, (f"context store could not be read: {exc}",)

    active_skills: list[dict[str, Any]] = []
    permission_outcomes: Counter[str] = Counter()
    for trace in traces:
        for outcome in trace.skill_permission_outcomes:
            permission_outcomes[outcome.kind] += 1
        for skill_trace in trace.skill_traces:
            active_skills.append(
                {
                    "traceId": trace.trace_id,
                    "snapshotId": trace.snapshot_id,
                    "taskId": trace.task_id,
                    "skillId": skill_trace.skill_id,
                    "activationId": skill_trace.activation_id,
                    "contentHash": skill_trace.content_hash,
                    "activationReason": skill_trace.activation_reason,
                    "sourceRef": skill_trace.source_ref,
                    "segmentHash": skill_trace.segment_hash,
                    "truncated": skill_trace.truncated,
                    "truncationReason": skill_trace.truncation_reason,
                    "permissionOutcomes": [
                        {
                            "kind": outcome.kind,
                            "tool": outcome.tool,
                            "reason": outcome.reason,
                        }
                        for outcome in trace.skill_permission_outcomes
                        if outcome.skill_id == skill_trace.skill_id
                    ],
                }
            )

    return (
        {
            "schemaVersion": SKILL_GOVERNANCE_DIAGNOSTIC_SCHEMA_VERSION,
            "sessionId": session_id,
            "traceCount": len(traces),
            "activeSkillCount": len(active_skills),
            "activeSkills": active_skills,
            "permissionOutcomeCounts": dict(sorted(permission_outcomes.items())),
        },
        (),
    )


def _read_context_traces(context_db_path: Path, session_id: str) -> tuple[ContextTrace, ...]:
    conn = sqlite3.connect(str(context_db_path))
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT payload FROM context_traces
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
    finally:
        conn.close()
    return tuple(ContextTrace.model_validate_json(str(row["payload"])) for row in rows)
