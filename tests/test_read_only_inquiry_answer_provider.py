from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from taskweavn.llm import ChatResponse
from taskweavn.server.read_only_inquiry_answer_provider import (
    GuardedLLMReadOnlyInquiryAnswerProvider,
)
from taskweavn.server.ui_contract.read_only_inquiry import (
    ReadOnlyInquiryAnswer,
    ReadOnlyInquiryEvidenceRef,
    ReadOnlyInquiryRequest,
    ReadOnlyInquiryScope,
)


def test_guarded_llm_provider_accepts_cited_json_answer() -> None:
    llm = _LLM(
        json.dumps(
            {
                "status": "answered",
                "title": "Evidence answer",
                "body": "The selected task is done based on the cited status.",
                "confidence": "high",
                "citedRefIds": ["task:task-1:status"],
            }
        )
    )
    provider = GuardedLLMReadOnlyInquiryAnswerProvider(llm)

    result = provider.answer(
        request=_request(question="What happened at /Users/example/project?"),
        baseline_answer=_baseline(body="Safe baseline at /Users/example/project."),
        evidence_refs=(_task_evidence(),),
    )

    assert result.status == "answered"
    assert result.answer is not None
    assert result.answer.title == "Evidence answer"
    assert result.answer.body == "The selected task is done based on the cited status."
    assert result.answer.confidence == "high"
    assert result.evidence_refs == (_task_evidence(),)
    assert result.warnings == ()
    assert llm.calls[0]["tools"] is None
    prompt = llm.calls[0]["messages"][1]["content"]
    assert "/Users/example/project" not in prompt
    assert "[redacted-path]" in prompt


def test_guarded_llm_provider_falls_back_when_citation_is_unknown() -> None:
    llm = _LLM(
        json.dumps(
            {
                "status": "answered",
                "body": "Unsupported answer.",
                "confidence": "medium",
                "citedRefIds": ["unknown-ref"],
            }
        )
    )
    baseline = _baseline()
    provider = GuardedLLMReadOnlyInquiryAnswerProvider(llm)

    result = provider.answer(
        request=_request(),
        baseline_answer=baseline,
        evidence_refs=(_task_evidence(),),
    )

    assert result.status == "answered"
    assert result.answer == baseline
    assert result.evidence_refs == (_task_evidence(),)
    assert result.warnings[-1].code == "inquiry.provider_unavailable"
    assert "unsupported output" in result.warnings[-1].message


def test_guarded_llm_provider_ignores_mutating_output() -> None:
    llm = _LLM(
        json.dumps(
            {
                "status": "answered",
                "body": "I will run a shell command to inspect the workspace.",
                "confidence": "high",
                "citedRefIds": ["task:task-1:status"],
            }
        )
    )
    baseline = _baseline()
    provider = GuardedLLMReadOnlyInquiryAnswerProvider(llm)

    result = provider.answer(
        request=_request(),
        baseline_answer=baseline,
        evidence_refs=(_task_evidence(),),
    )

    assert result.status == "answered"
    assert result.answer == baseline
    assert result.warnings[-1].code == "inquiry.no_mutation_boundary"
    assert "mutation or tool execution" in result.warnings[-1].message


def test_guarded_llm_provider_supports_safe_non_answer_status() -> None:
    llm = _LLM(
        json.dumps(
            {
                "status": "needs_clarification",
                "citedRefIds": ["task:task-1:status"],
            }
        )
    )
    provider = GuardedLLMReadOnlyInquiryAnswerProvider(llm)

    result = provider.answer(
        request=_request(),
        baseline_answer=_baseline(),
        evidence_refs=(_task_evidence(),),
    )

    assert result.status == "needs_clarification"
    assert result.answer is None
    assert result.evidence_refs == (_task_evidence(),)
    assert result.warnings[-1].code == "inquiry.unsupported_question"


@dataclass
class _LLM:
    content: str
    calls: list[dict[str, Any]] = field(default_factory=list)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        self.calls.append({"messages": messages, "tools": tools, "kwargs": kwargs})
        return ChatResponse(
            content=self.content,
            tool_calls=[],
            raw_assistant_message={},
        )


def _request(question: str = "What happened?") -> ReadOnlyInquiryRequest:
    return ReadOnlyInquiryRequest(
        inquiry_id="inq-1",
        session_id="session-1",
        question=question,
        scope=ReadOnlyInquiryScope(
            kind="task",
            plan_id="plan-1",
            task_node_id="task-1",
        ),
    )


def _baseline(body: str = "Task 1 is done.") -> ReadOnlyInquiryAnswer:
    return ReadOnlyInquiryAnswer(
        title="Task status",
        body=body,
        confidence="high",
    )


def _task_evidence() -> ReadOnlyInquiryEvidenceRef:
    return ReadOnlyInquiryEvidenceRef(
        kind="task_status",
        ref_id="task:task-1:status",
        label="Task 1",
    )
