from __future__ import annotations

import subprocess

from pytest import MonkeyPatch

from taskweavn.integrations.wechat_desktop import macos_driver
from taskweavn.integrations.wechat_desktop.macos_driver import MacOSWeChatSearchDriver


def test_resolve_contact_fails_before_search_when_wechat_window_unavailable(
    monkeypatch: MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_run_osascript(
        script: str, timeout_seconds: float
    ) -> subprocess.CompletedProcess[str]:
        del timeout_seconds
        calls.append(script)
        return subprocess.CompletedProcess(
            ["osascript", "-e", script],
            0,
            stdout=(
                "status=needs_user\n"
                "reason=WeChat main window is unavailable; "
                "open the main WeChat window before sending.\n"
                "error=Can’t get front window"
            ),
            stderr="",
        )

    monkeypatch.setattr(
        "taskweavn.integrations.wechat_desktop.macos_driver.platform.system",
        lambda: "Darwin",
    )
    monkeypatch.setattr(macos_driver, "_run_osascript", fake_run_osascript)

    result = MacOSWeChatSearchDriver().resolve_contact(
        app_name="WeChat",
        contact_display_name="文件传输助手",
        timeout_seconds=40.0,
    )

    assert result.status == "needs_user"
    assert result.summary == (
        "WeChat main window is unavailable; open the main WeChat window before sending."
    )
    assert result.diagnostics == {
        "reason": (
            "WeChat main window is unavailable; open the main WeChat window before sending."
        ),
        "error": "Can’t get front window",
    }
    assert len(calls) == 1


def test_resolve_contact_continues_to_search_after_wechat_window_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_run_osascript(
        script: str, timeout_seconds: float
    ) -> subprocess.CompletedProcess[str]:
        del timeout_seconds
        calls.append(script)
        if len(calls) == 1:
            return subprocess.CompletedProcess(
                ["osascript", "-e", script],
                0,
                stdout="status=ready\nwindow_position=0, 0\nwindow_size=1200, 800",
                stderr="",
            )
        if len(calls) == 2:
            return subprocess.CompletedProcess(
                ["osascript", "-e", script],
                0,
                stdout="status=ready\nfocus=搜索 文件传输助手",
                stderr="",
            )
        return subprocess.CompletedProcess(
            ["osascript", "-e", script],
            0,
            stdout=(
                "status=resolved\n"
                "display_name=文件传输助手\n"
                "stable_hint=wechat:search:文件传输助手\n"
                "observation_ref=wechat-search-selected"
            ),
            stderr="",
        )

    monkeypatch.setattr(
        "taskweavn.integrations.wechat_desktop.macos_driver.platform.system",
        lambda: "Darwin",
    )
    monkeypatch.setattr(
        "taskweavn.integrations.wechat_desktop.macos_driver.time.sleep",
        lambda seconds: None,
    )
    monkeypatch.setattr(macos_driver, "_run_osascript", fake_run_osascript)

    result = MacOSWeChatSearchDriver().resolve_contact(
        app_name="WeChat",
        contact_display_name="文件传输助手",
        timeout_seconds=40.0,
    )

    assert result.status == "resolved"
    assert result.display_name == "文件传输助手"
    assert len(calls) == 3


def test_submit_message_reports_keyboard_submit_metadata(
    monkeypatch: MonkeyPatch,
) -> None:
    scripts: list[str] = []

    def fake_run_osascript(
        script: str, timeout_seconds: float
    ) -> subprocess.CompletedProcess[str]:
        del timeout_seconds
        scripts.append(script)
        return subprocess.CompletedProcess(
            ["osascript", "-e", script],
            0,
            stdout=(
                "status=sent\n"
                "observation_ref=wechat-keyboard-submit\n"
                "phase=keyboard_submit\n"
                "send_method=keyboard_return\n"
                "send_attempted=true\n"
                "input_focus_verified=true\n"
                "input_content_verified=false\n"
                "focus_before=AXTextArea 文件传输助手 文本输入区"
            ),
            stderr="",
        )

    monkeypatch.setattr(
        "taskweavn.integrations.wechat_desktop.macos_driver.platform.system",
        lambda: "Darwin",
    )
    monkeypatch.setattr(macos_driver, "_run_osascript", fake_run_osascript)

    result = MacOSWeChatSearchDriver().submit_message(
        app_name="WeChat",
        contact_display_name="文件传输助手",
        message_preview="hello",
        timeout_seconds=10.0,
    )

    assert result.status == "sent"
    assert result.observation_ref == "wechat-keyboard-submit"
    assert result.diagnostics == {
        "phase": "keyboard_submit",
        "send_method": "keyboard_return",
        "send_attempted": "true",
        "input_focus_verified": "true",
        "input_content_verified": "false",
        "focus_before": "AXTextArea 文件传输助手 文本输入区",
    }
    assert len(scripts) == 1


def test_submit_message_script_uses_minimal_keyboard_return_without_click() -> None:
    script = macos_driver._submit_message_script(  # noqa: SLF001 - regression guard.
        "WeChat",
        "文件传输助手",
        "hello",
    )

    assert "key code 36" in script
    assert "click at" not in script
    assert "AXFocusedUIElement" not in script
    assert "input_focus_verified=prior_draft_observation" in script


def test_focus_message_input_script_clears_existing_draft_before_typing() -> None:
    script = macos_driver._focus_message_input_script(  # noqa: SLF001 - regression guard.
        "WeChat",
        "文件传输助手",
    )

    assert 'keystroke "a" using command down' in script
    assert "key code 51" in script
    assert "input_cleared=true" in script
