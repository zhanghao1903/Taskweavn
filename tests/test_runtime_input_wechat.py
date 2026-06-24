from taskweavn.server.runtime_input_wechat import (
    WECHAT_SEND_CAPABILITY,
    WECHAT_SEND_TASK_TYPE,
    resolve_wechat_send_input,
    resolve_wechat_send_pending_clarification,
    wechat_send_execution_payload,
    wechat_send_task_request,
)


def test_wechat_send_resolver_extracts_contact_message_and_strips_confirmation_hint() -> None:
    result = resolve_wechat_send_input(
        "给微信文件传输助手发送一条消息：Plato 本地发送测试。发送前让我确认。"
    )

    assert result is not None
    assert result.status == "ready"
    assert result.contact_display_name == "文件传输助手"
    assert result.message_text == "Plato 本地发送测试"


def test_wechat_send_resolver_allows_question_mark_inside_message() -> None:
    result = resolve_wechat_send_input("给微信文件传输助手发送一条消息：你好吗？")

    assert result is not None
    assert result.status == "ready"
    assert result.message_text == "你好吗？"


def test_wechat_send_resolver_requests_missing_message() -> None:
    result = resolve_wechat_send_input("给微信文件传输助手发消息")

    assert result is not None
    assert result.status == "needs_clarification"
    assert result.contact_display_name == "文件传输助手"
    assert result.missing_slots == ("messageText",)


def test_wechat_send_resolver_requests_missing_contact() -> None:
    result = resolve_wechat_send_input("帮我微信发送消息：明天开会")

    assert result is not None
    assert result.status == "needs_clarification"
    assert result.message_text == "明天开会"
    assert result.missing_slots == ("contactDisplayName",)


def test_wechat_send_pending_clarification_completes_missing_message() -> None:
    result = resolve_wechat_send_pending_clarification(
        "Plato 本地发送测试。发送前让我确认。",
        contact_display_name="文件传输助手",
        message_text=None,
        missing_slots=("messageText",),
    )

    assert result.status == "ready"
    assert result.contact_display_name == "文件传输助手"
    assert result.message_text == "Plato 本地发送测试"


def test_wechat_send_pending_clarification_completes_missing_contact() -> None:
    result = resolve_wechat_send_pending_clarification(
        "文件传输助手",
        contact_display_name=None,
        message_text="明天开会",
        missing_slots=("contactDisplayName",),
    )

    assert result.status == "ready"
    assert result.contact_display_name == "文件传输助手"
    assert result.message_text == "明天开会"


def test_wechat_pending_clarification_rejects_new_incomplete_intent() -> None:
    result = resolve_wechat_send_pending_clarification(
        "给微信张三发消息",
        contact_display_name="文件传输助手",
        message_text=None,
        missing_slots=("messageText",),
    )

    assert result.status == "needs_clarification"
    assert result.contact_display_name == "张三"
    assert result.missing_slots == ("messageText",)


def test_wechat_send_resolver_rejects_bulk_contact() -> None:
    result = resolve_wechat_send_input("给微信张三和李四发送消息：明天开会")

    assert result is not None
    assert result.status == "unsupported"
    assert result.reason_code == "bulk_contact"


def test_wechat_send_resolver_leaves_wechat_questions_to_question_router() -> None:
    assert resolve_wechat_send_input("怎么用微信发消息？") is None


def test_wechat_send_execution_payload_maps_to_contract_execution_task() -> None:
    result = resolve_wechat_send_input("在微信给文件传输助手发送：hello")
    assert result is not None
    assert result.status == "ready"

    payload = wechat_send_execution_payload(result)

    assert payload["title"] == "Send WeChat message to 文件传输助手"
    assert payload["requiredCapability"] == WECHAT_SEND_CAPABILITY
    assert WECHAT_SEND_TASK_TYPE in str(payload["instructions"])
    assert "文件传输助手" in str(payload["instructions"])
    assert "hello" in str(payload["instructions"])
    assert "Do not send without user confirmation." in payload["constraints"]


def test_wechat_send_task_request_maps_to_execution_plane_contract() -> None:
    result = resolve_wechat_send_input("给微信文件传输助手发送消息：hello")
    assert result is not None
    assert result.status == "ready"

    request = wechat_send_task_request(
        result,
        command_id="route-1",
        session_id="session-1",
        workspace_id="workspace-1",
        original_content="给微信文件传输助手发送消息：hello",
    )

    assert request.idempotency_key == "runtime-input:session-1:route-1"
    assert request.requester.kind == "plato"
    assert request.requester.id == "runtime-input-router"
    assert request.external_ref is not None
    assert request.external_ref.kind == "runtime_input"
    assert request.task_type == WECHAT_SEND_TASK_TYPE
    assert request.input["contactDisplayName"] == "文件传输助手"
    assert request.input["messageText"] == "hello"
    assert request.policy.required_capability == WECHAT_SEND_CAPABILITY
    assert request.policy.requires_human_confirmation is True
    assert request.policy.risk_level == "high"
    assert request.metadata["sessionId"] == "session-1"
    assert request.metadata["source"] == "main_page_runtime_input"
    assert "originalUserInputHash" in request.metadata
