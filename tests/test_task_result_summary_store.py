from __future__ import annotations

from pathlib import Path

from taskweavn.llm import ErrorClassification
from taskweavn.llm.errors import LLMProviderError
from taskweavn.task import (
    InMemoryTaskExecutionSummaryStore,
    SqliteTaskExecutionSummaryStore,
    TaskDomain,
    TaskExecutionSummaryViewStore,
    build_agent_loop_error_summary,
    build_agent_loop_result_summary,
    build_execution_exception_summary,
)


def test_sqlite_task_execution_summary_store_persists_result_and_error(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "results.sqlite"
    task = _task("task-1")
    result = build_agent_loop_result_summary(
        summary_id="agent_loop:s1:task-1:agent_finish",
        task=task,
        final_answer="Built the page.",
        stop_reason="agent_finish",
    )
    error = build_agent_loop_error_summary(
        summary_id="agent_loop_failed:s1:task-1:max_steps",
        task=task,
        stop_reason="max_steps",
    )

    first = SqliteTaskExecutionSummaryStore(db_path)
    try:
        first.put(result)
        first.put(error)
    finally:
        first.close()

    second = SqliteTaskExecutionSummaryStore(db_path)
    try:
        loaded_result = second.get(result.summary_id)
        loaded_error = second.get(error.summary_id)
        latest_error = second.get_for_task("s1", "task-1", kind="error")
    finally:
        second.close()

    assert loaded_result == result
    assert loaded_error == error
    assert latest_error == error


def test_in_memory_task_execution_summary_store_reads_latest_by_task() -> None:
    store = InMemoryTaskExecutionSummaryStore()
    task = _task("task-1")
    first = build_agent_loop_result_summary(
        summary_id="agent_loop:s1:task-1:agent_finish",
        task=task,
        final_answer="First.",
        stop_reason="agent_finish",
    )
    second = build_agent_loop_result_summary(
        summary_id="agent_loop:s1:task-1:no_tool_calls",
        task=task,
        final_answer="Second.",
        stop_reason="no_tool_calls",
    )

    store.put(first)
    store.put(second)

    assert store.get(first.summary_id) == first
    assert store.get_for_task("s1", "task-1", kind="result") == second


def test_task_execution_summary_view_store_projects_error_summary() -> None:
    store = InMemoryTaskExecutionSummaryStore()
    task = _task("task-1")
    error = build_agent_loop_error_summary(
        summary_id="agent_loop_failed:s1:task-1:max_steps",
        task=task,
        stop_reason="max_steps",
        final_answer="Partial output",
    )
    store.put(error)

    view_store = TaskExecutionSummaryViewStore(store)
    view = view_store.get("s1", "task-1")

    assert view is not None
    assert view.task_ref.id == "task-1"
    assert view.summary == "AgentLoop stopped before finishing: max_steps."
    assert view.failure_reason == "AgentLoop stopped before finishing: max_steps."


def test_execution_exception_summary_maps_llm_error_without_raw_message() -> None:
    task = _task("task-1")
    exc = LLMProviderError(
        "raw provider payload with sensitive details",
        provider_name="deepseek",
        model="deepseek-chat",
        classification=ErrorClassification.FATAL_AUTH,
    )

    summary = build_execution_exception_summary(
        summary_id="task_error:s1:task-1:llm",
        task=task,
        exc=exc,
    )

    assert summary.error_message == "Task execution failed with LLMProviderError."
    assert "sensitive details" not in summary.error_message
    assert summary.metadata["productCategory"] == "llm_auth_or_config"
    assert summary.metadata["recoveryActions"] == [
        "open_settings",
        "export_diagnostics",
    ]
    assert summary.metadata["llmClassification"] == "fatal_auth"
    assert summary.metadata["diagnosticRefs"] == {
        "errorRef": "task_error:s1:task-1:llm",
        "taskId": "task-1",
        "sessionId": "s1",
        "providerName": "deepseek",
        "model": "deepseek-chat",
    }


def test_agent_loop_error_summary_marks_task_failure_recovery() -> None:
    task = _task("task-1")

    summary = build_agent_loop_error_summary(
        summary_id="agent_loop_failed:s1:task-1:max_steps",
        task=task,
        stop_reason="max_steps",
    )

    assert summary.metadata["productCategory"] == "task_execution_failed"
    assert summary.metadata["recoveryActions"] == [
        "retry_task",
        "open_audit",
        "export_diagnostics",
    ]
    assert summary.metadata["diagnosticRefs"] == {
        "errorRef": "agent_loop_failed:s1:task-1:max_steps",
        "taskId": "task-1",
        "sessionId": "s1",
    }


def _task(task_id: str) -> TaskDomain:
    return TaskDomain(
        task_id=task_id,
        session_id="s1",
        root_id=task_id,
        intent=f"Do {task_id}",
        required_capability="general",
        created_by="test",
    )
