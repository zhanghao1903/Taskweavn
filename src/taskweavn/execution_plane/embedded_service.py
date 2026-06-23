"""Embedded Execution Plane service backed by the current TaskBus."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol, cast
from uuid import NAMESPACE_URL, uuid5

from taskweavn.execution_plane.env_registry import (
    ExecutionEnvRegistry,
    InMemoryExecutionEnvRegistry,
    default_local_execution_env,
)
from taskweavn.execution_plane.errors import ExecutionPlaneError
from taskweavn.execution_plane.models import (
    CancelTaskCommand,
    EvidencePage,
    EvidenceRef,
    RetryTaskCommand,
    TaskError,
    TaskEvent,
    TaskEventPage,
    TaskEventQuery,
    TaskExecution,
    TaskExecutionStatus,
    TaskRequest,
    TaskRequester,
    TaskResult,
    utcnow,
)
from taskweavn.execution_plane.service import TaskApiService
from taskweavn.execution_plane.store import (
    ExecutionPlaneStore,
    InMemoryExecutionPlaneStore,
    TaskRequestIdempotencyRecord,
    request_hash,
    scoped_idempotency_key,
)
from taskweavn.task.bus import TaskBus
from taskweavn.task.models import TaskDispatchConstraints, TaskDomain
from taskweavn.task.result_summary import TaskExecutionSummaryStore
from taskweavn.task.stores import TaskStoreError


class EmbeddedTaskRuntimeHandler(Protocol):
    @property
    def task_type(self) -> str: ...

    def validate_request(self, request: TaskRequest) -> None: ...

    def publish_or_resume(
        self,
        request: TaskRequest,
        execution: TaskExecution,
    ) -> TaskExecution: ...


class EmbeddedTaskApiService(TaskApiService):
    """Service-compatible Task API that runs in-process over TaskBus."""

    def __init__(
        self,
        *,
        task_bus: TaskBus,
        store: ExecutionPlaneStore | None = None,
        env_registry: ExecutionEnvRegistry | None = None,
        summary_store: TaskExecutionSummaryStore | None = None,
        default_session_id: str = "execution-plane",
        runtime_handlers: Iterable[EmbeddedTaskRuntimeHandler] = (),
    ) -> None:
        self._task_bus = task_bus
        self._store = store or InMemoryExecutionPlaneStore()
        self._env_registry = env_registry or InMemoryExecutionEnvRegistry(
            (default_local_execution_env(),)
        )
        self._summary_store = summary_store
        self._default_session_id = default_session_id
        self._runtime_handlers = {handler.task_type: handler for handler in runtime_handlers}

    def publish_task(self, request: TaskRequest) -> TaskExecution:
        runtime_handler = self._runtime_handlers.get(request.task_type)
        if runtime_handler is not None:
            runtime_handler.validate_request(request)
        scoped_key = scoped_idempotency_key(request)
        current_hash = request_hash(request)
        existing = self._store.get_idempotency(scoped_key)
        if existing is not None:
            if existing.request_hash != current_hash:
                raise ExecutionPlaneError(
                    "idempotency_conflict",
                    "idempotency key was already used with a different request",
                    status_code=409,
                    details={
                        "existingRequestHash": existing.request_hash,
                        "requestHash": current_hash,
                    },
                )
            execution = self.get_task(existing.execution_id)
            if runtime_handler is not None:
                return runtime_handler.publish_or_resume(request, execution)
            return execution

        env = self._env_registry.find_compatible(request.policy)
        if env is None:
            raise ExecutionPlaneError(
                "capability_not_available",
                "no execution environment can satisfy the requested capability",
                status_code=409,
                retryable=True,
                details={
                    "requiredCapability": request.policy.required_capability,
                    "allowedTools": list(request.policy.allowed_tools),
                },
            )

        session_id = _session_id_for_request(request, default_session_id=self._default_session_id)
        task_id = _task_id_for_request(request)
        execution_id = _execution_id_for_task_id(task_id)
        now = utcnow()
        task = _task_for_request(request, session_id=session_id, task_id=task_id)
        try:
            self._task_bus.publish(task)
        except TaskStoreError as exc:
            existing_task = self._task_bus.get(session_id, task_id)
            if existing_task is None:
                raise ExecutionPlaneError(
                    "execution_failed",
                    str(exc),
                    status_code=500,
                    retryable=True,
                    details={"taskId": task_id},
                ) from exc

        execution = TaskExecution(
            execution_id=execution_id,
            task_id=task_id,
            request_id=scoped_key,
            status="pending",
            requester=request.requester,
            external_ref=request.external_ref,
            task_type=request.task_type,
            required_capability=request.policy.required_capability,
            env_id=env.env_id,
            created_at=now,
            updated_at=now,
            session_id=session_id,
        )
        self._store.put_execution(execution)
        self._store.put_idempotency(
            TaskRequestIdempotencyRecord(
                scoped_key=scoped_key,
                request_hash=current_hash,
                execution_id=execution_id,
                request=request,
                created_at=now,
                updated_at=now,
            )
        )
        self._store.append_event(
            TaskEvent(
                execution_id=execution_id,
                task_id=task_id,
                kind="task.accepted",
                occurred_at=now,
                summary="Task accepted by Execution Plane.",
                data={
                    "taskType": request.task_type,
                    "requiredCapability": request.policy.required_capability,
                    "envId": env.env_id,
                },
            )
        )
        if runtime_handler is not None:
            return runtime_handler.publish_or_resume(request, execution)
        return execution

    def get_task(self, execution_id: str) -> TaskExecution:
        execution = self._require_execution(execution_id)
        task = self._task_bus.get(execution.session_id, execution.task_id)
        if task is None:
            raise ExecutionPlaneError(
                "task_not_found",
                "execution task was not found in TaskBus",
                status_code=404,
                details={"executionId": execution_id, "taskId": execution.task_id},
            )
        updated = _execution_from_task(execution, task)
        if updated != execution:
            self._store.put_execution(updated)
        return updated

    def cancel_task(
        self,
        execution_id: str,
        command: CancelTaskCommand,
    ) -> TaskExecution:
        execution = self._require_execution(execution_id)
        try:
            task = self._task_bus.request_interrupt(
                execution.session_id,
                execution.task_id,
                reason=command.reason,
                requested_by="user",
                request_id=command.command_id,
            )
        except TaskStoreError as exc:
            raise ExecutionPlaneError(
                "task_not_cancellable",
                str(exc),
                status_code=409,
                details={"executionId": execution_id},
            ) from exc
        updated = _execution_from_task(execution, task)
        self._store.put_execution(updated)
        self._store.append_event(
            TaskEvent(
                execution_id=execution_id,
                task_id=execution.task_id,
                kind="task.cancelled" if updated.status == "failed" else "task.progress",
                summary=f"Cancel requested: {command.reason}",
                data={"commandId": command.command_id},
            )
        )
        return updated

    def retry_task(
        self,
        execution_id: str,
        command: RetryTaskCommand,
    ) -> TaskExecution:
        execution = self._require_execution(execution_id)
        try:
            task = self._task_bus.retry(
                execution.session_id,
                execution.task_id,
                instruction=command.instruction,
            )
        except TaskStoreError as exc:
            raise ExecutionPlaneError(
                "task_not_retryable",
                str(exc),
                status_code=409,
                details={"executionId": execution_id},
            ) from exc
        updated = _execution_from_task(execution, task)
        self._store.put_execution(updated)
        self._store.append_event(
            TaskEvent(
                execution_id=execution_id,
                task_id=execution.task_id,
                kind="task.progress",
                summary="Retry requested.",
                data={"commandId": command.command_id},
            )
        )
        return updated

    def list_events(
        self,
        execution_id: str,
        query: TaskEventQuery | None = None,
    ) -> TaskEventPage:
        self._require_execution(execution_id)
        effective_query = query or TaskEventQuery()
        return TaskEventPage(
            items=self._store.list_events(execution_id, limit=effective_query.limit)
        )

    def get_result(self, result_ref: str) -> TaskResult:
        result = self._store.get_result(result_ref)
        if result is not None:
            return result
        if self._summary_store is not None:
            summary = self._summary_store.get(result_ref)
            if summary is not None and summary.kind == "result":
                execution = self._execution_for_task(summary.session_id, summary.task_id)
                result = TaskResult(
                    result_ref=result_ref,
                    execution_id=execution.execution_id,
                    summary=summary.summary,
                    structured_payload=summary.metadata,
                    created_at=summary.created_at,
                )
                self._store.put_result(result)
                return result
        raise ExecutionPlaneError(
            "result_not_found",
            "task result was not found",
            status_code=404,
            details={"resultRef": result_ref},
        )

    def get_error(self, error_ref: str) -> TaskError:
        error = self._store.get_error(error_ref)
        if error is not None:
            return error
        if self._summary_store is not None:
            summary = self._summary_store.get(error_ref)
            if summary is not None and summary.kind == "error":
                execution = self._execution_for_task(summary.session_id, summary.task_id)
                error = TaskError(
                    error_ref=error_ref,
                    execution_id=execution.execution_id,
                    code=summary.error_type or "task_failed",
                    message=summary.error_message or summary.summary,
                    retryable=True,
                    recovery_hint=summary.stop_reason,
                    created_at=summary.created_at,
                )
                self._store.put_error(error)
                return error
        raise ExecutionPlaneError(
            "result_not_found",
            "task error was not found",
            status_code=404,
            details={"errorRef": error_ref},
        )

    def list_evidence(self, execution_id: str) -> EvidencePage:
        self._require_execution(execution_id)
        return EvidencePage(items=self._store.list_evidence(execution_id))

    def record_result(self, result: TaskResult) -> TaskResult:
        return self._store.put_result(result)

    def record_error(self, error: TaskError) -> TaskError:
        return self._store.put_error(error)

    def record_evidence(self, evidence: EvidenceRef) -> EvidenceRef:
        return self._store.put_evidence(evidence)

    def _require_execution(self, execution_id: str) -> TaskExecution:
        execution = self._store.get_execution(execution_id)
        if execution is None:
            raise ExecutionPlaneError(
                "task_not_found",
                "task execution was not found",
                status_code=404,
                details={"executionId": execution_id},
            )
        return execution

    def _execution_for_task(self, session_id: str, task_id: str) -> TaskExecution:
        # The service store is keyed by execution id, so this is intentionally a
        # narrow bridge for result summary compatibility. Deterministic ids keep
        # it queryable without scanning.
        execution_id = _execution_id_for_task_id(task_id)
        execution = self._store.get_execution(execution_id)
        if execution is not None:
            return execution
        task = self._task_bus.get(session_id, task_id)
        if task is None:
            raise ExecutionPlaneError(
                "task_not_found",
                "task summary points to a missing TaskBus task",
                status_code=404,
                details={"sessionId": session_id, "taskId": task_id},
            )
        fallback = TaskExecution(
            execution_id=execution_id,
            task_id=task_id,
            request_id=f"taskbus:{session_id}:{task_id}",
            status=_status_from_task(task.status),
            requester=TaskRequester(kind="system", id="taskbus"),
            task_type="taskbus.legacy_execution",
            required_capability=task.required_capability,
            session_id=session_id,
            result_ref=task.result_ref,
            error_ref=task.error_ref,
            created_at=task.created_at,
            updated_at=task.completed_at or task.started_at or task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
        )
        return self._store.put_execution(fallback)


def _task_id_for_request(request: TaskRequest) -> str:
    payload = f"{request.requester.scoped_id}:{request.idempotency_key}"
    return uuid5(NAMESPACE_URL, f"taskweavn.execution_plane.task:{payload}").hex


def _execution_id_for_task_id(task_id: str) -> str:
    return f"exec_{task_id}"


def _session_id_for_request(request: TaskRequest, *, default_session_id: str) -> str:
    raw = request.metadata.get("sessionId") or request.metadata.get("session_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if request.requester.kind == "plato":
        external = request.external_ref
        if external is not None and external.system == "plato":
            return default_session_id
    safe_requester = request.requester.id.replace("/", "_").replace(":", "_")
    return f"external:{safe_requester}" if safe_requester else default_session_id


def _task_for_request(
    request: TaskRequest,
    *,
    session_id: str,
    task_id: str,
) -> TaskDomain:
    now = utcnow()
    summary = _optional_str(request.input.get("summary"))
    instructions = _optional_str(request.input.get("instructions"))
    acceptance = request.input.get("acceptanceCriteria") or request.input.get(
        "acceptance_criteria"
    )
    acceptance_criteria = _string_tuple(acceptance)
    metadata: dict[str, Any] = {
        "execution_plane_requester": request.requester.model_dump(mode="json", by_alias=True),
        "execution_plane_task_type": request.task_type,
        "execution_plane_idempotency_key": request.idempotency_key,
    }
    if request.external_ref is not None:
        metadata["execution_plane_external_ref"] = request.external_ref.model_dump(
            mode="json",
            by_alias=True,
        )
    return TaskDomain(
        task_id=task_id,
        session_id=session_id,
        root_id=task_id,
        intent=request.intent,
        summary=summary,
        instructions=instructions,
        acceptance_criteria=acceptance_criteria,
        required_capability=request.policy.required_capability,
        dispatch_constraints=TaskDispatchConstraints(
            required_capabilities=(request.policy.required_capability,),
            metadata=metadata,
        ),
        status="pending",
        created_by=request.requester.scoped_id,
        created_at=now,
    )


def _execution_from_task(execution: TaskExecution, task: TaskDomain) -> TaskExecution:
    task_updated_at = task.completed_at or task.started_at or execution.updated_at
    return execution.model_copy(
        update={
            "status": _status_from_task(task.status),
            "updated_at": task_updated_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "result_ref": task.result_ref,
            "error_ref": task.error_ref,
        }
    )


def _status_from_task(status: str) -> TaskExecutionStatus:
    if status in {"pending", "running", "waiting_for_user", "done", "failed"}:
        return cast(TaskExecutionStatus, status)
    return "rejected"


def _optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
