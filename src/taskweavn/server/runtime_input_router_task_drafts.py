"""Adapters from LLM Router task drafts to bounded runtime task inputs."""

from __future__ import annotations

from taskweavn.server.runtime_input_llm_router import RouterTaskRequestDraft
from taskweavn.server.runtime_input_wechat import (
    WECHAT_SEND_TASK_TYPE,
    WeChatSendResolution,
)


def wechat_resolution_from_task_request_draft(
    task_request_draft: RouterTaskRequestDraft,
) -> WeChatSendResolution | None:
    """Convert a validated WeChat task draft into existing WeChat dispatch input."""

    if task_request_draft.task_type != WECHAT_SEND_TASK_TYPE:
        return None
    contact = _required_input_str(task_request_draft, "contactDisplayName")
    message = _required_input_str(task_request_draft, "messageText")
    return WeChatSendResolution(
        status="ready",
        reason_code="wechat_send_ready_from_router_task_draft",
        user_message="已识别为微信发送任务，发送前仍需要用户确认。",
        contact_display_name=contact,
        message_text=message,
    )


def _required_input_str(
    task_request_draft: RouterTaskRequestDraft,
    key: str,
) -> str:
    value = task_request_draft.input.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Router task request draft requires non-empty {key}")
    return value.strip()


__all__ = ["wechat_resolution_from_task_request_draft"]
