"""Deterministic Product 1.0 context selection policy."""

from __future__ import annotations

from dataclasses import dataclass

from taskweavn.context.models import (
    ContextBudget,
    ContextCandidate,
    ContextExclusion,
    EventSummary,
    FileSnippet,
    ToolResultSummary,
)

POLICY_VERSION = "deterministic-context-policy.v0"


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4) if text else 0


@dataclass(frozen=True)
class CandidateSelection:
    selected: tuple[ContextCandidate, ...]
    excluded: tuple[ContextExclusion, ...]


class DeterministicContextPolicy:
    """Small deterministic selector with stable priority ordering."""

    version = POLICY_VERSION

    def select_candidates(
        self,
        candidates: tuple[ContextCandidate, ...],
        *,
        max_candidates: int | None = None,
        max_tokens: int | None = None,
    ) -> CandidateSelection:
        ordered = sorted(
            candidates,
            key=lambda candidate: (
                candidate.priority,
                candidate.source_type,
                candidate.source_ref,
                candidate.candidate_id,
            ),
        )
        selected: list[ContextCandidate] = []
        excluded: list[ContextExclusion] = []
        token_count = 0
        for candidate in ordered:
            if max_candidates is not None and len(selected) >= max_candidates:
                excluded.append(
                    ContextExclusion(
                        candidate_id=candidate.candidate_id,
                        reason="max_candidates_exceeded",
                    )
                )
                continue
            next_count = token_count + candidate.token_estimate
            if max_tokens is not None and next_count > max_tokens:
                excluded.append(
                    ContextExclusion(
                        candidate_id=candidate.candidate_id,
                        reason="max_tokens_exceeded",
                    )
                )
                continue
            selected.append(candidate)
            token_count = next_count
        return CandidateSelection(selected=tuple(selected), excluded=tuple(excluded))

    def trim_events(
        self,
        events: tuple[EventSummary, ...],
        budget: ContextBudget,
    ) -> tuple[EventSummary, ...]:
        if budget.max_events == 0:
            return ()
        return tuple(events[-budget.max_events :])

    def trim_tool_results(
        self,
        tool_results: tuple[ToolResultSummary, ...],
        budget: ContextBudget,
    ) -> tuple[ToolResultSummary, ...]:
        if budget.max_tool_results == 0:
            return ()
        return tuple(tool_results[-budget.max_tool_results :])

    def trim_file_snippets(
        self,
        snippets: tuple[FileSnippet, ...],
        budget: ContextBudget,
    ) -> tuple[FileSnippet, ...]:
        if budget.max_file_snippets == 0 or budget.max_file_snippet_chars == 0:
            return ()
        selected: list[FileSnippet] = []
        used_chars = 0
        for snippet in snippets[-budget.max_file_snippets :]:
            remaining = budget.max_file_snippet_chars - used_chars
            if remaining <= 0:
                break
            if len(snippet.content) <= remaining:
                selected.append(snippet)
                used_chars += len(snippet.content)
                continue
            truncated = snippet.model_copy(
                update={
                    "content": snippet.content[:remaining],
                    "token_estimate": estimate_tokens(snippet.content[:remaining]),
                    "reason": f"{snippet.reason}; truncated_by_context_budget",
                }
            )
            selected.append(truncated)
            break
        return tuple(selected)
