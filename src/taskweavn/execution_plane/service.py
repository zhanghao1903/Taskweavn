"""Execution Plane service protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from taskweavn.execution_plane.models import (
    CancelTaskCommand,
    EvidencePage,
    RetryTaskCommand,
    TaskError,
    TaskEventPage,
    TaskEventQuery,
    TaskExecution,
    TaskRequest,
    TaskResult,
)


@runtime_checkable
class TaskApiService(Protocol):
    def publish_task(self, request: TaskRequest) -> TaskExecution: ...

    def get_task(self, execution_id: str) -> TaskExecution: ...

    def cancel_task(
        self,
        execution_id: str,
        command: CancelTaskCommand,
    ) -> TaskExecution: ...

    def retry_task(
        self,
        execution_id: str,
        command: RetryTaskCommand,
    ) -> TaskExecution: ...

    def list_events(
        self,
        execution_id: str,
        query: TaskEventQuery | None = None,
    ) -> TaskEventPage: ...

    def get_result(self, result_ref: str) -> TaskResult: ...

    def get_error(self, error_ref: str) -> TaskError: ...

    def list_evidence(self, execution_id: str) -> EvidencePage: ...
