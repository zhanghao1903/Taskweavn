"""Durable task execution result summaries.

These records are the first Product 1.0 bridge between TaskBus lifecycle refs
and user-readable result/error payloads. They are not audit verdicts and they
are not raw observation logs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from taskweavn.product_errors import (
    product_error_details_for_llm_classification,
    product_error_details_for_task_failure,
)
from taskweavn.task.models import TaskDomain, TaskRef
from taskweavn.task.views import TaskSummaryView

TaskExecutionSummaryKind = Literal["result", "error"]
TaskExecutionSummarySource = Literal[
    "agent_loop",
    "execution_bridge",
    "external_agent",
]


def utcnow() -> datetime:
    return datetime.now(UTC)


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class TaskExecutionSummary(_FrozenModel):
    """Readable result/error payload addressed by TaskBus refs."""

    summary_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    kind: TaskExecutionSummaryKind
    source: TaskExecutionSummarySource
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    stop_reason: str | None = Field(default=None, min_length=1)
    final_answer: str | None = Field(default=None, min_length=1)
    error_type: str | None = Field(default=None, min_length=1)
    error_message: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _validate_kind_payload(self) -> TaskExecutionSummary:
        if self.kind == "result" and self.error_type is not None:
            raise ValueError("result summary must not include error_type")
        if self.kind == "error" and self.error_type is None:
            raise ValueError("error summary requires error_type")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        return self


@runtime_checkable
class TaskExecutionSummaryStore(Protocol):
    """Durable lookup boundary for task result/error refs."""

    def put(self, summary: TaskExecutionSummary) -> TaskExecutionSummary: ...

    def get(self, summary_id: str) -> TaskExecutionSummary | None: ...

    def get_for_task(
        self,
        session_id: str,
        task_id: str,
        *,
        kind: TaskExecutionSummaryKind | None = None,
    ) -> TaskExecutionSummary | None: ...


class InMemoryTaskExecutionSummaryStore:
    """Small in-memory implementation for focused tests."""

    def __init__(self) -> None:
        self._summaries: dict[str, TaskExecutionSummary] = {}

    def put(self, summary: TaskExecutionSummary) -> TaskExecutionSummary:
        self._summaries[summary.summary_id] = summary
        return summary

    def get(self, summary_id: str) -> TaskExecutionSummary | None:
        return self._summaries.get(summary_id)

    def get_for_task(
        self,
        session_id: str,
        task_id: str,
        *,
        kind: TaskExecutionSummaryKind | None = None,
    ) -> TaskExecutionSummary | None:
        matches = [
            summary
            for summary in self._summaries.values()
            if summary.session_id == session_id
            and summary.task_id == task_id
            and (kind is None or summary.kind == kind)
        ]
        if not matches:
            return None
        matches.sort(key=lambda summary: summary.updated_at)
        return matches[-1]


class TaskExecutionSummaryViewStore:
    """Adapter from durable execution summaries to task projection summaries."""

    def __init__(self, summary_store: TaskExecutionSummaryStore) -> None:
        self._summary_store = summary_store

    def get(self, session_id: str, task_id: str) -> TaskSummaryView | None:
        summary = self._summary_store.get_for_task(session_id, task_id)
        if summary is None:
            return None
        return task_execution_summary_to_task_summary_view(summary)


def task_execution_summary_to_task_summary_view(
    summary: TaskExecutionSummary,
) -> TaskSummaryView:
    failure_reason = None
    if summary.kind == "error":
        failure_reason = summary.error_message or summary.summary
    return TaskSummaryView(
        task_ref=TaskRef.published(summary.task_id),
        summary=summary.summary,
        failure_reason=failure_reason,
        updated_at=summary.updated_at,
    )


def build_agent_loop_result_summary(
    *,
    summary_id: str,
    task: TaskDomain,
    final_answer: str,
    stop_reason: str,
) -> TaskExecutionSummary:
    summary = final_answer.strip() or "Task completed."
    return TaskExecutionSummary(
        summary_id=summary_id,
        session_id=task.session_id,
        task_id=task.task_id,
        kind="result",
        source="agent_loop",
        title="Task completed",
        summary=summary,
        final_answer=summary,
        stop_reason=stop_reason,
        metadata={"requiredCapability": task.required_capability},
    )


def build_agent_loop_error_summary(
    *,
    summary_id: str,
    task: TaskDomain,
    stop_reason: str,
    final_answer: str = "",
) -> TaskExecutionSummary:
    reason = stop_reason.strip() or "unknown"
    message = f"AgentLoop stopped before finishing: {reason}."
    return TaskExecutionSummary(
        summary_id=summary_id,
        session_id=task.session_id,
        task_id=task.task_id,
        kind="error",
        source="agent_loop",
        title="Task execution did not finish",
        summary=message,
        final_answer=final_answer.strip() or None,
        stop_reason=reason,
        error_type="agent_loop_failed",
        error_message=message,
        metadata={
            "requiredCapability": task.required_capability,
            **product_error_details_for_task_failure(
                error_type="agent_loop_failed",
                interrupted=reason == "interrupted" or reason.startswith("cancelled"),
                diagnostic_refs={
                    "errorRef": summary_id,
                    "taskId": task.task_id,
                    "sessionId": task.session_id,
                },
            ),
        },
    )


def build_execution_exception_summary(
    *,
    summary_id: str,
    task: TaskDomain,
    exc: Exception,
) -> TaskExecutionSummary:
    error_type = type(exc).__name__
    message = f"Task execution failed with {error_type}."
    product_details = _product_error_details_for_exception(
        summary_id=summary_id,
        task=task,
        exc=exc,
        error_type=error_type,
    )
    return TaskExecutionSummary(
        summary_id=summary_id,
        session_id=task.session_id,
        task_id=task.task_id,
        kind="error",
        source="execution_bridge",
        title="Task execution failed",
        summary=message,
        error_type=error_type,
        error_message=message,
        metadata={
            "requiredCapability": task.required_capability,
            **product_details,
        },
    )


def build_execution_completed_summary(
    *,
    summary_id: str,
    task: TaskDomain,
) -> TaskExecutionSummary:
    return TaskExecutionSummary(
        summary_id=summary_id,
        session_id=task.session_id,
        task_id=task.task_id,
        kind="result",
        source="execution_bridge",
        title="Task completed",
        summary="Task completed.",
        metadata={"requiredCapability": task.required_capability},
    )


def build_external_result_ref_summary(
    *,
    result_ref: str,
    task: TaskDomain,
) -> TaskExecutionSummary:
    return TaskExecutionSummary(
        summary_id=result_ref,
        session_id=task.session_id,
        task_id=task.task_id,
        kind="result",
        source="external_agent",
        title="Task completed",
        summary=f"Task completed. Result reference: {result_ref}.",
        metadata={"requiredCapability": task.required_capability},
    )


def build_external_error_ref_summary(
    *,
    error_ref: str,
    task: TaskDomain,
) -> TaskExecutionSummary:
    return TaskExecutionSummary(
        summary_id=error_ref,
        session_id=task.session_id,
        task_id=task.task_id,
        kind="error",
        source="external_agent",
        title="Task execution failed",
        summary=f"Task execution failed. Error reference: {error_ref}.",
        error_type="external_agent_error",
        error_message=error_ref,
        metadata={
            "requiredCapability": task.required_capability,
            **product_error_details_for_task_failure(
                error_type="external_agent_error",
                diagnostic_refs={
                    "errorRef": error_ref,
                    "taskId": task.task_id,
                    "sessionId": task.session_id,
                },
            ),
        },
    )


def _product_error_details_for_exception(
    *,
    summary_id: str,
    task: TaskDomain,
    exc: Exception,
    error_type: str,
) -> dict[str, object]:
    diagnostic_refs: dict[str, object] = {
        "errorRef": summary_id,
        "taskId": task.task_id,
        "sessionId": task.session_id,
    }
    classification = getattr(exc, "classification", None)
    if classification is not None:
        provider_name = getattr(exc, "provider_name", None)
        model = getattr(exc, "model", None)
        retry_records = getattr(exc, "retry_records", ())
        if provider_name:
            diagnostic_refs["providerName"] = provider_name
        if model:
            diagnostic_refs["model"] = model
        return product_error_details_for_llm_classification(
            classification,
            retry_count=len(retry_records),
            diagnostic_refs=diagnostic_refs,
            extra={"errorType": error_type},
        )
    return product_error_details_for_task_failure(
        error_type=error_type,
        diagnostic_refs=diagnostic_refs,
    )


__all__ = [
    "InMemoryTaskExecutionSummaryStore",
    "TaskExecutionSummary",
    "TaskExecutionSummaryKind",
    "TaskExecutionSummarySource",
    "TaskExecutionSummaryStore",
    "TaskExecutionSummaryViewStore",
    "build_agent_loop_error_summary",
    "build_agent_loop_result_summary",
    "build_execution_completed_summary",
    "build_execution_exception_summary",
    "build_external_error_ref_summary",
    "build_external_result_ref_summary",
    "task_execution_summary_to_task_summary_view",
]
