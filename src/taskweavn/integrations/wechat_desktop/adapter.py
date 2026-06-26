"""WeChat Desktop adapter over Plato's computer-use backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from taskweavn.integrations.wechat_desktop.confirmation import (
    WeChatSendActionFingerprint,
)
from taskweavn.integrations.wechat_desktop.macos_driver import (
    WeChatContactSearchResult,
    WeChatInputFocusResult,
    WeChatMessageSubmitResult,
    WeChatWindowReadinessResult,
)
from taskweavn.integrations.wechat_desktop.models import (
    WeChatContactCandidate,
    WeChatContactResolution,
    WeChatContactResolutionStatus,
    WeChatDraftState,
    WeChatOperationResult,
    WeChatOperationStatus,
    WeChatReadiness,
    WeChatReadinessStatus,
    WeChatSendAttemptResult,
    WeChatSendTaskInput,
    wechat_message_hash,
    wechat_message_preview,
)
from taskweavn.tools.computer_use import ComputerUseBackend
from taskweavn.types.computer_use import ComputerUseAction, ComputerUseObservation


@dataclass(frozen=True)
class WeChatDesktopAdapterConfig:
    """Configuration for the local macOS WeChat Desktop adapter."""

    app_name: str = "WeChat"
    bundle_id: str | None = "com.tencent.xinWeChat"
    min_resolve_confidence: float = 0.8
    max_message_chars: int = 2_000
    default_timeout_seconds: float = 5.0


class WeChatContactSearchDriver(Protocol):
    """Optional deterministic contact-search driver for real WeChat Desktop."""

    def resolve_contact(
        self,
        *,
        app_name: str,
        contact_display_name: str,
        timeout_seconds: float,
    ) -> WeChatContactSearchResult: ...

    def focus_message_input(
        self,
        *,
        app_name: str,
        contact_display_name: str,
        timeout_seconds: float,
    ) -> WeChatInputFocusResult: ...

    def submit_message(
        self,
        *,
        app_name: str,
        contact_display_name: str,
        message_preview: str,
        timeout_seconds: float,
    ) -> WeChatMessageSubmitResult: ...

    def window_readiness(
        self,
        *,
        app_name: str,
        timeout_seconds: float,
    ) -> WeChatWindowReadinessResult: ...


@dataclass(frozen=True)
class WeChatDesktopAdapter:
    """Business adapter for draft-only local WeChat message preparation.

    This adapter prepares safe pre-confirmation phases: readiness, open/focus,
    contact resolution, and message drafting. It exposes one confirmation-gated
    submit operation that verifies the message input path and uses keyboard
    Return instead of clicking a send button.
    """

    computer_use_backend: ComputerUseBackend
    config: WeChatDesktopAdapterConfig = WeChatDesktopAdapterConfig()
    contact_search_driver: WeChatContactSearchDriver | None = None

    def readiness(self) -> WeChatReadiness:
        observation = self._execute(
            ComputerUseAction(
                operation="readiness",
                instruction="Check local macOS computer-use readiness for WeChat.",
                metadata={"target_app": self.config.app_name},
            )
        )
        if observation.status != "ok":
            return WeChatReadiness(
                status=_readiness_status_from_computer_use(observation),
                summary=observation.summary,
                app_name=self.config.app_name,
                bundle_id=self.config.bundle_id,
                observation_ref=observation.event_id,
                setup_hint=_string_metadata(observation, "setup_hint"),
            )
        app_status = _string_metadata(observation, "wechat_status") or "ready"
        status = _readiness_status_from_wechat_metadata(app_status)
        return WeChatReadiness(
            status=status,
            summary=_readiness_summary(status, observation.summary),
            app_name=self.config.app_name,
            bundle_id=self.config.bundle_id,
            observation_ref=observation.event_id,
            setup_hint=_string_metadata(observation, "setup_hint"),
        )

    def open_or_focus(self) -> WeChatOperationResult:
        observation = self._execute(
            ComputerUseAction(
                operation="open_app",
                instruction="Open or focus WeChat Desktop.",
                target=self.config.app_name,
                timeout_seconds=10.0,
            )
        )
        return _operation_result_from_observation(observation)

    def window_readiness(self) -> WeChatOperationResult:
        if self.contact_search_driver is None:
            return WeChatOperationResult(
                status="not_available",
                summary="WeChat window readiness requires the macOS search driver.",
            )
        result = self.contact_search_driver.window_readiness(
            app_name=self.config.app_name,
            timeout_seconds=max(self.config.default_timeout_seconds, 10.0),
        )
        return WeChatOperationResult(
            status=_operation_status_from_driver_status(result.status),
            summary=result.summary,
            metadata=result.diagnostics,
        )

    def resolve_contact(
        self,
        task_input: WeChatSendTaskInput,
        *,
        execution_id: str | None = None,
        idempotency_key: str | None = None,
        session_id: str | None = None,
    ) -> WeChatContactResolution:
        observation = self._execute(
            ComputerUseAction(
                operation="observe",
                instruction=(
                    "Observe safe WeChat contact candidates for "
                    f"{task_input.contact_display_name}."
                ),
                target=self.config.app_name,
                timeout_seconds=self.config.default_timeout_seconds,
                metadata={
                    "target_app": self.config.app_name,
                    "contact_display_name": task_input.contact_display_name,
                    **(
                        {"contact_alias": task_input.contact_alias}
                        if task_input.contact_alias
                        else {}
                    ),
                },
            )
        )
        if observation.status != "ok":
            if _should_try_driver_after_observe_failure(observation):
                driver_resolution = self._resolve_contact_with_driver(task_input)
                if driver_resolution is not None:
                    return driver_resolution
            return WeChatContactResolution(
                status=_contact_status_from_observation(observation),
                candidates=(),
                observation_ref=observation.event_id,
                reason=observation.summary,
        )
        forced_status = _string_metadata(observation, "contact_resolution_status")
        if forced_status == "needs_user":
            return WeChatContactResolution(
                status="needs_user",
                candidates=(),
                observation_ref=observation.event_id,
                reason=observation.summary,
            )
        if forced_status == "failed":
            return WeChatContactResolution(
                status="failed",
                candidates=(),
                observation_ref=observation.event_id,
                reason=observation.summary,
            )

        candidates = _candidate_tuple(observation.metadata.get("contact_candidates"))
        if not candidates:
            driver_resolution = self._resolve_contact_with_driver(task_input)
            if driver_resolution is not None:
                return driver_resolution
            return WeChatContactResolution(
                status="not_found",
                candidates=(),
                observation_ref=observation.event_id,
                reason="No matching WeChat contact candidate was observed.",
            )
        if len(candidates) == 1:
            candidate = candidates[0]
            if candidate.confidence >= self.config.min_resolve_confidence:
                return WeChatContactResolution(
                    status="resolved",
                    selected=candidate,
                    candidates=candidates,
                    observation_ref=observation.event_id,
                )
            return WeChatContactResolution(
                status="needs_user",
                candidates=candidates,
                observation_ref=observation.event_id,
                reason="Observed contact confidence is below the safe threshold.",
            )
        return WeChatContactResolution(
            status="ambiguous",
            candidates=candidates,
            observation_ref=observation.event_id,
            reason="Multiple WeChat contact candidates were observed.",
        )

    def draft_message(
        self,
        resolution: WeChatContactResolution,
        message_text: str,
    ) -> WeChatDraftState:
        if resolution.status != "resolved" or resolution.selected is None:
            return _failed_draft(
                message_text,
                reason="Cannot draft before exactly one contact is resolved.",
            )
        normalized = message_text.strip()
        if not normalized:
            return _failed_draft(message_text, reason="message_text is required")
        if len(normalized) > self.config.max_message_chars:
            return _failed_draft(
                message_text,
                contact_summary=resolution.selected.summary(),
                reason=(
                    "message_text exceeds WeChat draft limit "
                    f"({self.config.max_message_chars} characters)"
                ),
            )

        if self.contact_search_driver is not None:
            focus = self.contact_search_driver.focus_message_input(
                app_name=self.config.app_name,
                contact_display_name=resolution.selected.display_name,
                timeout_seconds=max(self.config.default_timeout_seconds, 40.0),
            )
            if focus.status != "focused":
                return _failed_draft(
                    normalized,
                    contact_summary=resolution.selected.summary(),
                    reason=focus.summary,
                    draft_observation_ref=focus.observation_ref,
                )

        observation = self._execute(
            ComputerUseAction(
                operation="type_text",
                instruction="Type the exact WeChat draft message without sending.",
                text=normalized,
                timeout_seconds=self.config.default_timeout_seconds,
                metadata={
                    "target_app": self.config.app_name,
                    "contact_summary": resolution.selected.summary(),
                    "draft_only": True,
                },
            )
        )
        if observation.status != "ok":
            return _failed_draft(
                normalized,
                contact_summary=resolution.selected.summary(),
                reason=observation.summary,
                draft_observation_ref=observation.event_id,
            )
        return WeChatDraftState(
            status="drafted",
            contact_summary=resolution.selected.summary(),
            message_hash=wechat_message_hash(normalized),
            message_preview=wechat_message_preview(normalized),
            draft_observation_ref=observation.event_id,
        )

    def _resolve_contact_with_driver(
        self,
        task_input: WeChatSendTaskInput,
    ) -> WeChatContactResolution | None:
        if self.contact_search_driver is None:
            return None
        result = self.contact_search_driver.resolve_contact(
            app_name=self.config.app_name,
            contact_display_name=task_input.contact_display_name,
            timeout_seconds=max(self.config.default_timeout_seconds, 40.0),
        )
        if result.status == "resolved" and result.display_name:
            candidate = WeChatContactCandidate(
                display_name=result.display_name,
                stable_hint=result.stable_hint,
                confidence=1.0,
            )
            return WeChatContactResolution(
                status="resolved",
                selected=candidate,
                candidates=(candidate,),
                observation_ref=result.observation_ref,
                diagnostics=result.diagnostics,
            )
        if result.status == "not_found":
            return WeChatContactResolution(
                status="not_found",
                candidates=(),
                observation_ref=result.observation_ref,
                reason=result.summary,
                diagnostics=result.diagnostics,
            )
        if result.status == "failed":
            return WeChatContactResolution(
                status="failed",
                candidates=(),
                observation_ref=result.observation_ref,
                reason=result.summary,
                diagnostics=result.diagnostics,
            )
        return WeChatContactResolution(
            status="needs_user",
            candidates=(),
            observation_ref=result.observation_ref,
            reason=result.summary,
            diagnostics=result.diagnostics,
        )

    def send_after_confirmation(
        self,
        fingerprint: WeChatSendActionFingerprint,
        *,
        contact_summary: str,
        message_preview: str,
        confirmation_id: str | None = None,
    ) -> WeChatSendAttemptResult:
        if self.contact_search_driver is not None:
            submit = self.contact_search_driver.submit_message(
                app_name=self.config.app_name,
                contact_display_name=contact_summary,
                message_preview=message_preview,
                timeout_seconds=max(self.config.default_timeout_seconds, 10.0),
            )
            metadata = {
                **(submit.diagnostics or {}),
                "action_fingerprint": fingerprint.digest(),
                "message_hash": fingerprint.message_hash,
                "draft_observation_ref": fingerprint.draft_observation_ref or "",
                "confirmation_required": "true",
                "confirmed_by_user": "true",
            }
            if submit.status == "sent":
                return WeChatSendAttemptResult(
                    status="sent",
                    summary=submit.summary,
                    send_observation_ref=submit.observation_ref,
                    metadata=metadata,
                )
            if submit.status == "not_sent":
                return WeChatSendAttemptResult(
                    status="not_sent",
                    summary=submit.summary,
                    send_observation_ref=submit.observation_ref,
                    reason=submit.summary,
                    metadata=metadata,
                )
            return WeChatSendAttemptResult(
                status="unknown",
                summary=(
                    "WeChat keyboard submit did not return a confirmed success; "
                    "manual review is required before retrying."
                ),
                send_observation_ref=submit.observation_ref,
                reason=submit.summary,
                metadata=metadata,
            )

        observation = self._execute(
            ComputerUseAction(
                operation="press_key",
                instruction=(
                    "Submit the already drafted WeChat message with keyboard "
                    "Return after explicit Plato confirmation."
                ),
                keys=("return",),
                timeout_seconds=self.config.default_timeout_seconds,
                metadata={
                    "target_app": self.config.app_name,
                    "action_fingerprint": fingerprint.digest(),
                    "message_hash": fingerprint.message_hash,
                    "draft_observation_ref": fingerprint.draft_observation_ref,
                    "confirmation_required": True,
                    "confirmed_by_user": True,
                    "send_method": "keyboard_return",
                    "send_attempted": True,
                    "phase": "keyboard_submit",
                },
            )
        )
        if observation.status == "ok":
            metadata = {
                **_string_map(observation.metadata),
                "send_method": "keyboard_return",
                "send_attempted": "true",
                "phase": "keyboard_submit",
            }
            return WeChatSendAttemptResult(
                status="sent",
                summary="WeChat message submitted with keyboard Return.",
                send_observation_ref=observation.event_id,
                metadata=metadata,
            )
        metadata = {
            **_string_map(observation.metadata),
            "send_method": "keyboard_return",
            "send_attempted": "unknown",
            "phase": "keyboard_submit",
        }
        return WeChatSendAttemptResult(
            status="unknown",
            summary=(
                "WeChat keyboard submit did not return a confirmed success; "
                "manual review is required before retrying."
            ),
            send_observation_ref=observation.event_id,
            reason=observation.summary,
            metadata=metadata,
        )

    def _execute(self, action: ComputerUseAction) -> ComputerUseObservation:
        return self.computer_use_backend.execute(action)


def _operation_result_from_observation(
    observation: ComputerUseObservation,
) -> WeChatOperationResult:
    status: WeChatOperationStatus
    if observation.status == "ok":
        status = "ok"
    elif observation.status == "needs_user" or observation.status == "blocked":
        status = "needs_user"
    elif observation.status == "not_available":
        status = "not_available"
    else:
        status = "failed"
    return WeChatOperationResult(
        status=status,
        summary=observation.summary,
        observation_ref=observation.event_id,
        text_extract=observation.text_extract,
        metadata=_string_map(observation.metadata),
    )


def _operation_status_from_driver_status(status: str) -> WeChatOperationStatus:
    if status == "ready":
        return "ok"
    if status in {"needs_user", "blocked"}:
        return "needs_user"
    if status == "not_available":
        return "not_available"
    return "failed"


def _readiness_status_from_computer_use(
    observation: ComputerUseObservation,
) -> WeChatReadinessStatus:
    if observation.status == "needs_user" or observation.status == "blocked":
        return "needs_user"
    if observation.status == "not_available":
        return "not_observable"
    return "failed"


def _readiness_status_from_wechat_metadata(app_status: str) -> WeChatReadinessStatus:
    if app_status in {"ready", "ok"}:
        return "ready"
    if app_status in {"missing", "not_installed", "wechat_missing"}:
        return "wechat_missing"
    if app_status in {"not_logged_in", "login_required"}:
        return "not_logged_in"
    if app_status in {"not_observable", "missing_accessibility"}:
        return "not_observable"
    if app_status in {"locked", "needs_user"}:
        return "needs_user"
    return "failed"


def _readiness_summary(status: WeChatReadinessStatus, fallback: str) -> str:
    if status == "ready":
        return "WeChat Desktop is ready for draft-only automation."
    if status == "wechat_missing":
        return "WeChat Desktop is not installed or not allowlisted."
    if status == "not_logged_in":
        return "WeChat Desktop requires the user to log in."
    if status == "not_observable":
        return "WeChat Desktop is not observable through Accessibility."
    if status == "needs_user":
        return "WeChat Desktop needs user intervention before automation."
    return fallback


def _contact_status_from_observation(
    observation: ComputerUseObservation,
) -> WeChatContactResolutionStatus:
    if (
        observation.status == "needs_user"
        or observation.status == "blocked"
        or observation.status == "not_available"
    ):
        return "needs_user"
    return "failed"


def _should_try_driver_after_observe_failure(
    observation: ComputerUseObservation,
) -> bool:
    """Let the app-specific driver recover from focus races.

    Generic observe can fail when the helper process or Codex remains frontmost
    immediately after open_app. The macOS WeChat driver owns the deterministic
    app focus/search sequence, so it should get one bounded chance before the
    adapter reports the contact as blocked.
    """

    signals = (
        observation.summary,
        _string_metadata(observation, "failure_kind") or "",
        _string_metadata(observation, "phase") or "",
    )
    return any("frontmost" in signal.lower() for signal in signals)


def _candidate_tuple(raw: Any) -> tuple[WeChatContactCandidate, ...]:
    if not isinstance(raw, list | tuple):
        return ()
    candidates: list[WeChatContactCandidate] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        display_name = item.get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            continue
        subtitle = item.get("subtitle")
        stable_hint = item.get("stable_hint")
        confidence = item.get("confidence", 0.0)
        candidates.append(
            WeChatContactCandidate(
                display_name=display_name.strip(),
                subtitle=subtitle.strip() if isinstance(subtitle, str) else None,
                stable_hint=(
                    stable_hint.strip() if isinstance(stable_hint, str) else None
                ),
                confidence=(
                    float(confidence) if isinstance(confidence, int | float) else 0.0
                ),
            )
        )
    return tuple(candidates)


def _failed_draft(
    message_text: str,
    *,
    contact_summary: str = "",
    reason: str,
    draft_observation_ref: str | None = None,
) -> WeChatDraftState:
    return WeChatDraftState(
        status="failed",
        contact_summary=contact_summary,
        message_hash=wechat_message_hash(message_text),
        message_preview=wechat_message_preview(message_text),
        draft_observation_ref=draft_observation_ref,
        reason=reason,
    )


def _string_metadata(observation: ComputerUseObservation, key: str) -> str | None:
    value = observation.metadata.get(key)
    return value if isinstance(value, str) and value else None


def _string_map(metadata: dict[str, Any]) -> dict[str, str]:
    return {
        key: value
        for key, value in metadata.items()
        if isinstance(key, str) and isinstance(value, str)
    }


__all__ = [
    "WeChatDesktopAdapter",
    "WeChatDesktopAdapterConfig",
]
