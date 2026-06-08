"""Tests for Collaborator authoring evidence contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from taskweavn.task import (
    AuthoringEvidenceRecord,
    AuthoringEvidenceStore,
)


class _FakeAuthoringEvidenceStore:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], AuthoringEvidenceRecord] = {}

    def put(self, record: AuthoringEvidenceRecord) -> AuthoringEvidenceRecord:
        self._records[(record.session_id, record.evidence_id)] = record
        return record

    def get(
        self,
        session_id: str,
        evidence_id: str,
    ) -> AuthoringEvidenceRecord | None:
        return self._records.get((session_id, evidence_id))

    def list_for_loop(
        self,
        session_id: str,
        loop_id: str,
    ) -> tuple[AuthoringEvidenceRecord, ...]:
        return tuple(
            record
            for record in self._records.values()
            if record.session_id == session_id and record.loop_id == loop_id
        )

    def list_for_session(self, session_id: str) -> tuple[AuthoringEvidenceRecord, ...]:
        return tuple(
            record
            for record in self._records.values()
            if record.session_id == session_id
        )


def test_authoring_evidence_store_protocol_conformance() -> None:
    store = _FakeAuthoringEvidenceStore()
    record = AuthoringEvidenceRecord(
        session_id="s1",
        loop_id="loop-1",
        operation="read_workspace",
        tool_name="authoring_read_workspace",
        purpose="Inspect guidance",
        path_label="workspace://current/README.md",
        content_hash="sha256:abc",
        snippet="Project guidance",
        policy_decision="allowed",
    )

    stored = store.put(record)

    assert isinstance(store, AuthoringEvidenceStore)
    assert stored == record
    assert store.get("s1", record.evidence_id) == record
    assert store.list_for_loop("s1", "loop-1") == (record,)
    assert store.list_for_session("s1") == (record,)


def test_authoring_evidence_requires_safe_workspace_label() -> None:
    with pytest.raises(ValidationError, match="workspace://current"):
        AuthoringEvidenceRecord(
            session_id="s1",
            loop_id="loop-1",
            operation="read_workspace",
            tool_name="authoring_read_workspace",
            purpose="Inspect guidance",
            path_label="/Users/example/project/README.md",
            snippet="Project guidance",
            policy_decision="allowed",
        )


def test_authoring_evidence_omission_rules_are_explicit() -> None:
    with pytest.raises(ValidationError, match="omitted_reason"):
        AuthoringEvidenceRecord(
            session_id="s1",
            loop_id="loop-1",
            operation="search_workspace",
            tool_name="authoring_search_workspace",
            purpose="Search guidance",
            path_label="workspace://current/docs",
            policy_decision="omitted",
        )

    with pytest.raises(ValidationError, match="allowed evidence"):
        AuthoringEvidenceRecord(
            session_id="s1",
            loop_id="loop-1",
            operation="read_workspace",
            tool_name="authoring_read_workspace",
            purpose="Inspect guidance",
            path_label="workspace://current/README.md",
            snippet="Project guidance",
            omitted_reason="not needed",
            policy_decision="allowed",
        )
