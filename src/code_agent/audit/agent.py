"""AuditAgent — LLM-driven verdict on each CodeAction.

Design pillars (locked with the user, Phase 2.3):

1. **Synchronous** — the auditor runs inline, after every
   :class:`CodeExecutionObservation`. No background queue.
2. **Failure → ``inconclusive``** — any LLM error, JSON parse failure, or
   schema validation failure produces ``verdict="inconclusive"`` rather than
   propagating an exception. The audit must never crash the main loop.
3. **Verdict feeds back via a system message** — the loop appends a short
   system-role message summarizing the verdict so the next LLM turn sees it
   as authoritative steering signal, not as an LLM-generated tool result.
4. **Off by default** — :attr:`AuditConfig.enabled` defaults to ``False``;
   the loop only runs the auditor when explicitly opted in.
5. **Independent model config** — :class:`AuditConfig` carries its own
   ``model`` / ``api_key`` so the auditor can be a smaller/cheaper model
   than the main loop's model.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from code_agent.llm.client import LLMClient
from code_agent.types.base import BaseObservation
from code_agent.types.code_action import CodeAction, CodeExecutionObservation

_LOGGER = logging.getLogger(__name__)

Verdict = Literal["pass", "fail", "inconclusive"]


# ---------------------------------------------------------------------------
# Verdict payload (LLM output schema)
# ---------------------------------------------------------------------------


class AuditVerdict(BaseModel):
    """Structured payload the auditor LLM is asked to emit.

    This is the *content* of an audit, separate from the
    :class:`AuditObservation` event wrapper. Keeping it a plain (non-event)
    BaseModel makes it easy to validate parsed LLM JSON before promoting it
    to an Observation on the EventStream.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: Verdict = Field(
        description=(
            "'pass' = the snippet's behavior matches its declared intent and "
            "stayed within declared scope; 'fail' = a clear mismatch or "
            "scope violation; 'inconclusive' = not enough signal to decide."
        )
    )
    rationale: str = Field(
        min_length=1,
        max_length=1000,
        description="One- to three-sentence explanation feeding back to the loop.",
    )
    concerns: list[str] = Field(
        default_factory=list,
        description="Optional bulleted list of specific issues the auditor flagged.",
    )
    intent_met: bool | None = Field(
        default=None,
        description=(
            "True iff the snippet visibly accomplished its declared intent. "
            "None when inconclusive."
        ),
    )
    scope_respected: bool | None = Field(
        default=None,
        description=(
            "True iff there were no undeclared file changes. None when inconclusive."
        ),
    )


# ---------------------------------------------------------------------------
# Observation wrapper (EventStream event)
# ---------------------------------------------------------------------------


class AuditObservation(BaseObservation):
    """Records one auditor pass against a CodeAction + its observation.

    ``action_id`` (inherited) points at the *audited* CodeAction so the
    EventStream can be queried for "what did the auditor say about action
    X?". ``success`` is True iff the auditor produced a usable
    ``pass``/``fail`` verdict — ``inconclusive`` flips it to False so the
    loop can flag the gap during introspection.
    """

    verdict: Verdict
    rationale: str
    concerns: list[str] = Field(default_factory=list)
    intent_met: bool | None = None
    scope_respected: bool | None = None
    audited_observation_id: str = Field(
        description="event_id of the CodeExecutionObservation that was audited."
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditConfig:
    """Per-run audit knobs.

    The auditor is opt-in — leaving :attr:`enabled` False means the loop
    skips the audit step entirely. ``model`` / ``api_key`` default to the
    main loop's LLM env vars (:func:`from_env`) if unset, but can also be
    overridden to point the auditor at a cheaper/different model.
    """

    enabled: bool = False
    model: str | None = None
    api_key: str | None = None

    @classmethod
    def from_env(cls) -> AuditConfig:
        """Build from ``AUDIT_ENABLED``, ``AUDIT_MODEL``, ``AUDIT_API_KEY``.

        Useful for the CLI when the user wants to flip auditing on without
        touching the agent constructor. ``AUDIT_ENABLED`` is truthy when
        set to ``1``, ``true``, ``yes``, ``on`` (case-insensitive).
        """
        enabled = os.environ.get("AUDIT_ENABLED", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        return cls(
            enabled=enabled,
            model=os.environ.get("AUDIT_MODEL") or None,
            api_key=os.environ.get("AUDIT_API_KEY") or None,
        )


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------


AUDIT_SYSTEM_PROMPT = """You are CodeAuditor, an independent reviewer that judges whether a single \
code snippet executed as the agent claimed it would.

You receive:
* the agent's stated INTENT for the snippet (one sentence),
* the SOURCE CODE of the snippet,
* the agent's declared TRACKING scope (file paths and variable names it \
claimed it would touch), and
* the OBSERVED RESULT (exit code, stdout, stderr, file changes split into \
declared vs undeclared, captured variable values, timeout flag).

Your output MUST be a single JSON object with this exact shape — nothing else, \
no Markdown fences, no commentary outside the JSON:

{
  "verdict": "pass" | "fail" | "inconclusive",
  "rationale": "<1-3 sentences explaining the verdict>",
  "concerns": ["<short bullet>", "..."],
  "intent_met": true | false | null,
  "scope_respected": true | false | null
}

Rules:
* "pass" means the snippet visibly achieved its INTENT AND did not produce \
undeclared file changes.
* "fail" means at least one of: the snippet did not achieve its INTENT, the \
snippet errored or timed out without recovery, or undeclared_changes is non-empty \
in a way that meaningfully exceeds the declared scope.
* "inconclusive" means you genuinely cannot tell from the observation (e.g. the \
intent claims something the observation cannot evidence either way). Use it \
sparingly.
* "intent_met" / "scope_respected" should be null when "verdict" is \
"inconclusive" and concrete booleans otherwise.
* "concerns" may be an empty list. Keep each entry under ~120 characters.
"""


# ---------------------------------------------------------------------------
# Audit Agent
# ---------------------------------------------------------------------------


class AuditAgent:
    """Synchronous LLM auditor. Construct once per AgentLoop run."""

    def __init__(
        self,
        llm: LLMClient,
        *,
        system_prompt: str = AUDIT_SYSTEM_PROMPT,
    ) -> None:
        self._llm = llm
        self._system_prompt = system_prompt

    @classmethod
    def from_config(
        cls, config: AuditConfig, *, fallback_llm: LLMClient | None = None
    ) -> AuditAgent | None:
        """Build an AuditAgent from :class:`AuditConfig`, or None if disabled.

        Resolution order for the LLM:
          1. ``config.model`` (+ ``config.api_key`` if given) — explicit override.
          2. Env vars via :meth:`LLMClient.from_env` — separate ``AUDIT_*``
             not yet implemented; this falls through to LLM_*.
          3. ``fallback_llm`` — typically the main loop's LLMClient, so the
             auditor reuses the same model.
        """
        if not config.enabled:
            return None
        if config.model is not None:
            llm = LLMClient(model=config.model, api_key=config.api_key)
        elif fallback_llm is not None:
            llm = fallback_llm
        else:
            llm = LLMClient.from_env()
        return cls(llm=llm)

    def audit(
        self,
        action: CodeAction,
        observation: CodeExecutionObservation,
    ) -> AuditObservation:
        """Score a (CodeAction, CodeExecutionObservation) pair.

        Never raises — any error is folded into a ``verdict="inconclusive"``
        AuditObservation whose ``rationale`` describes the failure.
        """
        prompt = self._render_user_prompt(action, observation)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": prompt},
        ]
        try:
            response = self._llm.chat(messages=messages, tools=None)
        except Exception as exc:  # noqa: BLE001 — auditor must not crash the loop.
            _LOGGER.exception("auditor LLM call failed")
            return self._inconclusive(
                observation,
                rationale=f"Auditor LLM call failed: {type(exc).__name__}: {exc}",
            )

        verdict_or_error = self._parse_verdict(response.content)
        if isinstance(verdict_or_error, str):  # error reason
            return self._inconclusive(
                observation,
                rationale=f"Auditor response was not usable JSON: {verdict_or_error}",
            )

        verdict = verdict_or_error
        return AuditObservation(
            action_id=action.event_id,
            audited_observation_id=observation.event_id,
            verdict=verdict.verdict,
            rationale=verdict.rationale,
            concerns=list(verdict.concerns),
            intent_met=verdict.intent_met,
            scope_respected=verdict.scope_respected,
            success=(verdict.verdict != "inconclusive"),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _render_user_prompt(
        action: CodeAction, observation: CodeExecutionObservation
    ) -> str:
        """Serialize the audit subject into a single user-message string.

        We hand the LLM JSON because (a) it's faithful, (b) it round-trips
        with the EventStream encoding the rest of the system uses, and (c)
        the model can ignore fields it doesn't need.
        """
        payload = {
            "intent": action.intent,
            "code": action.code,
            "tracking": {
                "files": list(action.tracking.files),
                "variables": list(action.tracking.variables),
            },
            "observation": {
                "exit_code": observation.exit_code,
                "stdout": _truncate(observation.stdout),
                "stderr": _truncate(observation.stderr),
                "duration_ms": observation.duration_ms,
                "timed_out": observation.timed_out,
                "blocked_reason": observation.blocked_reason,
                "declared_changes": [
                    c.model_dump(mode="json") for c in observation.declared_changes
                ],
                "undeclared_changes": [
                    c.model_dump(mode="json") for c in observation.undeclared_changes
                ],
                "variable_dump": dict(observation.variable_dump),
            },
        }
        return (
            "Audit the following CodeAction execution. Respond with ONLY the "
            "JSON object specified by the system prompt.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    @staticmethod
    def _parse_verdict(raw: str) -> AuditVerdict | str:
        """Return a parsed AuditVerdict, or an error-string reason.

        Accepts either pure JSON or JSON wrapped in ```json fences``` /
        leading prose — finds the outermost ``{...}`` and validates that.
        """
        body = raw.strip()
        if not body:
            return "empty response"
        # If wrapped in ```json``` or ``` fences, strip them.
        if body.startswith("```"):
            body = body.strip("`")
            if body.lower().startswith("json"):
                body = body[4:]
            body = body.strip()
        # As a last resort, find the first { and last } and try that span.
        start = body.find("{")
        end = body.rfind("}")
        if start == -1 or end == -1 or end < start:
            return "no JSON object found"
        candidate = body[start : end + 1]
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            return f"json decode error: {exc}"
        try:
            return AuditVerdict.model_validate(data)
        except ValidationError as exc:
            return f"schema validation failed: {exc.errors()}"

    @staticmethod
    def _inconclusive(
        observation: CodeExecutionObservation, *, rationale: str
    ) -> AuditObservation:
        return AuditObservation(
            action_id=observation.action_id,
            audited_observation_id=observation.event_id,
            verdict="inconclusive",
            rationale=rationale,
            concerns=[],
            intent_met=None,
            scope_respected=None,
            success=False,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_OUTPUT_TRUNCATE_CHARS = 4000


def _truncate(value: str) -> str:
    if len(value) <= _OUTPUT_TRUNCATE_CHARS:
        return value
    keep = _OUTPUT_TRUNCATE_CHARS // 2
    return f"{value[:keep]}\n...<truncated {len(value) - 2 * keep} chars>...\n{value[-keep:]}"


def render_audit_system_message(audit: AuditObservation) -> str:
    """Format an AuditObservation as the body of a ``role=system`` message.

    The loop appends this between turns so the next LLM call sees the
    auditor's verdict as authoritative steering — distinct from a tool
    response (which the model could legitimately argue with) or assistant
    chain-of-thought (which it could ignore).
    """
    lines = [f"[audit] verdict={audit.verdict}"]
    if audit.intent_met is not None:
        lines.append(f"[audit] intent_met={audit.intent_met}")
    if audit.scope_respected is not None:
        lines.append(f"[audit] scope_respected={audit.scope_respected}")
    lines.append(f"[audit] rationale: {audit.rationale}")
    if audit.concerns:
        lines.append("[audit] concerns:")
        lines.extend(f"  - {c}" for c in audit.concerns)
    return "\n".join(lines)
