"""Guarded answer providers for read-only inquiry."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol, cast

from taskweavn.llm.contracts import ChatResponse
from taskweavn.llm.logging import log_agent_llm_input, log_agent_llm_output
from taskweavn.observability import LogContext
from taskweavn.server.ui_contract.read_only_inquiry import (
    ReadOnlyInquiryAnswer,
    ReadOnlyInquiryConfidence,
    ReadOnlyInquiryEvidenceRef,
    ReadOnlyInquiryRequest,
    ReadOnlyInquiryStatus,
    ReadOnlyInquiryWarning,
)


class ReadOnlyInquiryAnswerProvider(Protocol):
    """Optional bounded answer renderer for normalized inquiry context."""

    def answer(
        self,
        *,
        request: ReadOnlyInquiryRequest,
        baseline_answer: ReadOnlyInquiryAnswer,
        evidence_refs: tuple[ReadOnlyInquiryEvidenceRef, ...],
        warnings: tuple[ReadOnlyInquiryWarning, ...] = (),
    ) -> ReadOnlyInquiryAnswerProviderResult: ...


class LLMChatClient(Protocol):
    """Small LLM surface used by guarded read-only inquiry answers."""

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any: ...


@dataclass(frozen=True)
class ReadOnlyInquiryAnswerProviderResult:
    status: ReadOnlyInquiryStatus
    answer: ReadOnlyInquiryAnswer | None
    evidence_refs: tuple[ReadOnlyInquiryEvidenceRef, ...]
    warnings: tuple[ReadOnlyInquiryWarning, ...] = ()


@dataclass(frozen=True)
class GuardedLLMReadOnlyInquiryAnswerProvider:
    """LLM-backed answer provider with no tools and citation validation."""

    llm: LLMChatClient
    timeout_seconds: float | None = None
    max_answer_chars: int = 4000
    max_cited_refs: int = 12

    def answer(
        self,
        *,
        request: ReadOnlyInquiryRequest,
        baseline_answer: ReadOnlyInquiryAnswer,
        evidence_refs: tuple[ReadOnlyInquiryEvidenceRef, ...],
        warnings: tuple[ReadOnlyInquiryWarning, ...] = (),
    ) -> ReadOnlyInquiryAnswerProviderResult:
        if not evidence_refs:
            return _fallback(
                baseline_answer,
                evidence_refs,
                warnings,
                _provider_warning("LLM answer provider requires cited evidence."),
            )
        try:
            metadata = {
                "agent_kind": "read_only_inquiry",
                "agent_id": "read_only_inquiry",
                "feature": "read_only_inquiry",
                "inquiryId": request.inquiry_id,
                "request_purpose": "read_only_inquiry.answer",
                "session_id": request.session_id,
            }
            messages = _messages(
                request=request,
                baseline_answer=baseline_answer,
                evidence_refs=evidence_refs,
                max_answer_chars=self.max_answer_chars,
                max_cited_refs=self.max_cited_refs,
            )
            chat_kwargs: dict[str, Any] = {"metadata": metadata}
            if self.timeout_seconds is not None:
                chat_kwargs["timeout_seconds"] = self.timeout_seconds
            log_context = LogContext(
                session_id=request.session_id,
                agent_id="read_only_inquiry",
            )
            log_agent_llm_input(
                agent_kind="read_only_inquiry",
                request_purpose="read_only_inquiry.answer",
                messages=messages,
                tools=None,
                metadata=metadata,
                context=log_context,
            )
            response = self.llm.chat(
                messages=messages,
                tools=None,
                **chat_kwargs,
            )
            if isinstance(response, ChatResponse):
                log_agent_llm_output(
                    agent_kind="read_only_inquiry",
                    request_purpose="read_only_inquiry.answer",
                    response=response,
                    metadata=metadata,
                    context=log_context,
                )
            payload = _json_payload(_response_content(response))
        except Exception:  # noqa: BLE001 - do not expose provider internals.
            return _fallback(
                baseline_answer,
                evidence_refs,
                warnings,
                _provider_warning("LLM answer provider is unavailable."),
            )

        if _contains_mutating_intent(payload):
            return _fallback(
                baseline_answer,
                evidence_refs,
                warnings,
                ReadOnlyInquiryWarning(
                    code="inquiry.no_mutation_boundary",
                    message=(
                        "LLM answer provider output was ignored because it "
                        "requested mutation or tool execution."
                    ),
                ),
            )

        result = _validated_payload(
            payload,
            evidence_refs=evidence_refs,
            max_answer_chars=self.max_answer_chars,
            max_cited_refs=self.max_cited_refs,
        )
        if result is None:
            return _fallback(
                baseline_answer,
                evidence_refs,
                warnings,
                _provider_warning("LLM answer provider returned unsupported output."),
            )
        return ReadOnlyInquiryAnswerProviderResult(
            status=result.status,
            answer=result.answer,
            evidence_refs=result.evidence_refs,
            warnings=(*warnings, *result.warnings),
        )


@dataclass(frozen=True)
class _ValidatedProviderPayload:
    status: ReadOnlyInquiryStatus
    answer: ReadOnlyInquiryAnswer | None
    evidence_refs: tuple[ReadOnlyInquiryEvidenceRef, ...]
    warnings: tuple[ReadOnlyInquiryWarning, ...] = ()


_VALID_STATUSES: set[str] = {
    "answered",
    "needs_clarification",
    "unsupported",
    "rejected",
}
_VALID_CONFIDENCE: set[str] = {"high", "medium", "low"}
_MUTATING_KEYS: set[str] = {
    "action",
    "actions",
    "command",
    "commands",
    "file_edits",
    "mutation",
    "patch",
    "plan_patch",
    "taskbus",
    "tool",
    "tool_calls",
    "tools",
    "workspace_write",
}
_MUTATING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:run|execute)\s+(?:a\s+)?(?:shell\s+)?command\b", re.I),
    re.compile(r"\b(?:write|edit|modify|delete|create)\s+(?:the\s+)?file\b", re.I),
    re.compile(r"\bapply[_ -]?patch\b", re.I),
    re.compile(r"\btask\s*bus\b", re.I),
    re.compile(r"\bI\s+(?:will|can)\s+(?:run|execute|write|edit|modify|delete)\b", re.I),
)
_ABSOLUTE_HOME_PATH = re.compile(r"/Users/[^\s`\"']+")


def _messages(
    *,
    request: ReadOnlyInquiryRequest,
    baseline_answer: ReadOnlyInquiryAnswer,
    evidence_refs: tuple[ReadOnlyInquiryEvidenceRef, ...],
    max_answer_chars: int,
    max_cited_refs: int,
) -> list[dict[str, str]]:
    evidence = [
        {
            "refId": ref.ref_id,
            "kind": ref.kind,
            "label": _safe_text(ref.label, limit=240),
            "disclosure": ref.disclosure,
            "truncated": ref.truncated,
        }
        for ref in evidence_refs[:max_cited_refs]
        if ref.disclosure != "hidden"
    ]
    payload = {
        "inquiryId": request.inquiry_id,
        "question": _safe_text(request.question, limit=1200),
        "scope": {
            "kind": request.scope.kind,
            "planId": request.scope.plan_id,
            "taskNodeId": request.scope.task_node_id,
        },
        "baselineAnswer": {
            "title": baseline_answer.title,
            "body": _safe_text(baseline_answer.body, limit=6000),
            "confidence": baseline_answer.confidence,
        },
        "evidenceRefs": evidence,
        "outputRules": {
            "format": "json_object",
            "allowedStatus": sorted(_VALID_STATUSES),
            "maxAnswerChars": max_answer_chars,
            "maxCitedRefs": max_cited_refs,
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "You answer read-only questions about already-provided Plato "
                "context. Do not request tools, commands, file edits, Plan or "
                "Task mutation, TaskBus work, or hidden context. Return only "
                "JSON with keys: status, body, confidence, citedRefIds."
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def _validated_payload(
    payload: dict[str, Any],
    *,
    evidence_refs: tuple[ReadOnlyInquiryEvidenceRef, ...],
    max_answer_chars: int,
    max_cited_refs: int,
) -> _ValidatedProviderPayload | None:
    raw_status = payload.get("status") or "answered"
    if not isinstance(raw_status, str) or raw_status not in _VALID_STATUSES:
        return None
    status = cast(ReadOnlyInquiryStatus, raw_status)

    cited_ref_ids = _string_list(payload.get("citedRefIds"))[:max_cited_refs]
    known_refs = {ref.ref_id: ref for ref in evidence_refs}
    cited_refs = tuple(known_refs[ref_id] for ref_id in cited_ref_ids if ref_id in known_refs)
    if cited_ref_ids and len(cited_refs) != len(cited_ref_ids):
        return None
    if status == "answered" and not cited_refs:
        return None

    if status != "answered":
        return _ValidatedProviderPayload(
            status=status,
            answer=None,
            evidence_refs=cited_refs or evidence_refs,
            warnings=(
                ReadOnlyInquiryWarning(
                    code=(
                        "inquiry.no_mutation_boundary"
                        if status == "rejected"
                        else "inquiry.unsupported_question"
                    ),
                    message="LLM answer provider could not produce a safe answer.",
                ),
            ),
        )

    body = _answer_body(payload)
    raw_confidence = payload.get("confidence") or "medium"
    if (
        body is None
        or not isinstance(raw_confidence, str)
        or raw_confidence not in _VALID_CONFIDENCE
    ):
        return None
    confidence = cast(ReadOnlyInquiryConfidence, raw_confidence)
    return _ValidatedProviderPayload(
        status="answered",
        answer=ReadOnlyInquiryAnswer(
            title=_optional_string(payload.get("title")),
            body=body[:max_answer_chars],
            confidence=confidence,
        ),
        evidence_refs=cited_refs,
    )


def _json_payload(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        first = stripped.find("{")
        last = stripped.rfind("}")
        if first >= 0 and last > first:
            stripped = stripped[first : last + 1]
    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise ValueError("provider output must be a JSON object")
    return payload


def _response_content(response: Any) -> str:
    content = getattr(response, "content", None)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("provider response has no content")
    return content


def _answer_body(payload: dict[str, Any]) -> str | None:
    body = payload.get("body")
    if isinstance(body, str) and body.strip():
        return _safe_text(body, limit=12000)
    answer = payload.get("answer")
    if isinstance(answer, dict):
        nested = answer.get("body")
        if isinstance(nested, str) and nested.strip():
            return _safe_text(nested, limit=12000)
    return None


def _contains_mutating_intent(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _MUTATING_KEYS:
                return True
            if _contains_mutating_intent(item):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_mutating_intent(item) for item in value)
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in _MUTATING_PATTERNS)
    return False


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _safe_text(value: str, *, limit: int) -> str:
    return _ABSOLUTE_HOME_PATH.sub("[redacted-path]", value.replace("\x00", ""))[:limit]


def _fallback(
    baseline_answer: ReadOnlyInquiryAnswer,
    evidence_refs: tuple[ReadOnlyInquiryEvidenceRef, ...],
    warnings: tuple[ReadOnlyInquiryWarning, ...],
    warning: ReadOnlyInquiryWarning,
) -> ReadOnlyInquiryAnswerProviderResult:
    return ReadOnlyInquiryAnswerProviderResult(
        status="answered",
        answer=baseline_answer,
        evidence_refs=evidence_refs,
        warnings=(*warnings, warning),
    )


def _provider_warning(message: str) -> ReadOnlyInquiryWarning:
    return ReadOnlyInquiryWarning(
        code="inquiry.provider_unavailable",
        message=message,
    )


__all__ = [
    "GuardedLLMReadOnlyInquiryAnswerProvider",
    "LLMChatClient",
    "ReadOnlyInquiryAnswerProvider",
    "ReadOnlyInquiryAnswerProviderResult",
]
