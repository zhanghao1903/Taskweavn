"""Bounded WeChat-send intent resolution for Runtime Input Router."""

from __future__ import annotations

import re
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

WECHAT_SEND_TASK_TYPE = "communication.wechat.send_message"
WECHAT_SEND_CAPABILITY = "communication.wechat_desktop_send"

WeChatSendResolutionStatus = Literal["ready", "needs_clarification", "unsupported"]
WeChatSendMissingSlot = Literal["contactDisplayName", "messageText"]

_SEND_VERBS = (
    "发送一条消息",
    "发送消息",
    "发一条消息",
    "发消息",
    "发送",
    "发",
)
_CONTACT_AND_MESSAGE_PATTERNS = (
    re.compile(rf"^给微信(?P<contact>.+?)(?:{'|'.join(_SEND_VERBS)})[:：](?P<message>.+)$"),
    re.compile(r"^给(?P<contact>.+?)发微信[:：](?P<message>.+)$"),
    re.compile(rf"^在微信给(?P<contact>.+?)(?:{'|'.join(_SEND_VERBS)})[:：](?P<message>.+)$"),
    re.compile(rf"^用微信给(?P<contact>.+?)(?:{'|'.join(_SEND_VERBS)})[:：](?P<message>.+)$"),
)
_CONTACT_ONLY_PATTERNS = (
    re.compile(rf"^给微信(?P<contact>.+?)(?:{'|'.join(_SEND_VERBS)})$"),
    re.compile(r"^给(?P<contact>.+?)发微信$"),
    re.compile(rf"^在微信给(?P<contact>.+?)(?:{'|'.join(_SEND_VERBS)})$"),
    re.compile(rf"^用微信给(?P<contact>.+?)(?:{'|'.join(_SEND_VERBS)})$"),
)
_MESSAGE_ONLY_PATTERN = re.compile(
    rf"^(?:帮我|请|麻烦)?(?:用)?微信?(?:{'|'.join(_SEND_VERBS)})[:：](?P<message>.+)$"
)
_CONFIRMATION_HINT_RE = re.compile(
    r"(?:。|\.|，|,|\s)*(?:发送前让我确认|发送前确认|先让我确认|先确认|需要我确认)(?:。|\.|！|!|，|,|\s)*$"
)
_QUESTION_PREFIXES = ("怎么", "如何", "为什么", "为何", "什么")
_BULK_CONTACT_MARKERS = ("、", "，", ",", "和", "及", "以及")


@dataclass(frozen=True)
class WeChatSendResolution:
    status: WeChatSendResolutionStatus
    reason_code: str
    user_message: str
    contact_display_name: str | None = None
    message_text: str | None = None
    missing_slots: tuple[WeChatSendMissingSlot, ...] = ()


def resolve_wechat_send_input(content: str) -> WeChatSendResolution | None:
    """Return a bounded WeChat-send interpretation, or None if unrelated."""

    normalized = _normalize(content)
    if not normalized:
        return None
    if _looks_like_question(normalized):
        return None
    if "微信" not in normalized:
        return None

    for pattern in _CONTACT_AND_MESSAGE_PATTERNS:
        match = pattern.match(normalized)
        if match is None:
            continue
        contact = _clean_slot(match.group("contact"))
        message = _strip_confirmation_hint(_clean_slot(match.group("message")))
        if _is_bulk_contact(contact):
            return _unsupported("bulk_contact", "一次只能创建一个微信发送任务。没有发送消息。")
        if not message:
            return _missing_message(contact)
        return WeChatSendResolution(
            status="ready",
            reason_code="wechat_send_ready",
            user_message="已识别为微信发送任务，发送前仍需要用户确认。",
            contact_display_name=contact,
            message_text=message,
        )

    for pattern in _CONTACT_ONLY_PATTERNS:
        match = pattern.match(normalized)
        if match is None:
            continue
        contact = _clean_slot(match.group("contact"))
        if _is_bulk_contact(contact):
            return _unsupported("bulk_contact", "一次只能创建一个微信发送任务。没有发送消息。")
        return _missing_message(contact)

    message_only = _MESSAGE_ONLY_PATTERN.match(normalized)
    if message_only is not None:
        return WeChatSendResolution(
            status="needs_clarification",
            reason_code="missing_contact",
            user_message="要发送给哪个微信联系人？没有创建发送任务。",
            message_text=_strip_confirmation_hint(_clean_slot(message_only.group("message"))),
            missing_slots=("contactDisplayName",),
        )

    if _contains_wechat_send_intent(normalized):
        return _unsupported(
            "unsupported_wechat_send_shape",
            "这个微信发送请求不够明确。请说明联系人和消息内容。没有发送消息。",
        )
    return None


def resolve_wechat_send_pending_clarification(
    content: str,
    *,
    contact_display_name: str | None,
    message_text: str | None,
    missing_slots: tuple[str, ...],
) -> WeChatSendResolution:
    """Complete a pending WeChat-send clarification from the next user answer."""

    fresh = resolve_wechat_send_input(content)
    if fresh is not None:
        if fresh.status == "ready" or fresh.status == "unsupported":
            return fresh
        if fresh.status == "needs_clarification":
            if fresh.missing_slots == ("messageText",) and message_text is None:
                assert fresh.contact_display_name is not None
                return _missing_message(fresh.contact_display_name)
            contact_display_name = fresh.contact_display_name or contact_display_name
            message_text = fresh.message_text or message_text

    if "messageText" in missing_slots and contact_display_name is not None:
        message = message_text or _strip_confirmation_hint(_clean_slot(content))
        if not message:
            return _missing_message(contact_display_name)
        return WeChatSendResolution(
            status="ready",
            reason_code="wechat_send_ready",
            user_message="已补全微信发送消息内容，发送前仍需要用户确认。",
            contact_display_name=contact_display_name,
            message_text=message,
        )

    if "contactDisplayName" in missing_slots and message_text is not None:
        contact = contact_display_name or _clean_slot(content)
        if _is_bulk_contact(contact):
            return _unsupported("bulk_contact", "一次只能创建一个微信发送任务。没有发送消息。")
        if not contact:
            return WeChatSendResolution(
                status="needs_clarification",
                reason_code="missing_contact",
                user_message="要发送给哪个微信联系人？没有创建发送任务。",
                message_text=message_text,
                missing_slots=("contactDisplayName",),
            )
        return WeChatSendResolution(
            status="ready",
            reason_code="wechat_send_ready",
            user_message="已补全微信联系人，发送前仍需要用户确认。",
            contact_display_name=contact,
            message_text=message_text,
        )

    return fresh or WeChatSendResolution(
        status="needs_clarification",
        reason_code="missing_contact_message",
        user_message="请说明微信联系人和消息内容。没有创建发送任务。",
        missing_slots=("contactDisplayName", "messageText"),
    )


def wechat_send_execution_payload(resolution: WeChatSendResolution) -> dict[str, object]:
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


def _normalize(content: str) -> str:
    return " ".join(content.strip().split())


def _looks_like_question(content: str) -> bool:
    return content.startswith(_QUESTION_PREFIXES)


def _clean_slot(value: str) -> str:
    return value.strip(" \t\r\n：:，,。.")


def _strip_confirmation_hint(message: str) -> str:
    return _clean_slot(_CONFIRMATION_HINT_RE.sub("", message))


def _is_bulk_contact(contact: str) -> bool:
    padded = f" {contact} "
    return any(marker in padded for marker in _BULK_CONTACT_MARKERS) or "都" in contact


def _contains_wechat_send_intent(content: str) -> bool:
    return "微信" in content and any(verb in content for verb in _SEND_VERBS)


def _missing_message(contact: str) -> WeChatSendResolution:
    return WeChatSendResolution(
        status="needs_clarification",
        reason_code="missing_message",
        user_message=f"要发送给{contact}的消息内容是什么？没有创建发送任务。",
        contact_display_name=contact,
        missing_slots=("messageText",),
    )


def _unsupported(reason_code: str, user_message: str) -> WeChatSendResolution:
    return WeChatSendResolution(
        status="unsupported",
        reason_code=reason_code,
        user_message=user_message,
    )


__all__ = [
    "WECHAT_SEND_CAPABILITY",
    "WECHAT_SEND_TASK_TYPE",
    "WeChatSendResolution",
    "resolve_wechat_send_pending_clarification",
    "resolve_wechat_send_input",
    "wechat_send_execution_payload",
    "wechat_send_task_request",
]
