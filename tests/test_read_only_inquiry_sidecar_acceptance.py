"""Real sidecar acceptance for Read-Only Inquiry Context."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from taskweavn.llm import ChatResponse
from tests.fixtures.sidecar_smoke import (
    SMOKE_INSPECTION_FILE_PATH,
    build_audit_sidecar_smoke_fixture,
)


def test_read_only_inquiry_sidecar_acceptance_no_mutation(
    tmp_path: Path,
) -> None:
    fixture = build_audit_sidecar_smoke_fixture(
        tmp_path,
        include_runtime_input_interactions=False,
    )
    target = tmp_path / SMOKE_INSPECTION_FILE_PATH
    before_content = target.read_text(encoding="utf-8")
    before_task = fixture.app.task_bus.get(fixture.session_id, fixture.task_id)
    assert before_task is not None
    before_task_payload = before_task.model_dump(mode="json")

    try:
        response = fixture.request(
            "POST",
            (
                f"/api/v1/workspaces/{quote(fixture.workspace_id, safe='')}"
                f"/sessions/{quote(fixture.session_id, safe='')}"
                "/runtime-input/route"
            ),
            body={
                "commandId": "route-read-only-sidecar-acceptance",
                "sessionId": fixture.session_id,
                "content": (
                    "What changed in the diagnostics summary and what support "
                    "diagnostics should I inspect?"
                ),
                "mode": "ask",
                "selection": {
                    "scopeKind": "session",
                },
                "inquiryRefs": [
                    {
                        "kind": "file",
                        "path": fixture.inspection_file_path,
                        "label": fixture.inspection_file_path,
                    },
                    {
                        "kind": "diff",
                        "path": fixture.inspection_file_path,
                        "label": fixture.inspection_file_path,
                    },
                    {
                        "kind": "audit_record",
                        "id": fixture.log_record_id,
                        "label": "Frontend error log record",
                    },
                    {
                        "kind": "audit_evidence",
                        "evidenceId": fixture.log_evidence_id,
                        "label": "Frontend error log evidence",
                    },
                    {
                        "kind": "result",
                        "id": fixture.result_id,
                        "label": "Task execution result",
                    },
                    {
                        "kind": "diagnostic",
                        "id": "diagnostic:bundle_export",
                        "label": "Diagnostic bundle export",
                    },
                ],
            },
        )
        activity_response = fixture.request(
            "GET",
            f"/api/v1/sessions/{quote(fixture.session_id, safe='')}/activity",
        )
        after_content = target.read_text(encoding="utf-8")
        after_task = fixture.app.task_bus.get(fixture.session_id, fixture.task_id)
    finally:
        fixture.close()

    assert after_task is not None
    assert response.status == 200
    body = response.json
    assert body["ok"] is True
    data = body["data"]
    assert data["outcome"]["status"] == "answered"
    assert data["decision"]["sideEffect"] == "no_effect"
    assert data["decision"]["dispatchTarget"] == "read_only_inquiry"

    inquiry = data["inquiryResult"]
    evidence_kinds = [ref["kind"] for ref in inquiry["evidenceRefs"]]
    assert "file_snapshot" in evidence_kinds
    assert "diff_snapshot" in evidence_kinds
    assert "audit_record" in evidence_kinds
    assert "audit_evidence" in evidence_kinds
    assert "result_summary" in evidence_kinds
    assert "diagnostic_summary" in evidence_kinds
    audit_evidence_refs = [
        ref for ref in inquiry["evidenceRefs"] if ref["kind"] == "audit_evidence"
    ]
    assert audit_evidence_refs
    assert audit_evidence_refs[0]["refId"] == fixture.log_evidence_id
    assert audit_evidence_refs[0]["parentRefId"] == fixture.log_record_id
    assert "Result 'Task result': Provider rate limit" in (
        inquiry["answer"]["body"]
    )
    assert "Diagnostic support 'Diagnostic bundle export'" in inquiry["answer"]["body"]
    assert str(tmp_path) not in inquiry["answer"]["body"]
    assert "/Users/" not in inquiry["answer"]["body"]

    related_refs = data["activity"]["relatedRefs"]
    hrefs = [ref.get("href") for ref in related_refs if ref.get("href")]
    assert any(
        href.startswith(
            f"/workspaces/{fixture.workspace_id}/inspection"
            f"?path={fixture.inspection_file_path}"
        )
        and "view=file" in href
        for href in hrefs
    )
    assert any(
        href.startswith(
            f"/workspaces/{fixture.workspace_id}/inspection"
            f"?path={fixture.inspection_file_path}"
        )
        and "view=diff" in href
        for href in hrefs
    )
    assert any(
        f"/sessions/{fixture.session_id}/audit?entry=from_session" in href
        and f"recordId={fixture.log_record_id}" in href
        and f"workspaceId={fixture.workspace_id}" in href
        for href in hrefs
    )
    assert any(
        f"/sessions/{fixture.session_id}/audit?entry=from_session" in href
        and f"recordId={fixture.log_record_id}" in href
        and f"evidenceId={fixture.log_evidence_id}" in href
        and f"workspaceId={fixture.workspace_id}" in href
        for href in hrefs
    )

    assert after_content == before_content
    assert after_task.model_dump(mode="json") == before_task_payload

    assert activity_response.status == 200
    activity_items = activity_response.json["data"]["items"]
    replayed = [
        item
        for item in activity_items
        if item["id"] == "activity:inquiry:route-read-only-sidecar-acceptance"
    ]
    assert replayed
    assert replayed[0]["kind"] == "answer"
    assert replayed[0]["sideEffect"] == "no_effect"
    replayed_hrefs = [
        ref.get("href") for ref in replayed[0]["relatedRefs"] if ref.get("href")
    ]
    assert any(ref["kind"] == "file" for ref in replayed[0]["relatedRefs"])
    assert any(ref["kind"] == "audit" for ref in replayed[0]["relatedRefs"])
    assert any(ref["kind"] == "result" for ref in replayed[0]["relatedRefs"])
    assert any(
        f"recordId={fixture.log_record_id}" in href
        and f"evidenceId={fixture.log_evidence_id}" in href
        for href in replayed_hrefs
    )


def test_read_only_inquiry_sidecar_acceptance_opt_in_llm_no_mutation(
    tmp_path: Path,
) -> None:
    llm = _InquiryLLM()
    fixture = build_audit_sidecar_smoke_fixture(
        tmp_path,
        llm=llm,
        enable_read_only_inquiry_llm=True,
        include_runtime_input_interactions=False,
    )
    target = tmp_path / SMOKE_INSPECTION_FILE_PATH
    before_content = target.read_text(encoding="utf-8")
    before_task = fixture.app.task_bus.get(fixture.session_id, fixture.task_id)
    assert before_task is not None
    before_task_payload = before_task.model_dump(mode="json")
    command_id = "route-read-only-sidecar-llm-acceptance"
    cited_refs = [
        f"session:{fixture.session_id}:status",
        fixture.inspection_file_path,
        fixture.log_record_id,
        fixture.result_id,
        "diagnostic:bundle_export",
    ]
    llm.content = json.dumps(
        {
            "status": "answered",
            "body": (
                "LLM rendered a read-only answer from cited safe evidence only."
            ),
            "confidence": "high",
            "citedRefIds": cited_refs,
        }
    )

    try:
        response = fixture.request(
            "POST",
            (
                f"/api/v1/workspaces/{quote(fixture.workspace_id, safe='')}"
                f"/sessions/{quote(fixture.session_id, safe='')}"
                "/runtime-input/route"
            ),
            body={
                "commandId": command_id,
                "sessionId": fixture.session_id,
                "content": (
                    "Use the selected evidence to answer what support should inspect."
                ),
                "mode": "ask",
                "selection": {"scopeKind": "session"},
                "inquiryRefs": [
                    {
                        "kind": "file",
                        "path": fixture.inspection_file_path,
                        "label": fixture.inspection_file_path,
                    },
                    {
                        "kind": "audit_record",
                        "id": fixture.log_record_id,
                        "label": "Frontend error log record",
                    },
                    {
                        "kind": "result",
                        "id": fixture.result_id,
                        "label": "Task execution result",
                    },
                    {
                        "kind": "diagnostic",
                        "id": "diagnostic:bundle_export",
                        "label": "Diagnostic bundle export",
                    },
                ],
            },
        )
        activity_response = fixture.request(
            "GET",
            f"/api/v1/sessions/{quote(fixture.session_id, safe='')}/activity",
        )
        after_content = target.read_text(encoding="utf-8")
        after_task = fixture.app.task_bus.get(fixture.session_id, fixture.task_id)
    finally:
        fixture.close()

    assert after_task is not None
    assert response.status == 200
    body = response.json
    assert body["ok"] is True
    data = body["data"]
    assert data["outcome"]["status"] == "answered"
    assert data["decision"]["sideEffect"] == "no_effect"
    assert data["outcome"]["userMessage"] == (
        "LLM rendered a read-only answer from cited safe evidence only."
    )
    inquiry = data["inquiryResult"]
    assert inquiry["answer"]["confidence"] == "high"
    assert inquiry["answer"]["body"] == (
        "LLM rendered a read-only answer from cited safe evidence only."
    )
    assert [ref["refId"] for ref in inquiry["evidenceRefs"]] == cited_refs
    assert str(tmp_path) not in inquiry["answer"]["body"]
    assert "/Users/" not in inquiry["answer"]["body"]
    assert after_content == before_content
    assert after_task.model_dump(mode="json") == before_task_payload
    assert llm.calls
    assert llm.calls[-1]["tools"] is None
    prompt = llm.calls[-1]["messages"][1]["content"]
    assert str(tmp_path) not in prompt
    assert "/Users/" not in prompt

    assert activity_response.status == 200
    activity_items = activity_response.json["data"]["items"]
    replayed = [item for item in activity_items if item["id"] == f"activity:inquiry:{command_id}"]
    assert replayed
    assert replayed[0]["kind"] == "answer"
    assert replayed[0]["sideEffect"] == "no_effect"


@dataclass
class _InquiryLLM:
    content: str = '{"intent_summary":"Diagnostics smoke"}'
    calls: list[dict[str, Any]] = field(default_factory=list)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "metadata": metadata,
                "kwargs": kwargs,
            }
        )
        return ChatResponse(
            content=self.content,
            tool_calls=[],
            raw_assistant_message={},
        )
