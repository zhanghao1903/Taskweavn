"""Regression tests for the Default Execution Agent system prompt."""

from __future__ import annotations

from taskweavn.prompts import AGENT_LOOP_SYSTEM_PROMPT


def test_agent_loop_prompt_contains_execution_domain_contract() -> None:
    prompt = AGENT_LOOP_SYSTEM_PROMPT

    assert "Default Execution Agent" in prompt
    assert "execute exactly one Published Task" in prompt
    assert "Context Manager owns the final LLM input" in prompt
    assert "Context Manager facts as evidence" in prompt
    assert "Answered ASK facts" in prompt
    assert "interruption is requested" in prompt
    assert "next safe point" in prompt
    assert "Default to choice-first ASK design" in prompt
    assert "provide `suggested_options`" in prompt
    assert "Do not enable free text by default" in prompt
    assert "`allow_free_text=true`" in prompt
    assert "`allow_no_option_with_text=true`" in prompt
    assert "`allow_free_text=false`" in prompt
    assert "`allow_no_option_with_text=false`" in prompt
    assert "Choose `free_text` only" in prompt
    assert "does not support per-question options" in prompt
    assert "`questions` array of at most 4" in prompt
    assert "blocking `ask_user` call is a yield point" in prompt
    assert "`agent_finish`" in prompt
