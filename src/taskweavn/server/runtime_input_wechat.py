"""Bounded WeChat-send task builders for Runtime Input Router."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from taskweavn.execution_plane.models import (
    CapabilityPolicy,
    EvidenceRequirement,
    ExternalRef,
    TaskRequest,
    TaskRequester,
)
from taskweavn.wechat_task_types import WECHAT_SEND_CAPABILITY, WECHAT_SEND_TASK_TYPE

WeChatSendResolutionStatus = Literal["ready"]


@dataclass(frozen=True)
class WeChatSendResolution:
    status: WeChatSendResolutionStatus
    reason_code: str
    user_message: str
    contact_display_name: str | None = None
    message_text: str | None = None


def wechat_send_task_payload(resolution: WeChatSendResolution) -> dict[str, object]:
    if resolution.status != "ready":
        raise ValueError("WeChat send execution payload requires ready resolution")
    assert resolution.contact_display_name is not None
    assert resolution.message_text is not None
    contact = resolution.contact_display_name
    message = resolution.message_text
    return {
        "title": f"Send WeChat message to {contact}",
        "intent": f"Use WeChat to send a message to {contact}.",
        "summary": (
            "Create a confirmation-gated local macOS WeChat send task. "
            f"Contact: {contact}."
        ),
        "instructions": (
            f"Task type: {WECHAT_SEND_TASK_TYPE}\n"
            f"Contact: {contact}\n"
            f"Message: {message}\n"
            "Policy: require human confirmation before sending; if rejected, do not send."
        ),
        "requiredCapability": WECHAT_SEND_CAPABILITY,
        "constraints": (
            "Do not send without user confirmation.",
            "Send exactly once if confirmed.",
            "Use WeChat Desktop through the local macOS computer-use backend.",
        ),
        "acceptanceCriteria": (
            "The exact message is drafted for the specified contact.",
            "The final send is gated by user confirmation.",
            "Rejecting confirmation results in no message being sent.",
            "Confirming sends the message once and records result/error/evidence.",
        ),
    }


def wechat_send_task_request(
    resolution: WeChatSendResolution,
    *,
    command_id: str,
    session_id: str,
    workspace_id: str | None,
    original_content: str,
) -> TaskRequest:
    if resolution.status != "ready":
        raise ValueError("WeChat send task request requires ready resolution")
    assert resolution.contact_display_name is not None
    assert resolution.message_text is not None
    contact = resolution.contact_display_name
    message = resolution.message_text
    return TaskRequest(
        idempotency_key=f"runtime-input:{session_id}:{command_id}",
        requester=TaskRequester(
            kind="plato",
            id="runtime-input-router",
            display_name="Plato Runtime Input Router",
            trust_scope="local_ui",
        ),
        external_ref=ExternalRef(
            system="plato",
            kind="runtime_input",
            id=command_id,
        ),
        task_type=WECHAT_SEND_TASK_TYPE,
        intent=f"Use WeChat to send a message to {contact}.",
        input={
            "contactDisplayName": contact,
            "messageText": message,
            "operatorNote": "Created from Plato Main Page input.",
        },
        policy=CapabilityPolicy(
            required_capability=WECHAT_SEND_CAPABILITY,
            allowed_tools=("computer_use", "wechat_desktop"),
            requires_human_confirmation=True,
            risk_level="high",
            workspace_scope=workspace_id,
        ),
        evidence=EvidenceRequirement(
            required=("result_summary", "tool_observation"),
            optional=("text_extract",),
            redact_for_diagnostics=True,
        ),
        metadata={
            "sessionId": session_id,
            "source": "main_page_runtime_input",
            "routerCommandId": command_id,
            "originalUserInputHash": sha256(
                original_content.encode("utf-8")
            ).hexdigest(),
        },
    )


__all__ = [
    "WECHAT_SEND_CAPABILITY",
    "WECHAT_SEND_TASK_TYPE",
    "WeChatSendResolution",
    "wechat_send_task_payload",
    "wechat_send_task_request",
]
