"""WeChat runtime adapter backed by Plato Computer Use Helper app APIs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from taskweavn.integrations.wechat_desktop.confirmation import (
    WeChatSendActionFingerprint,
)
from taskweavn.integrations.wechat_desktop.models import (
    WeChatContactCandidate,
    WeChatContactResolution,
    WeChatContactResolutionStatus,
    WeChatDraftState,
    WeChatOperationResult,
    WeChatReadiness,
    WeChatReadinessStatus,
    WeChatSendAttemptResult,
    WeChatSendAttemptStatus,
    WeChatSendTaskInput,
    wechat_message_hash,
    wechat_message_preview,
)


class WeChatHelperHttpClient(Protocol):
    """Subset of helper client APIs used by the WeChat runtime adapter."""

    def readiness(self) -> Mapping[str, Any]: ...

    def wechat_draft_message(
        self,
        *,
        request_id: str,
        idempotency_key: str,
        caller: Mapping[str, str],
        contact_display_name: str,
        message_text: str,
        contact_alias: str | None = None,
        operator_note: str | None = None,
        external_ref: Mapping[str, str] | None = None,
        app_identity: str | None = None,
    ) -> Mapping[str, Any]: ...

    def wechat_send_confirmed(
        self,
        *,
        request_id: str,
        idempotency_key: str,
        caller: Mapping[str, str],
        action_fingerprint_payload: Mapping[str, Any],
        action_fingerprint: str,
        contact_summary: str,
        message_preview: str,
        confirmation_id: str,
    ) -> Mapping[str, Any]: ...


@dataclass
class WeChatDesktopHelperAdapter:
    """Adapt helper-owned WeChat APIs to ``WeChatSendRuntimeHandler``."""

    client: WeChatHelperHttpClient
    app_name: str = "WeChat"
    app_identity: str = "com.tencent.xinWeChat"
    _drafts: dict[tuple[str, str], Mapping[str, Any]] = field(
        default_factory=dict,
        init=False,
    )

    def readiness(self) -> WeChatReadiness:
        try:
            response = self.client.readiness()
        except Exception as exc:  # noqa: BLE001 - helper boundary is sanitized.
            return WeChatReadiness(
                status="failed",
                summary=f"WeChat helper readiness failed: {type(exc).__name__}",
                app_name=self.app_name,
                setup_hint=str(exc),
            )
        status = _string(response.get("status")) or "failed"
        if status in {"ready", "ok"}:
            return WeChatReadiness(
                status="ready",
                summary=_summary(response, "Plato Computer Use Helper is ready."),
                app_name=self.app_name,
                bundle_id=self.app_identity,
                setup_hint=_setup_hint(response),
            )
        return WeChatReadiness(
            status=_readiness_status(status),
            summary=_summary(response, "Plato Computer Use Helper is not ready."),
            app_name=self.app_name,
            bundle_id=self.app_identity,
            setup_hint=_setup_hint(response),
        )

    def open_or_focus(self) -> WeChatOperationResult:
        return WeChatOperationResult(
            status="ok",
            summary="WeChat open/focus is delegated to helper draft-message.",
            metadata={"delegated_to_helper": "true"},
        )

    def resolve_contact(
        self,
        task_input: WeChatSendTaskInput,
        *,
        execution_id: str | None = None,
        idempotency_key: str | None = None,
        session_id: str | None = None,
    ) -> WeChatContactResolution:
        if execution_id is None or idempotency_key is None:
            return WeChatContactResolution(
                status="failed",
                reason="helper WeChat draft requires execution_id and idempotency_key",
            )
        try:
            response = self.client.wechat_draft_message(
                request_id=f"{execution_id}:wechat-draft",
                idempotency_key=idempotency_key,
                caller={
                    "sessionId": session_id or "",
                    "taskExecutionId": execution_id,
                },
                contact_display_name=task_input.contact_display_name,
                contact_alias=task_input.contact_alias,
                message_text=task_input.message_text,
                operator_note=task_input.operator_note,
                external_ref=task_input.external_ref,
                app_identity=self.app_identity,
            )
        except Exception as exc:  # noqa: BLE001 - helper boundary is sanitized.
            return WeChatContactResolution(
                status="failed",
                reason=f"WeChat helper draft request failed: {type(exc).__name__}",
                diagnostics={"error": str(exc)},
            )

        draft_key = _draft_key_from_response(response, task_input.message_text)
        self._drafts[draft_key] = response
        if _success(response):
            return _resolution_from_response(response, task_input)

        phase = _string(response.get("phase"))
        if phase == "draft":
            return _resolution_from_draft_failure(response, task_input)
        return WeChatContactResolution(
            status=_contact_failure_status(response),
            reason=_summary(response, "WeChat helper could not resolve contact."),
            observation_ref=_evidence_observation_ref(response),
            diagnostics=_diagnostics(response),
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
        key = (resolution.selected.summary(), wechat_message_hash(message_text))
        response = self._drafts.get(key)
        if response is None:
            return _failed_draft(
                message_text,
                contact_summary=resolution.selected.summary(),
                reason="WeChat helper draft response was not found.",
            )
        draft = _mapping(response.get("draftState"))
        if _success(response) and _string(draft.get("status")) == "drafted":
            return WeChatDraftState(
                status="drafted",
                contact_summary=_string(draft.get("contactSummary"))
                or resolution.selected.summary(),
                message_hash=_string(draft.get("messageHash"))
                or wechat_message_hash(message_text),
                message_preview=_string(draft.get("messagePreview"))
                or wechat_message_preview(message_text),
                draft_observation_ref=_string(draft.get("draftObservationRef")),
            )
        return _failed_draft(
            message_text,
            contact_summary=_string(draft.get("contactSummary"))
            or resolution.selected.summary(),
            reason=_summary(response, "WeChat helper draft failed."),
            draft_observation_ref=_string(draft.get("draftObservationRef")),
        )

    def send_after_confirmation(
        self,
        fingerprint: WeChatSendActionFingerprint,
        *,
        contact_summary: str,
        message_preview: str,
        confirmation_id: str | None = None,
    ) -> WeChatSendAttemptResult:
        try:
            response = self.client.wechat_send_confirmed(
                request_id=f"{fingerprint.execution_id}:wechat-send",
                idempotency_key=fingerprint.idempotency_key,
                caller={"taskExecutionId": fingerprint.execution_id},
                action_fingerprint_payload=fingerprint.to_safe_context(),
                action_fingerprint=fingerprint.digest(),
                contact_summary=contact_summary,
                message_preview=message_preview,
                confirmation_id=confirmation_id or "unknown-confirmation",
            )
        except Exception as exc:  # noqa: BLE001 - helper boundary is sanitized.
            return WeChatSendAttemptResult(
                status="not_sent",
                summary=f"WeChat helper send request failed: {type(exc).__name__}",
                reason=str(exc),
                metadata={
                    "failure_kind": "helper_request_failed",
                    "phase": "helper_send_confirmed",
                    "send_attempted": "false",
                },
            )
        status = _string(response.get("status")) or "failed"
        metadata = _string_metadata(response)
        metadata.setdefault("phase", _string(response.get("phase")) or "keyboard_submit")
        return WeChatSendAttemptResult(
            status=_send_status(status, response),
            summary=_summary(response, "WeChat helper send completed."),
            send_observation_ref=_evidence_observation_ref(response),
            reason=None if _success(response) else _summary(response, "WeChat send failed."),
            metadata=metadata,
        )


def _success(response: Mapping[str, Any]) -> bool:
    return response.get("success") is True or _string(response.get("status")) in {
        "ok",
        "sent",
    }


def _resolution_from_response(
    response: Mapping[str, Any],
    task_input: WeChatSendTaskInput,
) -> WeChatContactResolution:
    raw_resolution = _mapping(response.get("contactResolution"))
    raw_draft = _mapping(response.get("draftState"))
    selected = _string(raw_resolution.get("selected")) or _string(
        raw_draft.get("contactSummary")
    )
    candidate = WeChatContactCandidate(
        display_name=selected or task_input.contact_display_name,
        confidence=1.0,
    )
    return WeChatContactResolution(
        status="resolved",
        selected=candidate,
        candidates=(candidate,),
        observation_ref=_string(raw_resolution.get("observationRef"))
        or _evidence_observation_ref(response),
        diagnostics=_diagnostics(response),
    )


def _resolution_from_draft_failure(
    response: Mapping[str, Any],
    task_input: WeChatSendTaskInput,
) -> WeChatContactResolution:
    raw_draft = _mapping(response.get("draftState"))
    contact_summary = _string(raw_draft.get("contactSummary"))
    candidate = WeChatContactCandidate(
        display_name=contact_summary or task_input.contact_display_name,
        confidence=1.0,
    )
    return WeChatContactResolution(
        status="resolved",
        selected=candidate,
        candidates=(candidate,),
        observation_ref=_evidence_observation_ref(response),
        diagnostics=_diagnostics(response),
    )


def _failed_draft(
    message_text: str,
    *,
    reason: str,
    contact_summary: str = "",
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


def _draft_key_from_response(
    response: Mapping[str, Any],
    message_text: str,
) -> tuple[str, str]:
    draft = _mapping(response.get("draftState"))
    contact = _string(draft.get("contactSummary"))
    if contact is None:
        resolution = _mapping(response.get("contactResolution"))
        contact = _string(resolution.get("selected"))
    message_hash = _string(draft.get("messageHash")) or wechat_message_hash(message_text)
    return (contact or "", message_hash)


def _contact_failure_status(response: Mapping[str, Any]) -> WeChatContactResolutionStatus:
    status = _string(response.get("status"))
    if status == "needs_user":
        return "needs_user"
    failure_kind = _string(response.get("failureKind"))
    if failure_kind and "not_found" in failure_kind:
        return "not_found"
    if failure_kind and "ambiguous" in failure_kind:
        return "ambiguous"
    return "failed"


def _readiness_status(status: str) -> WeChatReadinessStatus:
    if status in {"needs_user", "app_needs_user"}:
        return "needs_user"
    if status in {"not_available", "missing_accessibility", "helper_untrusted"}:
        return "not_observable"
    return "failed"


def _send_status(
    status: str,
    response: Mapping[str, Any],
) -> WeChatSendAttemptStatus:
    if status == "sent":
        return "sent"
    if status == "unknown":
        return "unknown"
    failure_kind = _string(response.get("failureKind"))
    if failure_kind == "send_unknown":
        return "unknown"
    if status in {"not_sent", "failed", "not_available", "needs_user", "blocked"}:
        return "not_sent"
    return "failed"


def _evidence_observation_ref(response: Mapping[str, Any]) -> str | None:
    evidence = _mapping(response.get("evidence"))
    return _string(evidence.get("observationRef"))


def _diagnostics(response: Mapping[str, Any]) -> dict[str, str] | None:
    diagnostics = response.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        return None
    values = {
        key: value
        for key, value in diagnostics.items()
        if isinstance(key, str) and isinstance(value, str)
    }
    return values or None


def _string_metadata(response: Mapping[str, Any]) -> dict[str, str]:
    metadata = dict(_diagnostics(response) or {})
    failure_kind = _string(response.get("failureKind"))
    if failure_kind:
        metadata["failure_kind"] = failure_kind
    evidence = _mapping(response.get("evidence"))
    for source_key, target_key in (
        ("observationRef", "observation_ref"),
        ("targetApp", "target_app"),
        ("targetContact", "target_contact"),
        ("redaction", "redaction"),
    ):
        value = _string(evidence.get(source_key))
        if value is not None:
            metadata[target_key] = value
    metadata["send_attempted"] = "true" if _success(response) else "false"
    return metadata


def _setup_hint(response: Mapping[str, Any]) -> str | None:
    diagnostics = _mapping(response.get("diagnostics"))
    return _string(diagnostics.get("setupHint")) or _string(response.get("setupHint"))


def _summary(response: Mapping[str, Any], fallback: str) -> str:
    return _string(response.get("summary")) or fallback


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


__all__ = ["WeChatDesktopHelperAdapter", "WeChatHelperHttpClient"]
