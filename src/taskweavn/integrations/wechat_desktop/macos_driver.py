"""macOS-specific WeChat UI driver for deterministic contact selection."""

# ruff: noqa: E501

from __future__ import annotations

import platform
import subprocess
import time
from dataclasses import dataclass

WECHAT_MAIN_WINDOW_SETUP_HINT = (
    "Open the WeChat main window or chat list, make sure WeChat is logged in "
    "and unlocked, then rerun helper-backed preflight before publishing a task."
)
WECHAT_MAIN_WINDOW_RECOVERY_ACTIONS = (
    "open_wechat_main_window",
    "unlock_or_login_wechat",
    "rerun_helper_preflight",
)


@dataclass(frozen=True)
class WeChatContactSearchResult:
    """Result of selecting one contact in WeChat Desktop."""

    status: str
    summary: str
    display_name: str | None = None
    stable_hint: str | None = None
    observation_ref: str | None = None
    diagnostics: dict[str, str] | None = None


@dataclass(frozen=True)
class WeChatInputFocusResult:
    """Result of focusing the message input for an already selected chat."""

    status: str
    summary: str
    observation_ref: str | None = None
    diagnostics: dict[str, str] | None = None


@dataclass(frozen=True)
class WeChatMessageSubmitResult:
    """Result of submitting an already drafted message in WeChat Desktop."""

    status: str
    summary: str
    observation_ref: str | None = None
    diagnostics: dict[str, str] | None = None


@dataclass(frozen=True)
class WeChatWindowReadinessResult:
    """Result of checking whether the WeChat main window is automation-ready."""

    status: str
    summary: str
    diagnostics: dict[str, str] | None = None


class MacOSWeChatSearchDriver:
    """Small WeChat-specific driver over bounded AppleScript operations.

    The driver is intentionally not a general computer-use API. It performs
    only the deterministic setup and confirmation-gated submit steps required
    by Plato: locate a contact, focus the message input, and press Return only
    after the already-drafted input is verified. It never clicks a send button.
    """

    def resolve_contact(
        self,
        *,
        app_name: str,
        contact_display_name: str,
        timeout_seconds: float,
    ) -> WeChatContactSearchResult:
        if platform.system() != "Darwin":
            return WeChatContactSearchResult(
                status="not_available",
                summary="WeChat contact search is only available on macOS.",
            )
        normalized = contact_display_name.strip()
        if not normalized:
            return WeChatContactSearchResult(
                status="failed",
                summary="contact_display_name is required.",
            )

        readiness = self.window_readiness(
            app_name=app_name,
            timeout_seconds=min(timeout_seconds, 10.0),
        )
        if readiness.status != "ready":
            return WeChatContactSearchResult(
                status="needs_user",
                summary=readiness.summary,
                diagnostics=readiness.diagnostics,
            )

        prepare = _run_osascript(
            _contact_prepare_search_script(app_name, normalized), timeout_seconds
        )
        if prepare.returncode != 0:
            return WeChatContactSearchResult(
                status="needs_user",
                summary="WeChat main window/search readiness AppleScript failed.",
                diagnostics={"stderr": _bounded(prepare.stderr)},
            )
        prepare_fields = _parse_result_fields(prepare.stdout)
        if prepare_fields.get("status") != "ready":
            return WeChatContactSearchResult(
                status="needs_user",
                summary=(
                    prepare_fields.get("reason")
                    or "WeChat search input could not be prepared safely."
                ),
                diagnostics=_diagnostics(prepare_fields),
            )

        time.sleep(3.0)
        result = _run_osascript(
            _contact_select_result_script(app_name, normalized), timeout_seconds
        )
        if result.returncode != 0:
            return WeChatContactSearchResult(
                status="needs_user",
                summary="WeChat contact selection AppleScript failed.",
                diagnostics={"stderr": _bounded(result.stderr)},
            )
        fields = _parse_result_fields(result.stdout)
        status = fields.get("status", "failed")
        if status == "resolved":
            display_name = fields.get("display_name") or normalized
            return WeChatContactSearchResult(
                status="resolved",
                summary=f"WeChat contact selected: {display_name}.",
                display_name=display_name,
                stable_hint=fields.get("stable_hint") or f"wechat:contact:{display_name}",
                observation_ref=fields.get("observation_ref"),
                diagnostics=_diagnostics(fields),
            )
        if status == "not_found":
            return WeChatContactSearchResult(
                status="not_found",
                summary="WeChat search did not expose the requested contact.",
                observation_ref=fields.get("observation_ref"),
                diagnostics=_diagnostics(fields),
            )
        return WeChatContactSearchResult(
            status="needs_user",
            summary=fields.get("reason") or "WeChat search focus could not be verified.",
            observation_ref=fields.get("observation_ref"),
            diagnostics=_diagnostics(fields),
        )

    def focus_message_input(
        self,
        *,
        app_name: str,
        contact_display_name: str,
        timeout_seconds: float,
    ) -> WeChatInputFocusResult:
        if platform.system() != "Darwin":
            return WeChatInputFocusResult(
                status="not_available",
                summary="WeChat message input focus is only available on macOS.",
            )
        normalized = contact_display_name.strip()
        if not normalized:
            return WeChatInputFocusResult(
                status="failed",
                summary="contact_display_name is required.",
            )

        script = _focus_message_input_script(app_name, normalized)
        result = _run_osascript(script, timeout_seconds)
        if result.returncode != 0:
            return WeChatInputFocusResult(
                status="needs_user",
                summary="WeChat message input focus AppleScript failed.",
                diagnostics={"stderr": _bounded(result.stderr)},
            )
        fields = _parse_result_fields(result.stdout)
        if fields.get("status") == "focused":
            return WeChatInputFocusResult(
                status="focused",
                summary="WeChat message input focused for draft-only typing.",
                observation_ref=fields.get("observation_ref"),
                diagnostics=_diagnostics(fields),
            )
        return WeChatInputFocusResult(
            status="needs_user",
            summary=fields.get("reason") or "WeChat message input focus was not safe.",
            observation_ref=fields.get("observation_ref"),
            diagnostics=_diagnostics(fields),
        )

    def submit_message(
        self,
        *,
        app_name: str,
        contact_display_name: str,
        message_preview: str,
        timeout_seconds: float,
    ) -> WeChatMessageSubmitResult:
        if platform.system() != "Darwin":
            return WeChatMessageSubmitResult(
                status="not_available",
                summary="WeChat message submit is only available on macOS.",
                diagnostics={
                    "phase": "pre_submit",
                    "failure_kind": "not_available",
                    "send_attempted": "false",
                },
            )
        normalized_contact = contact_display_name.strip()
        normalized_preview = message_preview.strip()
        if not normalized_contact:
            return WeChatMessageSubmitResult(
                status="not_sent",
                summary="contact_display_name is required.",
                diagnostics={
                    "phase": "pre_submit",
                    "failure_kind": "missing_contact",
                    "send_attempted": "false",
                },
            )
        if not normalized_preview:
            return WeChatMessageSubmitResult(
                status="not_sent",
                summary="message_preview is required.",
                diagnostics={
                    "phase": "pre_submit",
                    "failure_kind": "missing_message_preview",
                    "send_attempted": "false",
                },
            )

        result = _run_osascript(
            _submit_message_script(app_name, normalized_contact, normalized_preview),
            timeout_seconds,
        )
        if result.returncode != 0:
            return WeChatMessageSubmitResult(
                status="unknown",
                summary="WeChat keyboard submit AppleScript failed.",
                diagnostics={
                    "phase": "keyboard_submit",
                    "failure_kind": "keyboard_submit_error",
                    "send_attempted": "unknown",
                    "stderr": _bounded(result.stderr),
                },
            )
        fields = _parse_result_fields(result.stdout)
        status = fields.get("status", "unknown")
        if status == "sent":
            return WeChatMessageSubmitResult(
                status="sent",
                summary="WeChat message submitted with keyboard Return.",
                observation_ref=fields.get("observation_ref"),
                diagnostics=_diagnostics(fields),
            )
        if status == "not_sent":
            return WeChatMessageSubmitResult(
                status="not_sent",
                summary=fields.get("reason") or "WeChat message was not submitted.",
                observation_ref=fields.get("observation_ref"),
                diagnostics=_diagnostics(fields),
            )
        return WeChatMessageSubmitResult(
            status="unknown",
            summary=fields.get("reason") or "WeChat message submit result is unknown.",
            observation_ref=fields.get("observation_ref"),
            diagnostics=_diagnostics(fields),
        )

    def window_readiness(
        self,
        *,
        app_name: str,
        timeout_seconds: float,
    ) -> WeChatWindowReadinessResult:
        if platform.system() != "Darwin":
            return WeChatWindowReadinessResult(
                status="not_available",
                summary="WeChat window readiness is only available on macOS.",
            )

        result = _run_osascript(_window_readiness_script(app_name), timeout_seconds)
        if result.returncode != 0:
            return WeChatWindowReadinessResult(
                status="needs_user",
                summary="WeChat main window readiness AppleScript failed.",
                diagnostics=_with_window_recovery_metadata(
                    {"stderr": _bounded(result.stderr)}
                ),
            )
        fields = _parse_result_fields(result.stdout)
        if fields.get("status") == "ready":
            return WeChatWindowReadinessResult(
                status="ready",
                summary="WeChat main window is available for search.",
                diagnostics=_diagnostics(fields),
            )
        return WeChatWindowReadinessResult(
            status="needs_user",
            summary=(
                fields.get("reason")
                or "WeChat main window is unavailable; open the main WeChat window before sending."
            ),
            diagnostics=_with_window_recovery_metadata(_diagnostics(fields) or {}),
        )


def _run_osascript(script: str, timeout_seconds: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr
        return subprocess.CompletedProcess(
            ["osascript", "-e", script],
            124,
            stdout="",
            stderr=stderr or f"osascript timed out after {timeout_seconds:.1f}s",
        )


def _window_readiness_script(app_name: str) -> str:
    return f"""
set appName to {_applescript_string(app_name)}
my activateTarget(appName)
delay 0.5
set windowSummary to my firstWindowSummary(appName)
if windowSummary starts with "status=ready" then return windowSummary
my activateTarget(appName)
delay 1.0
return my firstWindowSummary(appName)

on activateTarget(appName)
  try
    tell application appName to reopen
  end try
  try
    tell application appName to activate
  end try
  tell application "System Events"
    if exists process appName then
      tell process appName
        set frontmost to true
      end tell
    end if
  end tell
end activateTarget

on firstWindowSummary(appName)
tell application "System Events"
  if not (exists process appName) then
    return "status=needs_user" & linefeed & "reason=target app is not running"
  end if
  tell process appName
    try
      set windowPosition to position of window 1
      set windowSize to size of window 1
      return "status=ready" & linefeed & "window_position=" & (windowPosition as text) & linefeed & "window_size=" & (windowSize as text)
    on error errMsg
      return "status=needs_user" & linefeed & "reason=WeChat main window is unavailable; open the main WeChat window before sending." & linefeed & "error=" & errMsg
    end try
  end tell
end tell
end firstWindowSummary
"""


def _contact_prepare_search_script(app_name: str, contact_display_name: str) -> str:
    return f"""
set appName to {_applescript_string(app_name)}
set contactName to {_applescript_string(contact_display_name)}
tell application "System Events"
  if not (exists process appName) then error "target app is not running"
  tell process appName
    set frontmost to true
  end tell
  key code 53
  delay 0.3
  set focusText to my focusedElementSummary(appName)
  if my isSearchFocus(focusText) is false then
    keystroke "k" using command down
    delay 0.35
    set focusText to my focusedElementSummary(appName)
  end if
  if my isSearchFocus(focusText) is false then
    keystroke "f" using command down
    delay 0.35
    set focusText to my focusedElementSummary(appName)
  end if
  if my isSearchFocus(focusText) is false then
    return "status=needs_user" & linefeed & "reason=search focus not verified" & linefeed & "focus=" & focusText
  end if
  set focusTextAfterInput to focusText
  if focusTextAfterInput does not contain contactName then
    my replaceFocusedText(appName, contactName)
    set focusTextAfterInput to my focusedElementSummary(appName)
  end if
  if my isSearchFocus(focusTextAfterInput) is false then
    return "status=needs_user" & linefeed & "reason=search focus was lost after paste" & linefeed & "focus=" & focusTextAfterInput
  end if
  return "status=ready" & linefeed & "focus=" & focusTextAfterInput
end tell

on focusedElementSummary(appName)
  set parts to {{}}
  tell application "System Events"
    tell process appName
      try
        set focusedElement to value of attribute "AXFocusedUIElement"
        try
          set end of parts to role of focusedElement as text
        end try
        try
          set end of parts to name of focusedElement as text
        end try
        try
          set end of parts to description of focusedElement as text
        end try
        try
          set end of parts to value of focusedElement as text
        end try
      end try
    end tell
  end tell
  return my joinParts(parts, " ")
end focusedElementSummary

on replaceFocusedText(appName, newText)
  tell application "System Events"
    tell process appName
      set frontmost to true
    end tell
    set previousClipboard to the clipboard
    set the clipboard to newText
    keystroke "a" using command down
    delay 0.1
    keystroke "v" using command down
    delay 1.2
    set the clipboard to previousClipboard
  end tell
end replaceFocusedText

on isSearchFocus(focusText)
  set lowerText to my lowerASCII(focusText)
  if lowerText contains "search" then return true
  if focusText contains "搜索" then return true
  if focusText contains "查找" then return true
  return false
end isSearchFocus

on boundedWindowText(appName, maxItems)
  set texts to {{}}
  tell application "System Events"
    tell process appName
      try
        set allElements to entire contents of front window
        set itemCount to 0
        repeat with candidate in allElements
          if itemCount >= maxItems then exit repeat
          set candidateText to ""
          try
            set candidateText to name of candidate as text
          end try
          if candidateText is "" or candidateText is "missing value" then
            set candidateText to ""
            try
              set candidateText to description of candidate as text
            end try
          end if
          if candidateText is "" or candidateText is "missing value" then
            set candidateText to ""
            try
              set candidateText to value of candidate as text
            end try
          end if
          if candidateText is not "" and candidateText is not "missing value" then
            set end of texts to candidateText
            set itemCount to itemCount + 1
          end if
        end repeat
      end try
    end tell
  end tell
  return my joinParts(texts, " | ")
end boundedWindowText

on candidateText(candidate)
  set candidateText to ""
  try
    set candidateText to name of candidate as text
  end try
  if candidateText is missing value or candidateText is "" or candidateText is "missing value" then
    set candidateText to ""
    try
      set candidateText to description of candidate as text
    end try
  end if
  if candidateText is missing value or candidateText is "" or candidateText is "missing value" then
    set candidateText to ""
    try
      set candidateText to value of candidate as text
    end try
  end if
  if candidateText is missing value or candidateText is "missing value" then
    return ""
  end if
  return candidateText
end candidateText

on joinParts(parts, separator)
  set AppleScript's text item delimiters to separator
  set joined to parts as text
  set AppleScript's text item delimiters to ""
  return joined
end joinParts

on lowerASCII(inputText)
  set outputText to inputText
  set upperLetters to "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
  set lowerLetters to "abcdefghijklmnopqrstuvwxyz"
  repeat with i from 1 to length of upperLetters
    set outputText to my replaceText(character i of upperLetters, character i of lowerLetters, outputText)
  end repeat
  return outputText
end lowerASCII

on replaceText(searchText, replacementText, sourceText)
  set AppleScript's text item delimiters to searchText
  set textItems to text items of sourceText
  set AppleScript's text item delimiters to replacementText
  set replacedText to textItems as text
  set AppleScript's text item delimiters to ""
  return replacedText
end replaceText
"""


def _contact_select_result_script(app_name: str, contact_display_name: str) -> str:
    return f"""
set appName to {_applescript_string(app_name)}
set contactName to {_applescript_string(contact_display_name)}
tell application "System Events"
  if not (exists process appName) then error "target app is not running"
  tell process appName
    set frontmost to true
  end tell
  delay 0.2
  set focusBeforeSelection to my focusedElementSummary(appName)
  if my isSearchFocus(focusBeforeSelection) is false then
    return "status=needs_user" & linefeed & "reason=search focus was not active before selection" & linefeed & "focus=" & focusBeforeSelection
  end if
  key code 36
  delay 1.2
  set focusAfterSelection to my focusedElementSummary(appName)
  if my isSearchFocus(focusAfterSelection) is false then
    return "status=resolved" & linefeed & "display_name=" & contactName & linefeed & "stable_hint=wechat:search:" & contactName & linefeed & "observation_ref=wechat-search-selected" & linefeed & "focus=" & focusAfterSelection
  end if
  return "status=not_found" & linefeed & "reason=contact was not selected after return" & linefeed & "focus=" & focusAfterSelection
end tell

on focusedElementSummary(appName)
  set parts to {{}}
  tell application "System Events"
    tell process appName
      try
        set focusedElement to value of attribute "AXFocusedUIElement"
        try
          set end of parts to role of focusedElement as text
        end try
        try
          set end of parts to name of focusedElement as text
        end try
        try
          set end of parts to description of focusedElement as text
        end try
        try
          set end of parts to value of focusedElement as text
        end try
      end try
    end tell
  end tell
  return my joinParts(parts, " ")
end focusedElementSummary

on isSearchFocus(focusText)
  set lowerText to my lowerASCII(focusText)
  if lowerText contains "search" then return true
  if focusText contains "搜索" then return true
  if focusText contains "查找" then return true
  return false
end isSearchFocus

on boundedWindowText(appName, maxItems)
  set texts to {{}}
  tell application "System Events"
    tell process appName
      try
        set allElements to entire contents of front window
        set itemCount to 0
        repeat with candidate in allElements
          if itemCount >= maxItems then exit repeat
          set candidateText to ""
          try
            set candidateText to name of candidate as text
          end try
          if candidateText is "" or candidateText is "missing value" then
            set candidateText to ""
            try
              set candidateText to description of candidate as text
            end try
          end if
          if candidateText is "" or candidateText is "missing value" then
            set candidateText to ""
            try
              set candidateText to value of candidate as text
            end try
          end if
          if candidateText is not "" and candidateText is not "missing value" then
            set end of texts to candidateText
            set itemCount to itemCount + 1
          end if
        end repeat
      end try
    end tell
  end tell
  return my joinParts(texts, " | ")
end boundedWindowText

on candidateText(candidate)
  set candidateText to ""
  try
    set candidateText to name of candidate as text
  end try
  if candidateText is missing value or candidateText is "" or candidateText is "missing value" then
    set candidateText to ""
    try
      set candidateText to description of candidate as text
    end try
  end if
  if candidateText is missing value or candidateText is "" or candidateText is "missing value" then
    set candidateText to ""
    try
      set candidateText to value of candidate as text
    end try
  end if
  if candidateText is missing value or candidateText is "missing value" then
    return ""
  end if
  return candidateText
end candidateText

on joinParts(parts, separator)
  set AppleScript's text item delimiters to separator
  set joined to parts as text
  set AppleScript's text item delimiters to ""
  return joined
end joinParts

on lowerASCII(inputText)
  set outputText to inputText
  set upperLetters to "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
  set lowerLetters to "abcdefghijklmnopqrstuvwxyz"
  repeat with i from 1 to length of upperLetters
    set outputText to my replaceText(character i of upperLetters, character i of lowerLetters, outputText)
  end repeat
  return outputText
end lowerASCII

on replaceText(searchText, replacementText, sourceText)
  set AppleScript's text item delimiters to searchText
  set textItems to text items of sourceText
  set AppleScript's text item delimiters to replacementText
  set replacedText to textItems as text
  set AppleScript's text item delimiters to ""
  return replacedText
end replaceText
"""


def _focus_message_input_script(app_name: str, contact_display_name: str) -> str:
    return f"""
set appName to {_applescript_string(app_name)}
set contactName to {_applescript_string(contact_display_name)}
tell application "System Events"
  if not (exists application process appName) then error "target app is not running"
  tell application process appName
    set frontmost to true
    try
      set windowPosition to position of front window
      set windowSize to size of front window
      set clickX to (item 1 of windowPosition) + ((item 1 of windowSize) * 0.38)
      set clickY to (item 2 of windowPosition) + ((item 2 of windowSize) * 0.92)
      click at {{clickX, clickY}}
      delay 0.3
      set focusAfterClick to my focusedElementSummary(appName)
      if my isSearchFocus(focusAfterClick) then
        return "status=needs_user" & linefeed & "reason=message input click left focus in search" & linefeed & "focus=" & focusAfterClick
      end if
      keystroke "a" using command down
      delay 0.1
      key code 51
      delay 0.1
      return "status=focused" & linefeed & "observation_ref=wechat-message-input-focused" & linefeed & "focus=" & focusAfterClick & linefeed & "input_cleared=true"
    on error errMsg
      return "status=needs_user" & linefeed & "reason=" & errMsg
    end try
  end tell
end tell

on focusedElementSummary(appName)
  set parts to {{}}
  tell application "System Events"
    tell process appName
      try
        set focusedElement to value of attribute "AXFocusedUIElement"
        try
          set end of parts to role of focusedElement as text
        end try
        try
          set end of parts to name of focusedElement as text
        end try
        try
          set end of parts to description of focusedElement as text
        end try
        try
          set end of parts to value of focusedElement as text
        end try
      end try
    end tell
  end tell
  return my joinParts(parts, " ")
end focusedElementSummary

on isSearchFocus(focusText)
  set lowerText to my lowerASCII(focusText)
  if lowerText contains "search" then return true
  if focusText contains "搜索" then return true
  if focusText contains "查找" then return true
  return false
end isSearchFocus

on joinParts(parts, separator)
  set AppleScript's text item delimiters to separator
  set joined to parts as text
  set AppleScript's text item delimiters to ""
  return joined
end joinParts

on lowerASCII(inputText)
  set outputText to inputText
  set upperLetters to "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
  set lowerLetters to "abcdefghijklmnopqrstuvwxyz"
  repeat with i from 1 to length of upperLetters
    set outputText to my replaceText(character i of upperLetters, character i of lowerLetters, outputText)
  end repeat
  return outputText
end lowerASCII

on replaceText(searchText, replacementText, sourceText)
  set AppleScript's text item delimiters to searchText
  set textItems to text items of sourceText
  set AppleScript's text item delimiters to replacementText
  set replacedText to textItems as text
  set AppleScript's text item delimiters to ""
  return replacedText
end replaceText
"""


def _submit_message_script(
    app_name: str,
    contact_display_name: str,
    message_preview: str,
) -> str:
    del contact_display_name, message_preview
    return f"""
set appName to {_applescript_string(app_name)}
tell application "System Events"
  if not (exists application process appName) then
    return "status=not_sent" & linefeed & "reason=target app is not running" & linefeed & "phase=pre_submit" & linefeed & "failure_kind=app_not_running" & linefeed & "send_attempted=false"
  end if
  tell application process appName
    set frontmost to true
    try
      delay 0.15
      key code 36
      delay 0.2
      return "status=sent" & linefeed & "observation_ref=wechat-keyboard-submit" & linefeed & "phase=keyboard_submit" & linefeed & "send_method=keyboard_return" & linefeed & "send_attempted=true" & linefeed & "input_focus_verified=prior_draft_observation" & linefeed & "input_content_verified=prior_type_text_observation"
    on error errMsg
      return "status=unknown" & linefeed & "reason=" & errMsg & linefeed & "phase=keyboard_submit" & linefeed & "failure_kind=keyboard_submit_error" & linefeed & "send_attempted=unknown"
    end try
  end tell
end tell
"""


def _applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _parse_result_fields(raw: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key.strip()] = value.strip()
    return fields


def _diagnostics(fields: dict[str, str]) -> dict[str, str]:
    return {
        key: _bounded(value, 500)
        for key, value in fields.items()
        if key not in {"status", "display_name", "stable_hint", "observation_ref"}
    }


def _with_window_recovery_metadata(values: dict[str, str]) -> dict[str, str]:
    return {
        **values,
        "setupHint": WECHAT_MAIN_WINDOW_SETUP_HINT,
        "recoveryActions": ",".join(WECHAT_MAIN_WINDOW_RECOVERY_ACTIONS),
    }


def _bounded(value: str, limit: int = 1_000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "...[truncated]"


__all__ = [
    "MacOSWeChatSearchDriver",
    "WeChatContactSearchResult",
    "WeChatInputFocusResult",
    "WeChatMessageSubmitResult",
    "WeChatWindowReadinessResult",
]
