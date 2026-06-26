"""Send-after-confirmation orchestration for local WeChat sends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from taskweavn.execution_plane.models import (
    EvidenceRef,
    TaskError,
    TaskResult,
)
from taskweavn.execution_plane.store import ExecutionPlaneStore
from taskweavn.execution_plane.wechat_send_boundary import (
    WeChatSendBoundary,
    WeChatSendBoundaryStore,
    WeChatSendBoundaryStoreError,
)
from taskweavn.integrations.wechat_desktop.confirmation import (
    WeChatSendActionFingerprint,
    WeChatSendConfirmationAuthorizer,
)
from taskweavn.integrations.wechat_desktop.models import WeChatSendAttemptResult

WeChatSendExecutionStatus = Literal[
    "sent",
    "not_sent",
    "unknown",
    "waiting_for_user",
    "blocked",
]


class WeChatSendAdapter(Protocol):
    def send_after_confirmation(
        self,
        fingerprint: WeChatSendActionFingerprint,
        *,
        contact_summary: str,
        message_preview: str,
        confirmation_id: str | None = None,
    ) -> WeChatSendAttemptResult: ...


@dataclass(frozen=True)
class WeChatSendExecutionRequest:
    """Inputs the execution layer needs after drafting and confirmation."""

    execution_id: str
    action_fingerprint: WeChatSendActionFingerprint
    contact_summary: str
    message_preview: str


@dataclass(frozen=True)
class WeChatSendExecutionOutcome:
    """Result of attempting to advance one WeChat send boundary."""

    status: WeChatSendExecutionStatus
    summary: str
    boundary: WeChatSendBoundary
    result_ref: str | None = None
    error_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class WeChatSendExecutionService:
    """Advance a WeChat send boundary only after matching user confirmation."""

    boundary_store: WeChatSendBoundaryStore
    execution_store: ExecutionPlaneStore
    confirmation_authorizer: WeChatSendConfirmationAuthorizer
    adapter: WeChatSendAdapter

    def execute(
        self,
        request: WeChatSendExecutionRequest,
    ) -> WeChatSendExecutionOutcome:
        boundary = self.boundary_store.get(request.execution_id)
        if boundary is None:
            raise WeChatSendBoundaryStoreError(
                f"WeChat send boundary {request.execution_id!r} not found"
            )
        if boundary.action_fingerprint != request.action_fingerprint.digest():
            return self._mark_not_sent(
                boundary,
                request,
                code="wechat_send_boundary_mismatch",
                message="WeChat send boundary does not match the requested action.",
                retryable=False,
            )
        if boundary.status == "sent":
            return self._existing_sent(boundary)
        if boundary.status in {"send_attempted", "unknown"}:
            return self._manual_review_required(boundary)
        if boundary.status == "not_sent":
            return self._existing_not_sent(boundary)
        if boundary.confirmation_id is None:
            return WeChatSendExecutionOutcome(
                status="waiting_for_user",
                summary="WeChat send is waiting for a confirmation request.",
                boundary=boundary,
            )

        authorization = self.confirmation_authorizer.authorize(
            confirmation_id=boundary.confirmation_id,
            action_fingerprint=request.action_fingerprint,
        )
        if authorization.status == "pending":
            return WeChatSendExecutionOutcome(
                status="waiting_for_user",
                summary="WeChat send is waiting for user confirmation.",
                boundary=boundary,
            )
        if authorization.status == "rejected":
            return self._mark_not_sent(
                boundary,
                request,
                code="wechat_send_rejected",
                message="User rejected the WeChat send confirmation.",
                retryable=False,
            )
        if authorization.status != "authorized":
            return self._mark_not_sent(
                boundary,
                request,
                code=f"wechat_send_confirmation_{authorization.status}",
                message=authorization.reason
                or "WeChat send confirmation did not authorize this action.",
                retryable=False,
            )

        confirmed = self.boundary_store.transition(boundary.execution_id, "confirmed")
        attempt = self.adapter.send_after_confirmation(
            request.action_fingerprint,
            contact_summary=request.contact_summary,
            message_preview=request.message_preview,
            confirmation_id=boundary.confirmation_id,
        )
        if attempt.status == "sent":
            attempted = self.boundary_store.transition(
                confirmed.execution_id,
                "send_attempted",
            )
            return self._mark_sent(attempted, request, attempt)
        if attempt.status == "not_sent":
            send_evidence = self._put_send_evidence(confirmed, attempt)
            return self._mark_not_sent(
                confirmed,
                request,
                code=_attempt_error_code(attempt, "wechat_send_not_attempted"),
                message=attempt.reason or attempt.summary,
                retryable=True,
                evidence_refs=(send_evidence.evidence_id,),
            )
        attempted_or_confirmed = confirmed
        if _attempt_metadata_bool(attempt, "send_attempted"):
            attempted_or_confirmed = self.boundary_store.transition(
                confirmed.execution_id,
                "send_attempted",
            )
        return self._mark_unknown(attempted_or_confirmed, request, attempt)

    def _existing_sent(
        self,
        boundary: WeChatSendBoundary,
    ) -> WeChatSendExecutionOutcome:
        summary = "WeChat send was already completed for this idempotency key."
        if boundary.result_ref is not None:
            result = self.execution_store.get_result(boundary.result_ref)
            if result is not None:
                summary = result.summary
        return WeChatSendExecutionOutcome(
            status="sent",
            summary=summary,
            boundary=boundary,
            result_ref=boundary.result_ref,
            evidence_refs=(),
        )

    def _existing_not_sent(
        self,
        boundary: WeChatSendBoundary,
    ) -> WeChatSendExecutionOutcome:
        summary = "WeChat send is already terminal and was not sent."
        if boundary.error_ref is not None:
            error = self.execution_store.get_error(boundary.error_ref)
            if error is not None:
                summary = error.message
        return WeChatSendExecutionOutcome(
            status="not_sent",
            summary=summary,
            boundary=boundary,
            error_ref=boundary.error_ref,
            evidence_refs=(),
        )

    def _manual_review_required(
        self,
        boundary: WeChatSendBoundary,
    ) -> WeChatSendExecutionOutcome:
        summary = (
            "WeChat send boundary requires manual review before any retry; "
            f"current status is {boundary.status}."
        )
        return WeChatSendExecutionOutcome(
            status="blocked",
            summary=summary,
            boundary=boundary,
            error_ref=boundary.error_ref,
            evidence_refs=(),
        )

    def _mark_sent(
        self,
        boundary: WeChatSendBoundary,
        request: WeChatSendExecutionRequest,
        attempt: WeChatSendAttemptResult,
    ) -> WeChatSendExecutionOutcome:
        send_evidence = self._put_send_evidence(boundary, attempt)
        result_evidence = self.execution_store.put_evidence(
            EvidenceRef(
                evidence_id=_evidence_id(boundary.execution_id, "result-summary"),
                execution_id=boundary.execution_id,
                kind="result_summary",
                title="WeChat send result",
                summary="WeChat message send completed after user confirmation.",
                object_ref={
                    "contactSummary": request.contact_summary,
                    "messagePreview": request.message_preview,
                    "sendBoundaryStatus": "sent",
                    "confirmationId": boundary.confirmation_id,
                },
            )
        )
        result_ref = _result_ref(boundary.execution_id)
        result = self.execution_store.put_result(
            TaskResult(
                result_ref=result_ref,
                execution_id=boundary.execution_id,
                summary=(
                    "WeChat message sent after confirmation to "
                    f"{request.contact_summary}."
                ),
                structured_payload={
                    "kind": "wechat_send_result",
                    "contactSummary": request.contact_summary,
                    "messagePreview": request.message_preview,
                    "sendBoundaryStatus": "sent",
                    "confirmationId": boundary.confirmation_id,
                },
                evidence_refs=(send_evidence.evidence_id, result_evidence.evidence_id),
            )
        )
        updated = self.boundary_store.transition(
            boundary.execution_id,
            "sent",
            send_observation_ref=attempt.send_observation_ref,
            result_ref=result.result_ref,
        )
        return WeChatSendExecutionOutcome(
            status="sent",
            summary=result.summary,
            boundary=updated,
            result_ref=result.result_ref,
            evidence_refs=result.evidence_refs,
        )

    def _mark_unknown(
        self,
        boundary: WeChatSendBoundary,
        request: WeChatSendExecutionRequest,
        attempt: WeChatSendAttemptResult,
    ) -> WeChatSendExecutionOutcome:
        send_evidence = self._put_send_evidence(boundary, attempt)
        error = self._put_error(
            boundary,
            request,
            code="wechat_send_unknown",
            message=(
                "WeChat send result is unknown after the send boundary was "
                "attempted. Manual review is required before retrying."
            ),
            retryable=False,
            evidence_refs=(send_evidence.evidence_id,),
        )
        updated = self.boundary_store.transition(
            boundary.execution_id,
            "unknown",
            send_observation_ref=attempt.send_observation_ref,
            error_ref=error.error_ref,
        )
        return WeChatSendExecutionOutcome(
            status="unknown",
            summary=error.message,
            boundary=updated,
            error_ref=error.error_ref,
            evidence_refs=error.evidence_refs,
        )

    def _mark_not_sent(
        self,
        boundary: WeChatSendBoundary,
        request: WeChatSendExecutionRequest,
        *,
        code: str,
        message: str,
        retryable: bool,
        evidence_refs: tuple[str, ...] = (),
    ) -> WeChatSendExecutionOutcome:
        error = self._put_error(
            boundary,
            request,
            code=code,
            message=message,
            retryable=retryable,
            evidence_refs=evidence_refs,
        )
        updated = self.boundary_store.transition(
            boundary.execution_id,
            "not_sent",
            error_ref=error.error_ref,
        )
        return WeChatSendExecutionOutcome(
            status="not_sent",
            summary=error.message,
            boundary=updated,
            error_ref=error.error_ref,
            evidence_refs=error.evidence_refs,
        )

    def _put_send_evidence(
        self,
        boundary: WeChatSendBoundary,
        attempt: WeChatSendAttemptResult,
    ) -> EvidenceRef:
        return self.execution_store.put_evidence(
            EvidenceRef(
                evidence_id=_evidence_id(boundary.execution_id, "send-observation"),
                execution_id=boundary.execution_id,
                kind="tool_observation",
                title="WeChat send observation",
                summary=attempt.summary,
                object_ref={
                    "sendBoundaryStatus": attempt.status,
                    "sendObservationRef": attempt.send_observation_ref,
                    "reason": attempt.reason,
                    "metadata": attempt.metadata or {},
                },
            )
        )

    def _put_error(
        self,
        boundary: WeChatSendBoundary,
        request: WeChatSendExecutionRequest,
        *,
        code: str,
        message: str,
        retryable: bool,
        evidence_refs: tuple[str, ...],
    ) -> TaskError:
        error_evidence = self.execution_store.put_evidence(
            EvidenceRef(
                evidence_id=_evidence_id(boundary.execution_id, f"error-{code}"),
                execution_id=boundary.execution_id,
                kind="error_summary",
                title="WeChat send error",
                summary=message,
                object_ref={
                    "code": code,
                    "contactSummary": request.contact_summary,
                    "messagePreview": request.message_preview,
                    "sendBoundaryStatus": "not_sent"
                    if code != "wechat_send_unknown"
                    else "unknown",
                },
            )
        )
        return self.execution_store.put_error(
            TaskError(
                error_ref=_error_ref(boundary.execution_id, code),
                execution_id=boundary.execution_id,
                code=code,
                message=message,
                retryable=retryable,
                recovery_hint=(
                    "Start a new task after manual review if the message still "
                    "needs to be sent."
                ),
                evidence_refs=(*evidence_refs, error_evidence.evidence_id),
            )
        )


def _result_ref(execution_id: str) -> str:
    return f"result:wechat-send:{execution_id}"


def _error_ref(execution_id: str, code: str) -> str:
    return f"error:wechat-send:{execution_id}:{code}"


def _evidence_id(execution_id: str, kind: str) -> str:
    return f"evidence:wechat-send:{execution_id}:{kind}"


def _attempt_metadata_bool(attempt: WeChatSendAttemptResult, key: str) -> bool:
    if attempt.metadata is None:
        return False
    return attempt.metadata.get(key) == "true"


def _attempt_error_code(
    attempt: WeChatSendAttemptResult,
    default: str,
) -> str:
    if attempt.metadata is None:
        return default
    failure_kind = attempt.metadata.get("failure_kind")
    if isinstance(failure_kind, str) and failure_kind:
        return f"wechat_send_{failure_kind}"
    return default


__all__ = [
    "WeChatSendAdapter",
    "WeChatSendExecutionOutcome",
    "WeChatSendExecutionRequest",
    "WeChatSendExecutionService",
    "WeChatSendExecutionStatus",
]
