from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from taskweavn.llm import ChatResponse
from taskweavn.observability import configure_session_logging
from taskweavn.server.read_only_inquiry_answer_provider import (
    GuardedLLMReadOnlyInquiryAnswerProvider,
)
from taskweavn.server.ui_contract.read_only_inquiry import (
    ReadOnlyInquiryAnswer,
    ReadOnlyInquiryEvidenceRef,
    ReadOnlyInquiryRequest,
    ReadOnlyInquiryScope,
)
from taskweavn.web_retrieval import (
    WebSearchRequest,
    WebSearchResponse,
    WebSearchResult,
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


def test_guarded_llm_provider_injects_local_time_context() -> None:
    llm = _LLM(
        json.dumps(
            {
                "status": "answered",
                "body": "The resolved date is 2026-06-21.",
                "confidence": "high",
                "citedRefIds": ["task:task-1:status"],
            }
        )
    )
    provider = GuardedLLMReadOnlyInquiryAnswerProvider(
        llm,
        clock=lambda: datetime(
            2026,
            6,
            20,
            12,
            8,
            tzinfo=timezone(timedelta(hours=8), "Asia/Shanghai"),
        ),
    )

    provider.answer(
        request=_request(question="明天世界杯有哪些比赛"),
        baseline_answer=_baseline(),
        evidence_refs=(_task_evidence(),),
    )

    system_prompt = llm.calls[0]["messages"][0]["content"]
    prompt_payload = json.loads(llm.calls[0]["messages"][1]["content"])
    assert "Use timeContext to resolve relative dates" in system_prompt
    assert prompt_payload["timeContext"] == {
        "localNow": "2026-06-20T12:08:00+08:00",
        "localDate": "2026-06-20",
        "timezone": "Asia/Shanghai",
        "utcOffset": "+08:00",
        "yesterdayDate": "2026-06-19",
        "tomorrowDate": "2026-06-21",
    }


def test_guarded_llm_provider_extracts_embedded_structured_answer() -> None:
    body = (
        "根据提供的证据，下周（2026年6月21日至6月27日）将有以下世界杯比赛：\n\n"
        "* 6月21日：库拉索 vs 德国；突尼斯 vs 荷兰\n"
        "* 6月24日：瑞士 vs 加拿大；苏格兰 vs 巴西"
    )
    llm = _LLM(
        "* 6月21日：库拉索 vs 德国\n\n"
        + json.dumps(
            {
                "status": "answered",
                "body": body,
                "confidence": "medium",
                "citedRefIds": ["task:task-1:status"],
            },
            ensure_ascii=False,
        )
    )
    provider = GuardedLLMReadOnlyInquiryAnswerProvider(llm)

    result = provider.answer(
        request=_request(question="下周世界杯有哪些比赛"),
        baseline_answer=_baseline(body="Session 'ask' is understanding."),
        evidence_refs=(_task_evidence(),),
    )

    assert result.status == "answered"
    assert result.answer is not None
    assert result.answer.body == body
    assert result.answer.confidence == "medium"
    assert "Session 'ask' is understanding" not in result.answer.body


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


def test_guarded_llm_provider_uses_web_search_after_unsupported_answer() -> None:
    llm = _SequencedLLM(
        (
            json.dumps(
                {
                    "status": "unsupported",
                    "citedRefIds": ["task:task-1:status"],
                }
            ),
            json.dumps(
                {
                    "status": "answered",
                    "title": "World Cup fixtures",
                    "body": "Tomorrow's fixture list is available from FIFA.",
                    "confidence": "medium",
                    "citedRefIds": ["web:search:1"],
                }
            ),
        )
    )
    web_search = _WebSearchProvider(
        WebSearchResponse(
            provider="fake",
            query="明天世界杯有哪些比赛",
            retrieved_at=datetime.now(UTC),
            results=(
                WebSearchResult(
                    title="FIFA match centre",
                    url="https://www.fifa.com/match-centre",
                    snippet="Tomorrow's FIFA World Cup fixtures are listed here.",
                    source="fake",
                ),
            ),
        )
    )
    provider = GuardedLLMReadOnlyInquiryAnswerProvider(
        llm,
        web_search_provider=web_search,
    )

    result = provider.answer(
        request=_request(question="明天世界杯有哪些比赛"),
        baseline_answer=_baseline(),
        evidence_refs=(_task_evidence(),),
    )

    assert result.status == "answered"
    assert result.answer is not None
    assert result.answer.title == "World Cup fixtures"
    assert result.evidence_refs[-1].kind == "web_search_result"
    assert result.evidence_refs[-1].ref_id == "web:search:1"
    assert web_search.calls == [WebSearchRequest(query="明天世界杯有哪些比赛", max_results=5)]
    assert len(llm.calls) == 2
    second_prompt = llm.calls[1]["messages"][1]["content"]
    assert "External web search evidence" in second_prompt
    assert "FIFA match centre" in second_prompt
    assert "https://www.fifa.com/match-centre" in second_prompt


def test_guarded_llm_provider_wraps_plain_text_answer_after_web_search() -> None:
    plain_answer = "根据当前时间2026年6月20日，下周世界杯比赛包括若干小组赛。"
    llm = _SequencedLLM(
        (
            json.dumps(
                {
                    "status": "unsupported",
                    "citedRefIds": ["task:task-1:status"],
                }
            ),
            plain_answer,
        )
    )
    web_search = _WebSearchProvider(
        WebSearchResponse(
            provider="fake",
            query="下周世界杯有哪些比赛",
            retrieved_at=datetime.now(UTC),
            results=(
                WebSearchResult(
                    title="FIFA fixtures",
                    url="https://www.fifa.com/match-centre",
                    snippet="Fixtures for the requested week.",
                    source="fake",
                ),
            ),
        )
    )
    provider = GuardedLLMReadOnlyInquiryAnswerProvider(
        llm,
        web_search_provider=web_search,
    )

    result = provider.answer(
        request=_request(question="下周世界杯有哪些比赛"),
        baseline_answer=_baseline(),
        evidence_refs=(_task_evidence(),),
    )

    assert result.status == "answered"
    assert result.answer is not None
    assert result.answer.body == plain_answer
    assert result.answer.confidence == "medium"
    assert result.evidence_refs[-1].kind == "web_search_result"


def test_guarded_llm_provider_rejects_mutating_plain_text_answer() -> None:
    llm = _LLM("I will run a shell command to answer this.")
    provider = GuardedLLMReadOnlyInquiryAnswerProvider(llm)
    baseline = _baseline()

    result = provider.answer(
        request=_request(),
        baseline_answer=baseline,
        evidence_refs=(_web_search_evidence(),),
    )

    assert result.status == "answered"
    assert result.answer == baseline
    assert result.warnings[-1].code == "inquiry.no_mutation_boundary"


def test_guarded_llm_provider_writes_split_agent_logs(tmp_path: Path) -> None:
    configure_session_logging(tmp_path / "logs", session_id="session-1")
    llm = _LLM(
        json.dumps(
            {
                "status": "answered",
                "title": "Evidence answer",
                "body": "The task is complete.",
                "confidence": "high",
                "citedRefIds": ["task:task-1:status"],
            }
        )
    )
    provider = GuardedLLMReadOnlyInquiryAnswerProvider(llm)

    result = provider.answer(
        request=_request(question="课件是否已经完成了？"),
        baseline_answer=_baseline(),
        evidence_refs=(_task_evidence(),),
    )

    assert result.status == "answered"
    meta_rows = _read_jsonl(
        tmp_path / "logs" / "sessions" / "session-1" / "llm.jsonl"
    )
    io_rows = _read_jsonl(
        tmp_path / "logs" / "sessions" / "session-1" / "llm_io.jsonl"
    )
    assert [row["event"] for row in meta_rows[-2:]] == [
        "agent_input",
        "agent_output",
    ]
    assert [row["event"] for row in io_rows[-2:]] == [
        "agent_input",
        "agent_output",
    ]
    assert meta_rows[-2]["data"]["request_purpose"] == "read_only_inquiry.answer"
    assert "messages" not in meta_rows[-2]["data"]
    assert "课件是否已经完成了？" in io_rows[-2]["data"]["input"]["messages"][1]["content"]
    assert "content" not in meta_rows[-1]["data"]
    assert "The task is complete." in io_rows[-1]["data"]["output"]["content"]


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


@dataclass
class _SequencedLLM:
    contents: tuple[str, ...]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        self.calls.append({"messages": messages, "tools": tools, "kwargs": kwargs})
        content = self.contents[min(len(self.calls) - 1, len(self.contents) - 1)]
        return ChatResponse(
            content=content,
            tool_calls=[],
            raw_assistant_message={},
        )


@dataclass
class _WebSearchProvider:
    response: WebSearchResponse
    provider: str = "fake"
    calls: list[WebSearchRequest] = field(default_factory=list)

    def search(self, request: WebSearchRequest) -> WebSearchResponse:
        self.calls.append(request)
        return self.response


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


def _web_search_evidence() -> ReadOnlyInquiryEvidenceRef:
    return ReadOnlyInquiryEvidenceRef(
        kind="web_search_result",
        ref_id="web:search:1",
        label="FIFA fixtures - https://www.fifa.com/match-centre",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
