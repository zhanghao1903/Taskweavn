from __future__ import annotations

from typing import Any, cast

from taskweavn.integrations.wechat_desktop import (
    FakeWeChatDesktopAdapter,
    WeChatContactCandidate,
    WeChatContactResolution,
    WeChatContactSearchResult,
    WeChatDesktopAdapter,
    WeChatDesktopAdapterConfig,
    WeChatDraftState,
    WeChatInputFocusResult,
    WeChatMessageSubmitResult,
    WeChatSendActionFingerprint,
    WeChatSendTaskInput,
    WeChatWindowReadinessResult,
    wechat_message_hash,
)
from taskweavn.tools import ScriptedComputerUseBackend
from taskweavn.types import ComputerUseObservation


def _observation(
    *,
    operation: str,
    status: str = "ok",
    summary: str = "ok",
    metadata: dict[str, object] | None = None,
    text_extract: str | None = None,
) -> ComputerUseObservation:
    return ComputerUseObservation(
        operation=cast(Any, operation),
        status=cast(Any, status),
        success=status == "ok",
        summary=summary,
        metadata=metadata or {},
        text_extract=text_extract,
    )


class FakeSearchDriver:
    def __init__(
        self,
        *,
        window_result: WeChatWindowReadinessResult | None = None,
        search_result: WeChatContactSearchResult | None = None,
        focus_result: WeChatInputFocusResult | None = None,
        submit_result: WeChatMessageSubmitResult | None = None,
    ) -> None:
        self.window_result = window_result or WeChatWindowReadinessResult(
            status="ready",
            summary="window ready",
        )
        self.search_result = search_result or WeChatContactSearchResult(
            status="resolved",
            summary="selected",
            display_name="张三",
            stable_hint="wechat:search:张三",
            observation_ref="wechat-search-selected",
        )
        self.focus_result = focus_result or WeChatInputFocusResult(
            status="focused",
            summary="focused",
            observation_ref="wechat-message-input-focused",
        )
        self.submit_result = submit_result or WeChatMessageSubmitResult(
            status="sent",
            summary="keyboard submitted",
            observation_ref="wechat-keyboard-submit",
            diagnostics={
                "send_method": "keyboard_return",
                "send_attempted": "true",
                "phase": "keyboard_submit",
            },
        )
        self.calls: list[tuple[str, dict[str, object]]] = []

    def window_readiness(
        self,
        *,
        app_name: str,
        timeout_seconds: float,
    ) -> WeChatWindowReadinessResult:
        self.calls.append(
            (
                "window_readiness",
                {
                    "app_name": app_name,
                    "timeout_seconds": timeout_seconds,
                },
            )
        )
        return self.window_result

    def resolve_contact(
        self,
        *,
        app_name: str,
        contact_display_name: str,
        timeout_seconds: float,
    ) -> WeChatContactSearchResult:
        self.calls.append(
            (
                "resolve_contact",
                {
                    "app_name": app_name,
                    "contact_display_name": contact_display_name,
                    "timeout_seconds": timeout_seconds,
                },
            )
        )
        return self.search_result

    def focus_message_input(
        self,
        *,
        app_name: str,
        contact_display_name: str,
        timeout_seconds: float,
    ) -> WeChatInputFocusResult:
        self.calls.append(
            (
                "focus_message_input",
                {
                    "app_name": app_name,
                    "contact_display_name": contact_display_name,
                    "timeout_seconds": timeout_seconds,
                },
            )
        )
        return self.focus_result

    def submit_message(
        self,
        *,
        app_name: str,
        contact_display_name: str,
        message_preview: str,
        timeout_seconds: float,
    ) -> WeChatMessageSubmitResult:
        self.calls.append(
            (
                "submit_message",
                {
                    "app_name": app_name,
                    "contact_display_name": contact_display_name,
                    "message_preview": message_preview,
                    "timeout_seconds": timeout_seconds,
                },
            )
        )
        return self.submit_result


def test_wechat_readiness_maps_ready_metadata() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[
            _observation(
                operation="readiness",
                metadata={"wechat_status": "ready"},
                summary="computer-use ready",
            )
        ]
    )
    adapter = WeChatDesktopAdapter(backend)

    readiness = adapter.readiness()

    assert readiness.status == "ready"
    assert readiness.app_name == "WeChat"
    assert readiness.summary == "WeChat Desktop is ready for draft-only automation."


def test_wechat_readiness_maps_login_required() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[
            _observation(
                operation="readiness",
                metadata={"wechat_status": "not_logged_in"},
            )
        ]
    )
    adapter = WeChatDesktopAdapter(backend)

    readiness = adapter.readiness()

    assert readiness.status == "not_logged_in"
    assert "log in" in readiness.summary


def test_wechat_open_or_focus_uses_configured_app_name() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[_observation(operation="open_app", summary="opened")]
    )
    adapter = WeChatDesktopAdapter(
        backend,
        config=WeChatDesktopAdapterConfig(app_name="WeChat Beta"),
    )

    result = adapter.open_or_focus()

    assert result.status == "ok"
    assert backend.actions[0].operation == "open_app"
    assert backend.actions[0].target == "WeChat Beta"


def test_wechat_window_readiness_falls_back_to_observe_after_geometry_timeout() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[
            _observation(
                operation="observe",
                summary="Frontmost app: WeChat. Window: 文件传输助手.",
                metadata={
                    "frontmost_app": "WeChat",
                    "window_title": "文件传输助手",
                },
                text_extract="Frontmost app: WeChat. Window: 文件传输助手.",
            )
        ]
    )
    driver = FakeSearchDriver(
        window_result=WeChatWindowReadinessResult(
            status="needs_user",
            summary="WeChat main window readiness AppleScript timed out.",
            diagnostics={
                "phase": "window_readiness",
                "script_phase": "window_geometry",
                "failure_kind": "applescript_timeout",
            },
        )
    )
    adapter = WeChatDesktopAdapter(backend, contact_search_driver=driver)

    result = adapter.window_readiness()

    assert result.status == "ok"
    assert result.summary == "WeChat main window is observable through fallback observe."
    assert result.text_extract == "Frontmost app: WeChat. Window: 文件传输助手."
    assert result.metadata == {
        "phase": "window_readiness",
        "script_phase": "window_geometry",
        "failure_kind": "applescript_timeout",
        "fallback": "observe",
        "fallback_status": "ok",
        "fallback_summary": "Frontmost app: WeChat. Window: 文件传输助手.",
        "frontmost_app": "WeChat",
        "window_title": "文件传输助手",
    }
    assert backend.actions[0].operation == "observe"
    assert backend.actions[0].target == "WeChat"
    assert backend.actions[0].metadata["phase"] == "window_readiness_fallback"


def test_wechat_window_readiness_fallback_requires_window_title() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[
            _observation(
                operation="observe",
                summary="Frontmost app: WeChat.",
                metadata={
                    "frontmost_app": "WeChat",
                    "window_title": "",
                },
                text_extract="Frontmost app: WeChat.",
            )
        ]
    )
    driver = FakeSearchDriver(
        window_result=WeChatWindowReadinessResult(
            status="needs_user",
            summary="WeChat main window readiness AppleScript timed out.",
            diagnostics={
                "phase": "window_readiness",
                "script_phase": "window_geometry",
                "failure_kind": "applescript_timeout",
            },
        )
    )
    adapter = WeChatDesktopAdapter(backend, contact_search_driver=driver)

    result = adapter.window_readiness()

    assert result.status == "needs_user"
    assert result.summary == (
        "WeChat is frontmost but no observable main window title was found; "
        "open the main WeChat chat window before sending."
    )
    assert result.metadata is not None
    assert result.metadata["fallback"] == "observe"
    assert result.metadata["frontmost_app"] == "WeChat"
    assert result.metadata["window_title"] == ""


def test_wechat_resolve_contact_selects_single_high_confidence_candidate() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[
            _observation(
                operation="observe",
                metadata={
                    "contact_candidates": [
                        {
                            "display_name": "张三",
                            "subtitle": "合作达人",
                            "stable_hint": "wechat:zhangsan",
                            "confidence": 0.93,
                        }
                    ]
                },
            )
        ]
    )
    adapter = WeChatDesktopAdapter(backend)

    resolution = adapter.resolve_contact(
        WeChatSendTaskInput(contact_display_name="张三", message_text="你好")
    )

    assert resolution.status == "resolved"
    assert resolution.selected is not None
    assert resolution.selected.summary() == "张三 (合作达人)"
    assert backend.actions[0].operation == "observe"
    assert backend.actions[0].target == "WeChat"
    assert backend.actions[0].metadata["contact_display_name"] == "张三"


def test_wechat_resolve_contact_reports_ambiguous_candidates() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[
            _observation(
                operation="observe",
                metadata={
                    "contact_candidates": [
                        {"display_name": "张三", "confidence": 0.9},
                        {"display_name": "张三-供应商", "confidence": 0.86},
                    ]
                },
            )
        ]
    )
    adapter = WeChatDesktopAdapter(backend)

    resolution = adapter.resolve_contact(
        WeChatSendTaskInput(contact_display_name="张三", message_text="你好")
    )

    assert resolution.status == "ambiguous"
    assert resolution.selected is None
    assert len(resolution.candidates) == 2


def test_wechat_resolve_contact_reports_not_found() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[_observation(operation="observe", metadata={"contact_candidates": []})]
    )
    adapter = WeChatDesktopAdapter(backend)

    resolution = adapter.resolve_contact(
        WeChatSendTaskInput(contact_display_name="不存在", message_text="你好")
    )

    assert resolution.status == "not_found"
    assert resolution.reason == "No matching WeChat contact candidate was observed."


def test_wechat_resolve_contact_uses_search_driver_when_observe_has_no_candidates() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[_observation(operation="observe", metadata={"contact_candidates": []})]
    )
    driver = FakeSearchDriver()
    adapter = WeChatDesktopAdapter(backend, contact_search_driver=driver)

    resolution = adapter.resolve_contact(
        WeChatSendTaskInput(contact_display_name="张三", message_text="你好")
    )

    assert resolution.status == "resolved"
    assert resolution.selected is not None
    assert resolution.selected.display_name == "张三"
    assert resolution.selected.stable_hint == "wechat:search:张三"
    assert resolution.observation_ref == "wechat-search-selected"
    assert driver.calls == [
        (
            "resolve_contact",
                {
                    "app_name": "WeChat",
                    "contact_display_name": "张三",
                    "timeout_seconds": 40.0,
                },
            )
        ]


def test_wechat_resolve_contact_uses_search_driver_when_observe_loses_frontmost() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[
            _observation(
                operation="observe",
                status="needs_user",
                summary="Target app is not frontmost: expected WeChat, got Codex.",
                metadata={"failure_kind": "target_not_frontmost"},
            )
        ]
    )
    driver = FakeSearchDriver()
    adapter = WeChatDesktopAdapter(backend, contact_search_driver=driver)

    resolution = adapter.resolve_contact(
        WeChatSendTaskInput(contact_display_name="张三", message_text="你好")
    )

    assert resolution.status == "resolved"
    assert resolution.selected is not None
    assert resolution.selected.display_name == "张三"
    assert resolution.observation_ref == "wechat-search-selected"
    assert driver.calls == [
        (
            "resolve_contact",
            {
                "app_name": "WeChat",
                "contact_display_name": "张三",
                "timeout_seconds": 40.0,
            },
        )
    ]


def test_wechat_resolve_contact_does_not_use_search_driver_for_permission_failure() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[
            _observation(
                operation="observe",
                status="not_available",
                summary="Accessibility permission is missing.",
                metadata={"failure_kind": "missing_accessibility"},
            )
        ]
    )
    driver = FakeSearchDriver()
    adapter = WeChatDesktopAdapter(backend, contact_search_driver=driver)

    resolution = adapter.resolve_contact(
        WeChatSendTaskInput(contact_display_name="张三", message_text="你好")
    )

    assert resolution.status == "needs_user"
    assert resolution.reason == "Accessibility permission is missing."
    assert driver.calls == []


def test_wechat_resolve_contact_maps_search_driver_needs_user() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[_observation(operation="observe", metadata={"contact_candidates": []})]
    )
    driver = FakeSearchDriver(
        search_result=WeChatContactSearchResult(
            status="needs_user",
            summary="search focus not verified",
            observation_ref="wechat-search-focus",
            diagnostics={"stderr": "Can’t get group 1 of window 1"},
        )
    )
    adapter = WeChatDesktopAdapter(backend, contact_search_driver=driver)

    resolution = adapter.resolve_contact(
        WeChatSendTaskInput(contact_display_name="张三", message_text="你好")
    )

    assert resolution.status == "needs_user"
    assert resolution.reason == "search focus not verified"
    assert resolution.observation_ref == "wechat-search-focus"
    assert resolution.diagnostics == {"stderr": "Can’t get group 1 of window 1"}


def test_wechat_resolve_contact_low_confidence_needs_user() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[
            _observation(
                operation="observe",
                metadata={
                    "contact_candidates": [{"display_name": "张三", "confidence": 0.4}]
                },
            )
        ]
    )
    adapter = WeChatDesktopAdapter(backend)

    resolution = adapter.resolve_contact(
        WeChatSendTaskInput(contact_display_name="张三", message_text="你好")
    )

    assert resolution.status == "needs_user"
    assert "below the safe threshold" in str(resolution.reason)


def test_wechat_draft_message_types_exact_text_without_send() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[_observation(operation="type_text", summary="typed")]
    )
    adapter = WeChatDesktopAdapter(backend)
    resolution = WeChatContactResolution(
        status="resolved",
        selected=WeChatContactCandidate(display_name="张三", confidence=0.95),
    )

    draft = adapter.draft_message(resolution, "你好，样品已寄出。")

    assert draft.status == "drafted"
    assert draft.contact_summary == "张三"
    assert draft.message_hash == wechat_message_hash("你好，样品已寄出。")
    assert draft.message_preview == "你好，样品已寄出。"
    assert backend.actions[0].operation == "type_text"
    assert backend.actions[0].text == "你好，样品已寄出。"
    assert backend.actions[0].metadata["draft_only"] is True


def test_wechat_draft_message_focuses_message_input_with_search_driver() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[_observation(operation="type_text", summary="typed")]
    )
    driver = FakeSearchDriver()
    adapter = WeChatDesktopAdapter(backend, contact_search_driver=driver)
    resolution = WeChatContactResolution(
        status="resolved",
        selected=WeChatContactCandidate(display_name="张三", confidence=0.95),
    )

    draft = adapter.draft_message(resolution, "你好，样品已寄出。")

    assert draft.status == "drafted"
    assert driver.calls == [
        (
            "focus_message_input",
                {
                    "app_name": "WeChat",
                    "contact_display_name": "张三",
                    "timeout_seconds": 40.0,
                },
            )
        ]
    assert backend.actions[0].operation == "type_text"


def test_wechat_draft_message_stops_when_message_input_focus_fails() -> None:
    backend = ScriptedComputerUseBackend()
    driver = FakeSearchDriver(
        focus_result=WeChatInputFocusResult(
            status="needs_user",
            summary="selected chat did not contain contact",
            observation_ref="wechat-message-input-focus",
        )
    )
    adapter = WeChatDesktopAdapter(backend, contact_search_driver=driver)
    resolution = WeChatContactResolution(
        status="resolved",
        selected=WeChatContactCandidate(display_name="张三", confidence=0.95),
    )

    draft = adapter.draft_message(resolution, "你好")

    assert draft.status == "failed"
    assert draft.reason == "selected chat did not contain contact"
    assert draft.draft_observation_ref == "wechat-message-input-focus"
    assert backend.actions == []


def test_wechat_draft_message_requires_resolved_contact() -> None:
    backend = ScriptedComputerUseBackend()
    adapter = WeChatDesktopAdapter(backend)

    draft = adapter.draft_message(
        WeChatContactResolution(status="ambiguous"),
        "你好",
    )

    assert draft.status == "failed"
    assert "exactly one contact" in str(draft.reason)
    assert backend.actions == []


def test_wechat_draft_message_rejects_too_long_text_without_typing() -> None:
    backend = ScriptedComputerUseBackend()
    adapter = WeChatDesktopAdapter(
        backend,
        config=WeChatDesktopAdapterConfig(max_message_chars=4),
    )
    resolution = WeChatContactResolution(
        status="resolved",
        selected=WeChatContactCandidate(display_name="张三", confidence=0.95),
    )

    draft = adapter.draft_message(resolution, "12345")

    assert draft.status == "failed"
    assert "exceeds WeChat draft limit" in str(draft.reason)
    assert backend.actions == []


def test_wechat_send_after_confirmation_uses_keyboard_submit_with_search_driver() -> None:
    backend = ScriptedComputerUseBackend()
    driver = FakeSearchDriver()
    adapter = WeChatDesktopAdapter(backend, contact_search_driver=driver)
    fingerprint = WeChatSendActionFingerprint.from_draft(
        execution_id="exec-1",
        idempotency_key="idem-1",
        draft_state=WeChatDraftState(
            status="drafted",
            contact_summary="张三",
            message_hash=wechat_message_hash("你好"),
            message_preview="你好",
            draft_observation_ref="observe:draft-1",
        ),
        app_identity="com.tencent.xinWeChat",
    )

    result = adapter.send_after_confirmation(
        fingerprint,
        contact_summary="张三",
        message_preview="你好",
    )

    assert result.status == "sent"
    assert result.send_observation_ref == "wechat-keyboard-submit"
    assert result.metadata is not None
    assert result.metadata["send_method"] == "keyboard_return"
    assert result.metadata["send_attempted"] == "true"
    assert result.metadata["phase"] == "keyboard_submit"
    assert driver.calls[-1] == (
        "submit_message",
        {
            "app_name": "WeChat",
            "contact_display_name": "张三",
            "message_preview": "你好",
            "timeout_seconds": 10.0,
        },
    )
    assert backend.actions == []


def test_wechat_send_after_confirmation_falls_back_to_press_key_without_driver() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[_observation(operation="press_key", summary="pressed return")]
    )
    adapter = WeChatDesktopAdapter(backend)
    fingerprint = WeChatSendActionFingerprint.from_draft(
        execution_id="exec-1",
        idempotency_key="idem-1",
        draft_state=WeChatDraftState(
            status="drafted",
            contact_summary="张三",
            message_hash=wechat_message_hash("你好"),
            message_preview="你好",
            draft_observation_ref="observe:draft-1",
        ),
        app_identity="com.tencent.xinWeChat",
    )

    result = adapter.send_after_confirmation(
        fingerprint,
        contact_summary="张三",
        message_preview="你好",
    )

    assert result.status == "sent"
    assert backend.actions[0].operation == "press_key"
    assert backend.actions[0].keys == ("return",)
    assert backend.actions[0].metadata["action_fingerprint"] == fingerprint.digest()
    assert backend.actions[0].metadata["confirmation_required"] is True
    assert backend.actions[0].metadata["confirmed_by_user"] is True
    assert backend.actions[0].metadata["send_method"] == "keyboard_return"
    assert backend.actions[0].metadata["send_attempted"] is True


def test_wechat_send_after_confirmation_unknown_when_click_not_confirmed() -> None:
    backend = ScriptedComputerUseBackend(
        responses=[_observation(operation="press_key", status="failed", summary="lost focus")]
    )
    adapter = WeChatDesktopAdapter(backend)
    fingerprint = WeChatSendActionFingerprint.from_draft(
        execution_id="exec-1",
        idempotency_key="idem-1",
        draft_state=WeChatDraftState(
            status="drafted",
            contact_summary="张三",
            message_hash=wechat_message_hash("你好"),
            message_preview="你好",
            draft_observation_ref="observe:draft-1",
        ),
        app_identity="com.tencent.xinWeChat",
    )

    result = adapter.send_after_confirmation(
        fingerprint,
        contact_summary="张三",
        message_preview="你好",
    )

    assert result.status == "unknown"
    assert "manual review" in result.summary
    assert result.reason == "lost focus"


def test_wechat_send_after_confirmation_not_sent_when_pre_submit_verification_fails() -> None:
    backend = ScriptedComputerUseBackend()
    driver = FakeSearchDriver(
        submit_result=WeChatMessageSubmitResult(
            status="not_sent",
            summary="message input focus could not be verified",
            diagnostics={
                "failure_kind": "message_input_not_focused",
                "send_attempted": "false",
                "phase": "pre_submit",
            },
        )
    )
    adapter = WeChatDesktopAdapter(backend, contact_search_driver=driver)
    fingerprint = WeChatSendActionFingerprint.from_draft(
        execution_id="exec-1",
        idempotency_key="idem-1",
        draft_state=WeChatDraftState(
            status="drafted",
            contact_summary="张三",
            message_hash=wechat_message_hash("你好"),
            message_preview="你好",
            draft_observation_ref="observe:draft-1",
        ),
        app_identity="com.tencent.xinWeChat",
    )

    result = adapter.send_after_confirmation(
        fingerprint,
        contact_summary="张三",
        message_preview="你好",
    )

    assert result.status == "not_sent"
    assert result.metadata is not None
    assert result.metadata["failure_kind"] == "message_input_not_focused"
    assert result.metadata["send_attempted"] == "false"
    assert backend.actions == []


def test_fake_wechat_adapter_records_draft_only_calls() -> None:
    fake = FakeWeChatDesktopAdapter(
        contact_resolution=WeChatContactResolution(
            status="resolved",
            selected=WeChatContactCandidate(display_name="张三", confidence=1.0),
        )
    )
    task_input = WeChatSendTaskInput(contact_display_name="张三", message_text="你好")

    assert fake.readiness().status == "ready"
    assert fake.open_or_focus().status == "ok"
    resolution = fake.resolve_contact(task_input)
    draft = fake.draft_message(resolution, task_input.message_text)

    assert draft.status == "drafted"
    assert [call[0] for call in fake.calls] == [
        "readiness",
        "open_or_focus",
        "resolve_contact",
        "draft_message",
    ]
