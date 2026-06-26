"""Runtime wiring for the local macOS WeChat send MVP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from taskweavn.execution_plane.errors import ExecutionPlaneError
from taskweavn.execution_plane.models import (
    EvidenceRef,
    TaskError,
    TaskEvent,
    TaskExecution,
    TaskRequest,
    utcnow,
)
from taskweavn.execution_plane.store import ExecutionPlaneStore
from taskweavn.execution_plane.wechat_send_boundary import (
    WeChatSendBoundary,
    WeChatSendBoundaryStore,
)
from taskweavn.execution_plane.wechat_send_execution import (
    WeChatSendExecutionRequest,
    WeChatSendExecutionService,
)
from taskweavn.integrations.wechat_desktop.confirmation import (
    WeChatSendActionFingerprint,
    WeChatSendConfirmationAuthorizer,
    build_wechat_send_confirmation_payload,
)
from taskweavn.integrations.wechat_desktop.models import (
    WeChatContactResolution,
    WeChatDraftState,
    WeChatOperationResult,
    WeChatReadiness,
    WeChatSendAttemptResult,
    WeChatSendTaskInput,
    wechat_message_preview,
)
from taskweavn.interaction import MessageBus, MessageStream
from taskweavn.task.bus import TaskBus
from taskweavn.task.models import TaskDomain
from taskweavn.task.stores import TaskStoreError
from taskweavn.tools import RequestConfirmationTool

WECHAT_SEND_TASK_TYPE = "communication.wechat.send_message"
WECHAT_SEND_CAPABILITY = "communication.wechat_desktop_send"


class WeChatSendRuntimeAdapter(Protocol):
    def readiness(self) -> WeChatReadiness: ...

    def open_or_focus(self) -> WeChatOperationResult: ...

    def resolve_contact(
        self,
        task_input: WeChatSendTaskInput,
        *,
        execution_id: str | None = None,
        idempotency_key: str | None = None,
        session_id: str | None = None,
    ) -> WeChatContactResolution: ...

    def draft_message(
        self,
        resolution: WeChatContactResolution,
        message_text: str,
    ) -> WeChatDraftState: ...

    def send_after_confirmation(
        self,
        fingerprint: WeChatSendActionFingerprint,
        *,
        contact_summary: str,
        message_preview: str,
        confirmation_id: str | None = None,
    ) -> WeChatSendAttemptResult: ...


@dataclass(frozen=True)
class WeChatSendRuntimeConfig:
    app_identity: str = "com.tencent.xinWeChat"
    agent_id: str = "wechat_send_runtime"


@dataclass(frozen=True)
class WeChatSendRuntimeHandler:
    """Run one local WeChat send task through draft -> confirmation -> send."""

    task_bus: TaskBus
    message_bus: MessageBus
    message_stream: MessageStream
    execution_store: ExecutionPlaneStore
    boundary_store: WeChatSendBoundaryStore
    adapter: WeChatSendRuntimeAdapter
    config: WeChatSendRuntimeConfig = WeChatSendRuntimeConfig()

    task_type: str = WECHAT_SEND_TASK_TYPE

    def validate_request(self, request: TaskRequest) -> None:
        if request.task_type != self.task_type:
            return
        _task_input_from_request(request)
        if not request.policy.requires_human_confirmation:
            raise ExecutionPlaneError(
                "permission_denied",
                "WeChat send requires explicit human confirmation.",
                status_code=403,
                details={"taskType": request.task_type},
            )
        if request.policy.risk_level != "high":
            raise ExecutionPlaneError(
                "invalid_task_request",
                "WeChat send must use high risk policy.",
                status_code=400,
                details={"taskType": request.task_type, "riskLevel": request.policy.risk_level},
            )
        if request.policy.required_capability != WECHAT_SEND_CAPABILITY:
            raise ExecutionPlaneError(
                "invalid_task_request",
                "WeChat send requires communication.wechat_desktop_send capability.",
                status_code=400,
                details={
                    "taskType": request.task_type,
                    "requiredCapability": request.policy.required_capability,
                },
            )

    def publish_or_resume(
        self,
        request: TaskRequest,
        execution: TaskExecution,
    ) -> TaskExecution:
        task_input = _task_input_from_request(request)
        boundary = self.boundary_store.get(execution.execution_id)
        if boundary is None:
            return self._start_draft_and_confirmation(request, execution, task_input)
        return self._resume_after_confirmation(request, execution, task_input, boundary)

    def _start_draft_and_confirmation(
        self,
        request: TaskRequest,
        execution: TaskExecution,
        task_input: WeChatSendTaskInput,
    ) -> TaskExecution:
        self._ensure_running_task(execution)
        evidence_ids: list[str] = []

        readiness = self.adapter.readiness()
        evidence_ids.append(
            self._put_evidence(
                execution,
                suffix="readiness",
                title="WeChat readiness",
                summary=readiness.summary,
                object_ref={
                    "status": readiness.status,
                    "appName": readiness.app_name,
                    "bundleId": readiness.bundle_id,
                    "observationRef": readiness.observation_ref,
                },
            ).evidence_id
        )
        if readiness.status != "ready":
            return self._fail_execution(
                execution,
                code="wechat_not_ready",
                message=readiness.summary,
                evidence_refs=tuple(evidence_ids),
                retryable=True,
            )

        opened = self.adapter.open_or_focus()
        evidence_ids.append(
            self._put_evidence(
                execution,
                suffix="open",
                title="WeChat open/focus",
                summary=opened.summary,
                object_ref={
                    "status": opened.status,
                    "observationRef": opened.observation_ref,
                },
            ).evidence_id
        )
        if opened.status != "ok":
            return self._fail_execution(
                execution,
                code="wechat_open_failed",
                message=opened.summary,
                evidence_refs=tuple(evidence_ids),
                retryable=opened.status in {"needs_user", "not_available"},
            )

        resolution = self.adapter.resolve_contact(
            task_input,
            execution_id=execution.execution_id,
            idempotency_key=request.idempotency_key,
            session_id=execution.session_id,
        )
        evidence_ids.append(
            self._put_evidence(
                execution,
                suffix="contact-resolution",
                title="WeChat contact resolution",
                summary=_contact_resolution_summary(resolution),
                object_ref={
                    "status": resolution.status,
                    "selected": (
                        resolution.selected.summary()
                        if resolution.selected is not None
                        else None
                    ),
                    "candidateCount": len(resolution.candidates),
                    "observationRef": resolution.observation_ref,
                    "reason": resolution.reason,
                    "diagnostics": resolution.diagnostics,
                },
            ).evidence_id
        )
        if resolution.status != "resolved" or resolution.selected is None:
            return self._fail_execution(
                execution,
                code=f"wechat_contact_{resolution.status}",
                message=resolution.reason or _contact_resolution_summary(resolution),
                evidence_refs=tuple(evidence_ids),
                retryable=resolution.status in {"needs_user", "failed"},
            )

        draft = self.adapter.draft_message(resolution, task_input.message_text)
        evidence_ids.append(
            self._put_evidence(
                execution,
                suffix="draft",
                title="WeChat draft",
                summary=(
                    "WeChat message was drafted without sending."
                    if draft.status == "drafted"
                    else draft.reason or "WeChat draft failed."
                ),
                object_ref={
                    "status": draft.status,
                    "contactSummary": draft.contact_summary,
                    "messagePreview": draft.message_preview,
                    "messageHash": draft.message_hash,
                    "draftObservationRef": draft.draft_observation_ref,
                    "reason": draft.reason,
                },
            ).evidence_id
        )
        if draft.status != "drafted":
            return self._fail_execution(
                execution,
                code="wechat_draft_failed",
                message=draft.reason or "WeChat draft failed.",
                evidence_refs=tuple(evidence_ids),
                retryable=True,
            )

        fingerprint = WeChatSendActionFingerprint.from_draft(
            execution_id=execution.execution_id,
            idempotency_key=request.idempotency_key,
            draft_state=draft,
            app_identity=self.config.app_identity,
        )
        boundary = self.boundary_store.put(
            WeChatSendBoundary(
                execution_id=execution.execution_id,
                idempotency_key=request.idempotency_key,
                task_ref_kind="execution_plane_task",
                task_ref_id=execution.task_id,
                contact_summary_hash=fingerprint.contact_summary_hash,
                message_hash=fingerprint.message_hash,
                action_fingerprint=fingerprint.digest(),
            )
        )
        boundary = self.boundary_store.transition(
            boundary.execution_id,
            "drafted",
            draft_observation_ref=draft.draft_observation_ref,
        )
        confirmation_payload = build_wechat_send_confirmation_payload(
            contact_summary=draft.contact_summary,
            message_preview=draft.message_preview,
            message_hash=draft.message_hash,
            action_fingerprint=fingerprint,
        )
        confirmation = RequestConfirmationTool(
            message_bus=self.message_bus,
            task_bus=self.task_bus,
            session_id=execution.session_id,
            task_id=execution.task_id,
            agent_id=self.config.agent_id,
        ).execute(confirmation_payload.to_request_action())
        boundary = self.boundary_store.transition(
            boundary.execution_id,
            "confirmation_requested",
            confirmation_id=confirmation.confirmation_id,
        )
        evidence_ids.append(
            self._put_evidence(
                execution,
                suffix="confirmation-request",
                title="WeChat send confirmation requested",
                summary="User confirmation is required before sending the WeChat message.",
                object_ref={
                    "confirmationId": boundary.confirmation_id,
                    "actionFingerprint": boundary.action_fingerprint,
                    "contactSummary": draft.contact_summary,
                    "messagePreview": draft.message_preview,
                },
            ).evidence_id
        )
        updated = execution.model_copy(
            update={
                "status": "waiting_for_user",
                "updated_at": utcnow(),
                "evidence_refs": tuple(evidence_ids),
            }
        )
        self.execution_store.put_execution(updated)
        self.execution_store.append_event(
            TaskEvent(
                execution_id=execution.execution_id,
                task_id=execution.task_id,
                kind="task.waiting_for_user",
                summary="WeChat send is waiting for user confirmation.",
                evidence_refs=tuple(evidence_ids),
                data={"confirmationId": boundary.confirmation_id},
            )
        )
        return updated

    def _resume_after_confirmation(
        self,
        request: TaskRequest,
        execution: TaskExecution,
        task_input: WeChatSendTaskInput,
        boundary: WeChatSendBoundary,
    ) -> TaskExecution:
        if boundary.status == "sent" and execution.status == "done":
            return execution
        if boundary.status in {"not_sent", "unknown"} and execution.status == "failed":
            return execution
        if boundary.confirmation_id is not None:
            authorization = WeChatSendConfirmationAuthorizer(self.message_stream).authorize(
                confirmation_id=boundary.confirmation_id,
                action_fingerprint=_fingerprint_from_boundary(
                    request,
                    boundary,
                    app_identity=self.config.app_identity,
                ),
            )
            if authorization.status == "pending":
                return execution.model_copy(
                    update={"status": "waiting_for_user", "updated_at": utcnow()}
                )
            task = self.task_bus.get(execution.session_id, execution.task_id)
            if (
                task is not None
                and task.status == "waiting_for_user"
                and task.waiting_for_confirmation_id == boundary.confirmation_id
            ):
                self.task_bus.resume_after_confirmation(
                    execution.session_id,
                    execution.task_id,
                    confirmation_id=boundary.confirmation_id,
                )

        self._ensure_running_task(execution)
        fingerprint = _fingerprint_from_boundary(
            request,
            boundary,
            app_identity=self.config.app_identity,
        )
        service = WeChatSendExecutionService(
            boundary_store=self.boundary_store,
            execution_store=self.execution_store,
            confirmation_authorizer=WeChatSendConfirmationAuthorizer(self.message_stream),
            adapter=self.adapter,
        )
        outcome = service.execute(
            WeChatSendExecutionRequest(
                execution_id=execution.execution_id,
                action_fingerprint=fingerprint,
                contact_summary=_contact_summary_from_request(task_input),
                message_preview=wechat_message_preview(task_input.message_text),
            )
        )
        if outcome.status == "waiting_for_user":
            updated = execution.model_copy(
                update={"status": "waiting_for_user", "updated_at": utcnow()}
            )
            self.execution_store.put_execution(updated)
            return updated
        if outcome.status == "sent" and outcome.result_ref is not None:
            self.task_bus.complete(
                execution.session_id,
                execution.task_id,
                result_ref=outcome.result_ref,
            )
            updated = execution.model_copy(
                update={
                    "status": "done",
                    "updated_at": utcnow(),
                    "completed_at": utcnow(),
                    "result_ref": outcome.result_ref,
                    "evidence_refs": outcome.evidence_refs,
                }
            )
            self.execution_store.put_execution(updated)
            self.execution_store.append_event(
                TaskEvent(
                    execution_id=execution.execution_id,
                    task_id=execution.task_id,
                    kind="task.result_ready",
                    summary=outcome.summary,
                    evidence_refs=outcome.evidence_refs,
                    data={"resultRef": outcome.result_ref},
                )
            )
            return updated
        error_ref = outcome.error_ref or f"error:wechat-send:{execution.execution_id}"
        self.task_bus.fail(execution.session_id, execution.task_id, error_ref=error_ref)
        updated = execution.model_copy(
            update={
                "status": "failed",
                "updated_at": utcnow(),
                "completed_at": utcnow(),
                "error_ref": error_ref,
                "evidence_refs": outcome.evidence_refs,
            }
        )
        self.execution_store.put_execution(updated)
        self.execution_store.append_event(
            TaskEvent(
                execution_id=execution.execution_id,
                task_id=execution.task_id,
                kind="task.failed",
                summary=outcome.summary,
                evidence_refs=outcome.evidence_refs,
                data={"errorRef": error_ref},
            )
        )
        return updated

    def _ensure_running_task(self, execution: TaskExecution) -> TaskDomain:
        task = self.task_bus.get(execution.session_id, execution.task_id)
        if task is None:
            raise ExecutionPlaneError(
                "task_not_found",
                "WeChat send runtime task was not found in TaskBus.",
                status_code=404,
                details={"executionId": execution.execution_id, "taskId": execution.task_id},
            )
        if task.status == "running":
            return task
        if task.status != "pending":
            raise ExecutionPlaneError(
                "execution_failed",
                f"WeChat send runtime expected pending/running task, got {task.status}.",
                status_code=409,
                retryable=True,
                details={"executionId": execution.execution_id, "taskStatus": task.status},
            )
        claimed = self.task_bus.claim_next(
            execution.session_id,
            capability=task.required_capability,
            agent_id=self.config.agent_id,
        )
        if claimed is None or claimed.task_id != execution.task_id:
            raise ExecutionPlaneError(
                "lease_conflict",
                "WeChat send runtime could not claim the target task.",
                status_code=409,
                retryable=True,
                details={"executionId": execution.execution_id, "taskId": execution.task_id},
            )
        return claimed

    def _fail_execution(
        self,
        execution: TaskExecution,
        *,
        code: str,
        message: str,
        evidence_refs: tuple[str, ...],
        retryable: bool,
    ) -> TaskExecution:
        error = self.execution_store.put_error(
            TaskError(
                error_ref=f"error:wechat-runtime:{execution.execution_id}:{code}",
                execution_id=execution.execution_id,
                code=code,
                message=message,
                retryable=retryable,
                recovery_hint="Review WeChat readiness/contact state and start a new task.",
                evidence_refs=evidence_refs,
            )
        )
        with _suppress_task_store_error():
            self.task_bus.fail(
                execution.session_id,
                execution.task_id,
                error_ref=error.error_ref,
            )
        updated = execution.model_copy(
            update={
                "status": "failed",
                "updated_at": utcnow(),
                "completed_at": utcnow(),
                "error_ref": error.error_ref,
                "evidence_refs": evidence_refs,
            }
        )
        self.execution_store.put_execution(updated)
        self.execution_store.append_event(
            TaskEvent(
                execution_id=execution.execution_id,
                task_id=execution.task_id,
                kind="task.failed",
                summary=message,
                evidence_refs=evidence_refs,
                data={"errorRef": error.error_ref, "code": code},
            )
        )
        return updated

    def _put_evidence(
        self,
        execution: TaskExecution,
        *,
        suffix: str,
        title: str,
        summary: str,
        object_ref: dict[str, object],
    ) -> EvidenceRef:
        return self.execution_store.put_evidence(
            EvidenceRef(
                evidence_id=f"evidence:wechat-runtime:{execution.execution_id}:{suffix}",
                execution_id=execution.execution_id,
                kind="tool_observation",
                title=title,
                summary=summary,
                object_ref=object_ref,
            )
        )


class _suppress_task_store_error:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return isinstance(exc, TaskStoreError)


def _task_input_from_request(request: TaskRequest) -> WeChatSendTaskInput:
    return WeChatSendTaskInput(
        contact_display_name=_required_input_str(
            request,
            "contactDisplayName",
            "contact_display_name",
        ),
        message_text=_required_input_str(request, "messageText", "message_text"),
        contact_alias=_optional_input_str(request, "contactAlias", "contact_alias"),
        external_ref=_safe_external_ref(request),
        operator_note=_optional_input_str(request, "operatorNote", "operator_note"),
    )


def _required_input_str(request: TaskRequest, *keys: str) -> str:
    value = _optional_input_str(request, *keys)
    if value is None:
        raise ExecutionPlaneError(
            "invalid_task_request",
            f"WeChat send input requires {keys[0]}.",
            status_code=400,
            details={"taskType": request.task_type, "field": keys[0]},
        )
    return value


def _optional_input_str(request: TaskRequest, *keys: str) -> str | None:
    for key in keys:
        value = request.input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _safe_external_ref(request: TaskRequest) -> dict[str, str] | None:
    if request.external_ref is None:
        return None
    return request.external_ref.model_dump(mode="json", by_alias=True)


def _fingerprint_from_boundary(
    request: TaskRequest,
    boundary: WeChatSendBoundary,
    *,
    app_identity: str,
) -> WeChatSendActionFingerprint:
    return WeChatSendActionFingerprint(
        execution_id=boundary.execution_id,
        idempotency_key=request.idempotency_key,
        contact_summary_hash=boundary.contact_summary_hash,
        message_hash=boundary.message_hash,
        draft_observation_ref=boundary.draft_observation_ref,
        app_identity=app_identity,
    )


def _contact_summary_from_request(task_input: WeChatSendTaskInput) -> str:
    if task_input.contact_alias:
        return f"{task_input.contact_display_name} ({task_input.contact_alias})"
    return task_input.contact_display_name


def _contact_resolution_summary(resolution: WeChatContactResolution) -> str:
    if resolution.status == "resolved" and resolution.selected is not None:
        return f"WeChat contact resolved: {resolution.selected.summary()}."
    return resolution.reason or f"WeChat contact resolution status: {resolution.status}."


__all__ = [
    "WECHAT_SEND_CAPABILITY",
    "WECHAT_SEND_TASK_TYPE",
    "WeChatSendRuntimeAdapter",
    "WeChatSendRuntimeConfig",
    "WeChatSendRuntimeHandler",
]
