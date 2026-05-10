"""Tests for AuditAgent (Phase 2.3) — LLM is stubbed."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from taskweavn.audit import (
    AuditAgent,
    AuditConfig,
    AuditObservation,
    AuditVerdict,
    render_audit_system_message,
)
from taskweavn.audit.agent import _truncate
from taskweavn.llm.client import ChatResponse
from taskweavn.types import (
    CodeAction,
    CodeExecutionObservation,
    FileChange,
    ObservationRegistry,
    TrackingConfig,
)

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class StubLLM:
    """Returns canned ChatResponses; records every chat() call."""

    def __init__(self, responses: list[ChatResponse | Exception]) -> None:
        self._iter: Iterator[ChatResponse | Exception] = iter(responses)
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
        self.calls.append({"messages": list(messages), "tools": tools})
        item = next(self._iter)
        if isinstance(item, Exception):
            raise item
        return item


def _resp(content: str) -> ChatResponse:
    return ChatResponse(
        content=content,
        tool_calls=[],
        raw_assistant_message={"role": "assistant", "content": content},
    )


def _action() -> CodeAction:
    return CodeAction(
        intent="write counts to out.json",
        code="import json; json.dump({'n': 3}, open('out.json', 'w'))",
        tracking=TrackingConfig(files=["out.json"], variables=[]),
    )


def _obs(**overrides: Any) -> CodeExecutionObservation:
    base: dict[str, Any] = dict(
        intent="write counts to out.json",
        exit_code=0,
        stdout="",
        stderr="",
        duration_ms=12.0,
        declared_changes=[
            FileChange(
                path="out.json",
                change_type="created",
                after_sha256="a" * 64,
                size_delta=10,
            )
        ],
        undeclared_changes=[],
        variable_dump={},
    )
    base.update(overrides)
    return CodeExecutionObservation(**base)


# ---------------------------------------------------------------------------
# AuditVerdict (LLM payload schema)
# ---------------------------------------------------------------------------


def test_audit_verdict_rejects_unknown_verdict() -> None:
    with pytest.raises(ValidationError):
        AuditVerdict.model_validate({"verdict": "maybe", "rationale": "x"})


def test_audit_verdict_requires_rationale() -> None:
    with pytest.raises(ValidationError):
        AuditVerdict.model_validate({"verdict": "pass"})


# ---------------------------------------------------------------------------
# AuditObservation registers as an observation kind
# ---------------------------------------------------------------------------


def test_audit_observation_is_registered() -> None:
    assert "AuditObservation" in ObservationRegistry.all_kinds()


# ---------------------------------------------------------------------------
# AuditConfig
# ---------------------------------------------------------------------------


def test_audit_config_defaults_off() -> None:
    cfg = AuditConfig()
    assert cfg.enabled is False
    assert cfg.model is None


def test_audit_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_ENABLED", "yes")
    monkeypatch.setenv("AUDIT_MODEL", "anthropic/cheap")
    monkeypatch.setenv("AUDIT_API_KEY", "k")
    cfg = AuditConfig.from_env()
    assert cfg.enabled is True
    assert cfg.model == "anthropic/cheap"
    assert cfg.api_key == "k"


def test_audit_config_env_disabled_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDIT_ENABLED", raising=False)
    monkeypatch.delenv("AUDIT_MODEL", raising=False)
    monkeypatch.delenv("AUDIT_API_KEY", raising=False)
    cfg = AuditConfig.from_env()
    assert cfg.enabled is False
    assert cfg.model is None
    assert cfg.api_key is None


def test_from_config_returns_none_when_disabled() -> None:
    assert AuditAgent.from_config(AuditConfig(enabled=False)) is None


def test_from_config_uses_fallback_when_no_model() -> None:
    fb = MagicMock()
    auditor = AuditAgent.from_config(AuditConfig(enabled=True), fallback_llm=fb)
    assert auditor is not None
    assert auditor._llm is fb


# ---------------------------------------------------------------------------
# AuditAgent.audit happy paths
# ---------------------------------------------------------------------------


def test_audit_pass_verdict_round_trip() -> None:
    llm = StubLLM(
        [
            _resp(
                json.dumps(
                    {
                        "verdict": "pass",
                        "rationale": "out.json was created with the declared payload.",
                        "concerns": [],
                        "intent_met": True,
                        "scope_respected": True,
                    }
                )
            )
        ]
    )
    auditor = AuditAgent(llm=llm)  # type: ignore[arg-type]
    audit = auditor.audit(_action(), _obs())
    assert isinstance(audit, AuditObservation)
    assert audit.verdict == "pass"
    assert audit.intent_met is True
    assert audit.scope_respected is True
    assert audit.success is True


def test_audit_strips_markdown_code_fences() -> None:
    llm = StubLLM(
        [
            _resp(
                "```json\n"
                + json.dumps(
                    {
                        "verdict": "fail",
                        "rationale": "wrote leaked.log outside scope",
                        "concerns": ["undeclared file leaked.log"],
                        "intent_met": True,
                        "scope_respected": False,
                    }
                )
                + "\n```"
            )
        ]
    )
    auditor = AuditAgent(llm=llm)  # type: ignore[arg-type]
    audit = auditor.audit(
        _action(),
        _obs(
            undeclared_changes=[
                FileChange(
                    path="leaked.log",
                    change_type="created",
                    after_sha256="b" * 64,
                    size_delta=5,
                )
            ]
        ),
    )
    assert audit.verdict == "fail"
    assert audit.scope_respected is False


def test_audit_recovers_json_with_leading_prose() -> None:
    """LLM sometimes prefixes 'Here is the audit:' before the JSON."""
    llm = StubLLM(
        [
            _resp(
                "Sure thing! Here you go:\n"
                + json.dumps(
                    {
                        "verdict": "pass",
                        "rationale": "ok",
                    }
                )
                + "\nLet me know if you need more."
            )
        ]
    )
    auditor = AuditAgent(llm=llm)  # type: ignore[arg-type]
    audit = auditor.audit(_action(), _obs())
    assert audit.verdict == "pass"


# ---------------------------------------------------------------------------
# Failure modes -> inconclusive
# ---------------------------------------------------------------------------


def test_audit_returns_inconclusive_on_llm_exception() -> None:
    llm = StubLLM([RuntimeError("rate limited")])
    auditor = AuditAgent(llm=llm)  # type: ignore[arg-type]
    audit = auditor.audit(_action(), _obs())
    assert audit.verdict == "inconclusive"
    assert "rate limited" in audit.rationale
    assert audit.success is False
    assert audit.intent_met is None
    assert audit.scope_respected is None


def test_audit_returns_inconclusive_on_invalid_json() -> None:
    llm = StubLLM([_resp("definitely not json")])
    auditor = AuditAgent(llm=llm)  # type: ignore[arg-type]
    audit = auditor.audit(_action(), _obs())
    assert audit.verdict == "inconclusive"
    assert audit.success is False


def test_audit_returns_inconclusive_on_schema_violation() -> None:
    llm = StubLLM([_resp(json.dumps({"verdict": "kind_of"}))])
    auditor = AuditAgent(llm=llm)  # type: ignore[arg-type]
    audit = auditor.audit(_action(), _obs())
    assert audit.verdict == "inconclusive"


def test_audit_returns_inconclusive_on_empty_response() -> None:
    llm = StubLLM([_resp("")])
    auditor = AuditAgent(llm=llm)  # type: ignore[arg-type]
    audit = auditor.audit(_action(), _obs())
    assert audit.verdict == "inconclusive"


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------


def test_audit_prompt_includes_intent_code_and_observation() -> None:
    llm = StubLLM(
        [_resp(json.dumps({"verdict": "pass", "rationale": "ok"}))]
    )
    auditor = AuditAgent(llm=llm)  # type: ignore[arg-type]
    auditor.audit(_action(), _obs())
    user_msg = llm.calls[0]["messages"][1]["content"]
    assert "write counts to out.json" in user_msg  # intent
    assert "import json" in user_msg  # code
    assert "out.json" in user_msg  # tracking + observation
    assert "exit_code" in user_msg


def test_audit_truncates_huge_stdout_in_prompt() -> None:
    llm = StubLLM(
        [_resp(json.dumps({"verdict": "pass", "rationale": "ok"}))]
    )
    auditor = AuditAgent(llm=llm)  # type: ignore[arg-type]
    big = "X" * 100_000
    auditor.audit(_action(), _obs(stdout=big))
    user_msg = llm.calls[0]["messages"][1]["content"]
    assert "<truncated" in user_msg
    assert len(user_msg) < 30_000  # well under the raw 100k


def test_truncate_helper_shape() -> None:
    s = "a" * 9000
    out = _truncate(s)
    assert "<truncated" in out
    assert out.startswith("a")
    assert out.endswith("a")


# ---------------------------------------------------------------------------
# System-message renderer
# ---------------------------------------------------------------------------


def test_render_audit_system_message_contains_verdict() -> None:
    obs = AuditObservation(
        action_id="x",
        audited_observation_id="y",
        verdict="fail",
        rationale="declared scope was exceeded",
        concerns=["leaked.log was created"],
        intent_met=True,
        scope_respected=False,
        success=False,
    )
    body = render_audit_system_message(obs)
    assert "verdict=fail" in body
    assert "intent_met=True" in body
    assert "scope_respected=False" in body
    assert "rationale" in body
    assert "leaked.log" in body


def test_render_audit_system_message_inconclusive_omits_booleans() -> None:
    obs = AuditObservation(
        action_id="x",
        audited_observation_id="y",
        verdict="inconclusive",
        rationale="LLM unreachable",
        success=False,
    )
    body = render_audit_system_message(obs)
    assert "verdict=inconclusive" in body
    assert "intent_met" not in body
    assert "scope_respected" not in body
