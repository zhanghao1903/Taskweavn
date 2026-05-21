"""Centralized system prompts used by TaskWeavn LLM-backed components."""

from taskweavn.prompts.audit import AUDIT_SYSTEM_PROMPT
from taskweavn.prompts.collaborator import COLLABORATOR_AUTHORING_SYSTEM_PROMPT
from taskweavn.prompts.core import AGENT_LOOP_SYSTEM_PROMPT
from taskweavn.prompts.interaction import LLM_RISK_SYSTEM_PROMPT

__all__ = [
    "AGENT_LOOP_SYSTEM_PROMPT",
    "AUDIT_SYSTEM_PROMPT",
    "COLLABORATOR_AUTHORING_SYSTEM_PROMPT",
    "LLM_RISK_SYSTEM_PROMPT",
]
