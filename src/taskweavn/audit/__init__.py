"""AuditAgent (Phase 2.3) — LLM-driven verdict on each CodeAction.

The auditor is **off by default**. When enabled, after every
:class:`CodeAction` the loop dispatches the action + its
:class:`CodeExecutionObservation` to a separately-configured LLM and folds
the resulting verdict back into the conversation as a system message.
"""

from taskweavn.audit.agent import (
    AUDIT_SYSTEM_PROMPT,
    AuditAgent,
    AuditConfig,
    AuditObservation,
    AuditVerdict,
    render_audit_system_message,
)

__all__ = [
    "AUDIT_SYSTEM_PROMPT",
    "AuditAgent",
    "AuditConfig",
    "AuditObservation",
    "AuditVerdict",
    "render_audit_system_message",
]
