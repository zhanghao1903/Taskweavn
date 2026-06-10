from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from taskweavn.core import SessionManager, WorkspaceLayout
from taskweavn.diagnostics import DiagnosticBundleExporter, DiagnosticExportOptions
from taskweavn.llm.contracts import ChatResponse, LLMUsage
from taskweavn.server.transport import HttpApiRequest
from taskweavn.server.ui_http import PlatoUiHttpTransport
from taskweavn.server.ui_http_usage import DefaultTokenUsageSummaryGateway
from taskweavn.usage import (
    SqliteTokenUsageStore,
    TokenUsageEvent,
    TokenUsageFilter,
    UsageRecordingLLM,
    normalize_usage_event,
)


def test_normalize_usage_event_redacts_provider_request_id_and_metadata() -> None:
    response = ChatResponse(
        content="done",
        tool_calls=[],
        raw_assistant_message={"role": "assistant", "content": "done"},
        provider_name="deepseek",
        provider_request_id="provider-request-secret",
        usage=LLMUsage(
            input_tokens=100,
            output_tokens=25,
            total_tokens=125,
            reasoning_tokens=5,
            cached_tokens=80,
            cache_hit_tokens=80,
            cache_miss_tokens=20,
        ),
    )

    event = normalize_usage_event(
        response,
        workspace_id="workspace-a",
        metadata={
            "session_id": "session-a",
            "task_id": "task-a",
            "agent_run_id": "run-a",
            "request_purpose": "execution.agent_loop.step",
            "prompt": "raw prompt should not be stored",
            "workspace_path": "/tmp/secret-workspace",
            "context_render_mode": "stable_prefix",
        },
        model="deepseek-v4-pro",
        task_plan_resolver=lambda _session_id, _task_id: "plan-a",
    )

    assert event.workspace_id == "workspace-a"
    assert event.session_id == "session-a"
    assert event.task_node_id == "task-a"
    assert event.plan_id == "plan-a"
    assert event.provider_request_id_hash
    assert event.provider_request_id_hash != "provider-request-secret"
    assert event.usage_source == "provider_reported"
    assert event.cache_rate_source == "hit_miss_tokens"
    assert event.cache_hit_ratio == 0.8
    assert event.metadata == {"context_render_mode": "stable_prefix"}
    assert "raw prompt" not in event.model_dump_json()
    assert "/tmp/secret-workspace" not in event.model_dump_json()


def test_usage_recording_llm_records_response_without_changing_result(
    tmp_path: Path,
) -> None:
    store = SqliteTokenUsageStore(tmp_path / "usage.sqlite")
    response = _chat_response(
        input_tokens=20,
        output_tokens=5,
        total_tokens=25,
    )
    llm = UsageRecordingLLM(
        _StubLLM(response),
        workspace_id="workspace-a",
        sink=store,
        task_plan_resolver=lambda _session_id, _task_id: "plan-a",
    )

    returned = llm.chat(
        messages=[{"role": "user", "content": "hello"}],
        metadata={
            "session_id": "session-a",
            "task_id": "task-a",
            "request_purpose": "test",
        },
    )
    events = store.list_events(TokenUsageFilter(workspace_id="workspace-a"))

    assert returned is response
    assert len(events) == 1
    assert events[0].session_id == "session-a"
    assert events[0].task_node_id == "task-a"
    assert events[0].plan_id == "plan-a"


def test_usage_store_aggregates_by_task_plan_session_and_workspace(
    tmp_path: Path,
) -> None:
    store = SqliteTokenUsageStore(tmp_path / "usage.sqlite")
    for event in (
        _event(
            "e1",
            session_id="session-a",
            plan_id="plan-a",
            task_node_id="task-a",
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
            cache_hit_tokens=80,
            cache_miss_tokens=20,
        ),
        _event(
            "e2",
            session_id="session-a",
            plan_id="plan-a",
            task_node_id="task-b",
            input_tokens=50,
            output_tokens=10,
            total_tokens=60,
            cache_hit_tokens=25,
            cache_miss_tokens=None,
        ),
        _event(
            "e3",
            session_id="session-a",
            usage_source="unavailable",
        ),
        _event(
            "e4",
            session_id="session-b",
            plan_id="plan-b",
            task_node_id="task-c",
            input_tokens=5,
            output_tokens=2,
            total_tokens=7,
        ),
    ):
        store.put(event)

    task_summary = store.summarize(
        dimension="task",
        filters=TokenUsageFilter(workspace_id="workspace-a", session_id="session-a"),
    )
    plan_summary = store.summarize(
        dimension="plan",
        filters=TokenUsageFilter(workspace_id="workspace-a", session_id="session-a"),
    )
    session_summary = store.summarize(
        dimension="session",
        filters=TokenUsageFilter(workspace_id="workspace-a"),
    )
    workspace_summary = store.summarize(
        dimension="workspace",
        filters=TokenUsageFilter(workspace_id="workspace-a"),
    )

    assert task_summary.totals.call_count == 3
    assert task_summary.totals.unknown_usage_call_count == 1
    assert {row.id for row in task_summary.rows} == {"task-a", "task-b"}
    assert task_summary.totals.total_tokens == 180
    assert plan_summary.rows[0].id == "plan-a"
    assert plan_summary.rows[0].cache_rate_source == "input_tokens"
    assert plan_summary.rows[0].cache_hit_ratio == 0.7
    assert {row.id for row in session_summary.rows} == {"session-a", "session-b"}
    assert workspace_summary.rows[0].id == "workspace-a"
    assert workspace_summary.totals.total_tokens == 187


def test_usage_summary_http_endpoint_returns_contract_shape(tmp_path: Path) -> None:
    store = SqliteTokenUsageStore(tmp_path / "usage.sqlite")
    store.put(
        _event(
            "e1",
            session_id="session-a",
            plan_id="plan-a",
            task_node_id="task-a",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )
    )
    transport = PlatoUiHttpTransport(
        query_gateway=cast(Any, object()),
        command_gateway=cast(Any, object()),
        token_usage_gateway=DefaultTokenUsageSummaryGateway(
            store=store,
            workspace_id="workspace-a",
        ),
    )

    response = transport.handle(
        HttpApiRequest(
            method="GET",
            path="/api/v1/usage/token-summary?dimension=task&sessionId=session-a",
        )
    )

    assert response.status_code == 200
    assert response.body["ok"] is True
    assert response.body["data"]["dimension"] == "task"
    assert response.body["data"]["totals"]["totalTokens"] == 15
    assert response.body["data"]["rows"][0]["taskNodeId"] == "task-a"


def test_diagnostic_bundle_includes_redacted_token_usage_summary(tmp_path: Path) -> None:
    layout = WorkspaceLayout(tmp_path)
    with SessionManager(layout) as manager:
        session = manager.create("Diagnostics")
    store = SqliteTokenUsageStore(layout.workspace_usage_db)
    store.put(
        _event(
            "e1",
            session_id=session.id,
            plan_id="plan-a",
            task_node_id="task-a",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )
    )
    store.close()

    result = DiagnosticBundleExporter(
        DiagnosticExportOptions(
            workspace_root=tmp_path,
            session_id=session.id,
            output_dir=tmp_path / "diagnostics",
            create_zip=False,
        )
    ).export()

    usage_summary = json.loads(
        (result.bundle_dir / "usage" / "token-summary.json").read_text(
            encoding="utf-8"
        )
    )
    bundle_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in result.bundle_dir.rglob("*")
        if path.is_file()
    )
    assert usage_summary["schemaVersion"] == (
        "plato.token_usage.diagnostic_summary.v1"
    )
    assert usage_summary["totals"]["totalTokens"] == 15
    assert str(tmp_path) not in bundle_text
    assert "provider-request-secret" not in bundle_text


class _StubLLM:
    model = "deepseek-v4-pro"

    def __init__(self, response: ChatResponse) -> None:
        self.response = response

    def chat(self, *args: Any, **kwargs: Any) -> ChatResponse:
        return self.response


def _chat_response(
    *,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
) -> ChatResponse:
    return ChatResponse(
        content="ok",
        tool_calls=[],
        raw_assistant_message={"role": "assistant", "content": "ok"},
        provider_name="deepseek",
        provider_request_id="provider-request-secret",
        usage=LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        ),
    )


def _event(
    event_id: str,
    *,
    session_id: str | None = None,
    plan_id: str | None = None,
    task_node_id: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    cache_hit_tokens: int | None = None,
    cache_miss_tokens: int | None = None,
    usage_source: str = "provider_reported",
) -> TokenUsageEvent:
    return TokenUsageEvent(
        usage_event_id=event_id,
        occurred_at=f"2026-06-10T00:00:0{event_id[-1]}Z",
        workspace_id="workspace-a",
        session_id=session_id,
        plan_id=plan_id,
        task_node_id=task_node_id,
        request_purpose="test",
        provider="deepseek",
        model="deepseek-v4-pro",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cache_hit_tokens=cache_hit_tokens,
        cache_miss_tokens=cache_miss_tokens,
        cache_hit_ratio=None,
        usage_source=usage_source,  # type: ignore[arg-type]
        cache_rate_source="unavailable",
    )
