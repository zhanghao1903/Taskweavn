"""Tests for Main Page real-backend sidecar application assembly."""

from __future__ import annotations

import http.client
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import pytest

from taskweavn.core import SessionManager, SessionManagerError, WorkspaceLayout
from taskweavn.llm.contracts import ChatResponse
from taskweavn.server import (
    DEFAULT_PLATO_SIDECAR_PORT,
    MainPageSidecarConfig,
    MainPageSidecarDependencies,
    MainPageTaskRefResolver,
    build_main_page_sidecar_app,
)
from taskweavn.task import (
    DraftTaskNode,
    InMemoryDraftTaskStore,
    SqliteTaskBus,
    TaskDomain,
    TaskRef,
    TaskRunResult,
)


def test_main_page_sidecar_config_uses_stable_dev_port_by_default(
    tmp_path: Any,
) -> None:
    config = MainPageSidecarConfig(workspace_root=tmp_path)

    assert config.port == DEFAULT_PLATO_SIDECAR_PORT


def test_build_main_page_sidecar_app_starts_without_session_and_frontend_creates_one(
    tmp_path: Any,
) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=tmp_path,
            port=0,
        ),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        listed = _request(app, "GET", "/api/v1/sessions")
        created = _request(app, "POST", "/api/v1/sessions", body={"name": "Demo session"})
        session_id = created.json["data"]["sessionId"]
        response = _request(app, "GET", f"/api/v1/sessions/{session_id}/snapshot")
    finally:
        app.close()

    assert app.session is None
    assert listed.status == 200
    assert listed.json["data"]["sessions"] == []
    assert created.json["data"]["session"]["name"] == "Demo session"
    assert response.status == 200
    assert response.json["ok"] is True
    assert response.json["data"]["session"]["id"] == session_id
    assert response.json["data"]["session"]["status"] == "new"
    assert response.json["data"]["taskTree"] is None


def test_build_main_page_sidecar_app_reuses_existing_session(tmp_path: Any) -> None:
    layout = WorkspaceLayout(tmp_path)
    manager = SessionManager(layout)
    try:
        session = manager.create("Existing")
    finally:
        manager.close()

    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, session_id=session.id, port=0),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        assert app.session is not None
        assert app.session.id == session.id
        assert app.session.name == "Existing"
    finally:
        app.close()


def test_main_page_sidecar_app_session_lifecycle_routes(tmp_path: Any) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        first = _request(app, "POST", "/api/v1/sessions", body={"name": "First"})
        first_id = first.json["data"]["sessionId"]
        created = _request(
            app,
            "POST",
            "/api/v1/sessions",
            body={"name": "Second"},
        )
        created_id = created.json["data"]["sessionId"]
        renamed = _request(
            app,
            "PATCH",
            f"/api/v1/sessions/{created_id}",
            body={"name": "Renamed"},
        )
        deleted = _request(
            app,
            "POST",
            f"/api/v1/sessions/{created_id}/delete",
        )
        snapshot = _request(app, "GET", f"/api/v1/sessions/{first_id}/snapshot")
    finally:
        app.close()

    assert created.status == 200
    assert created.json["data"]["session"]["name"] == "Second"
    assert renamed.status == 200
    assert renamed.json["data"]["session"]["name"] == "Renamed"
    assert deleted.status == 200
    assert deleted.json["data"]["deletedSessionId"] == created_id
    assert snapshot.json["data"]["sessions"][0]["id"] == first_id


def test_build_main_page_sidecar_app_rejects_unknown_session_id(tmp_path: Any) -> None:
    with pytest.raises(SessionManagerError, match="no such session"):
        build_main_page_sidecar_app(
            MainPageSidecarConfig(workspace_root=tmp_path, session_id="missing"),
            MainPageSidecarDependencies(llm=_StubLLM()),
        )


def test_main_page_sidecar_app_routes_session_input_to_real_services(tmp_path: Any) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        session_id = _create_session(app)
        command = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/input",
            body={
                "commandId": "command-1",
                "sessionId": session_id,
                "payload": {
                    "content": "Build a quiet personal website.",
                    "mode": "global_guidance",
                },
            },
        )
        snapshot = _request(app, "GET", f"/api/v1/sessions/{session_id}/snapshot")
        raw_tasks = app.raw_task_store.list_for_session(session_id)
    finally:
        app.close()

    assert command.status == 200
    assert command.json["ok"] is True
    assert command.json["result"]["status"] == "accepted"
    assert raw_tasks[0].intent_summary == "Build a quiet website"
    assert snapshot.json["data"]["session"]["status"] == "understanding"
    assert snapshot.json["data"]["messages"][0]["body"] == (
        "Build a quiet personal website."
    )


def test_main_page_sidecar_app_generates_task_tree_from_prompt(tmp_path: Any) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(
            llm=_StubLLM(
                [
                    """
                    {
                      "intent_summary": "Build a quiet website",
                      "feasibility": {
                        "status": "ready",
                        "confidence": 0.95,
                        "suggested_next_action": "generate_task_tree"
                      },
                      "constraints": ["quiet visual style"]
                    }
                    """,
                    """
                    {
                      "assistant_message": "Drafted the first TaskTree.",
                      "roots": [
                        {
                          "title": "Plan structure",
                          "intent": "Plan the website structure.",
                          "required_capability": "general"
                        }
                      ]
                    }
                    """,
                ]
            )
        ),
    )
    try:
        session_id = _create_session(app)
        command = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/task-tree/generate",
            body={
                "commandId": "generate-1",
                "sessionId": session_id,
                "payload": {"prompt": "Build a quiet personal website."},
            },
        )
        snapshot = _request(app, "GET", f"/api/v1/sessions/{session_id}/snapshot")
    finally:
        app.close()

    assert command.status == 200
    assert command.json["ok"] is True
    assert snapshot.json["data"]["taskTree"]["nodes"][0]["title"] == "Plan structure"
    assert snapshot.json["data"]["taskTree"]["nodes"][0]["taskRef"]["kind"] == "draft"


def test_main_page_sidecar_app_recovers_draft_tree_after_restart_and_publishes(
    tmp_path: Any,
) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(
            llm=_StubLLM(
                [
                    """
                    {
                      "intent_summary": "Build a quiet website",
                      "feasibility": {
                        "status": "ready",
                        "confidence": 0.95,
                        "suggested_next_action": "generate_task_tree"
                      },
                      "constraints": ["quiet visual style"]
                    }
                    """,
                    """
                    {
                      "assistant_message": "Drafted the first TaskTree.",
                      "roots": [
                        {
                          "title": "Plan structure",
                          "intent": "Plan the website structure.",
                          "required_capability": "general"
                        }
                      ]
                    }
                    """,
                ]
            )
        ),
    )
    try:
        session_id = _create_session(app)
        generate = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/task-tree/generate",
            body={
                "commandId": "generate-restart",
                "sessionId": session_id,
                "idempotencyKey": "generate-restart-key",
                "payload": {"prompt": "Build a quiet personal website."},
            },
        )
        first_snapshot = _request(app, "GET", f"/api/v1/sessions/{session_id}/snapshot")
        assert app.authoring_state_store is not None
        active_before_restart = app.authoring_state_store.get_active(session_id)
    finally:
        app.close()

    replay_llm = _StubLLM(
        [
            """
            {
              "intent_summary": "Build a different quiet website",
              "feasibility": {
                "status": "ready",
                "confidence": 0.95,
                "suggested_next_action": "generate_task_tree"
              }
            }
            """,
            """
            {
              "assistant_message": "Drafted a different TaskTree.",
              "roots": [
                {
                  "title": "Different plan",
                  "intent": "This should be replayed away.",
                  "required_capability": "general"
                }
              ]
            }
            """,
        ]
    )
    restarted = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(llm=replay_llm),
    )
    try:
        duplicate_generate = _request(
            restarted,
            "POST",
            f"/api/v1/sessions/{session_id}/task-tree/generate",
            body={
                "commandId": "generate-restart",
                "sessionId": session_id,
                "idempotencyKey": "generate-restart-key",
                "payload": {"prompt": "Build a quiet personal website."},
            },
        )
        recovered_snapshot = _request(
            restarted,
            "GET",
            f"/api/v1/sessions/{session_id}/snapshot",
        )
        publish = _request(
            restarted,
            "POST",
            f"/api/v1/sessions/{session_id}/task-tree/publish",
            body={
                "commandId": "publish-recovered",
                "sessionId": session_id,
                "idempotencyKey": "publish-recovered-key",
                "payload": {"startImmediately": False},
            },
        )
        assert restarted.authoring_state_store is not None
        active_after_publish = restarted.authoring_state_store.get_active(session_id)
        published_tasks = restarted.task_bus.list_for_session(session_id)
    finally:
        restarted.close()

    replayed = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        duplicate_publish = _request(
            replayed,
            "POST",
            f"/api/v1/sessions/{session_id}/task-tree/publish",
            body={
                "commandId": "publish-recovered",
                "sessionId": session_id,
                "idempotencyKey": "publish-recovered-key",
                "payload": {"startImmediately": False},
            },
        )
        replayed_tasks = replayed.task_bus.list_for_session(session_id)
    finally:
        replayed.close()

    assert generate.status == 200
    assert generate.json["ok"] is True
    assert active_before_restart.active_state == "draft_tree"
    assert active_before_restart.active_draft_tree_id is not None
    assert WorkspaceLayout(tmp_path).workspace_authoring_db.is_file()
    assert first_snapshot.json["data"]["taskTree"]["id"] == (
        active_before_restart.active_draft_tree_id
    )
    assert recovered_snapshot.status == 200
    assert recovered_snapshot.json["ok"] is True
    assert recovered_snapshot.json["data"]["taskTree"]["id"] == (
        active_before_restart.active_draft_tree_id
    )
    assert duplicate_generate.status == 200
    assert duplicate_generate.json["ok"] is True
    assert duplicate_generate.json == generate.json
    assert replay_llm.calls == 0
    assert recovered_snapshot.json["data"]["taskTree"]["nodes"][0]["title"] == (
        "Plan structure"
    )
    assert publish.status == 200
    assert publish.json["ok"] is True
    assert {"kind": "draft_tree", "id": active_before_restart.active_draft_tree_id} in (
        publish.json["result"]["objectRefs"]
    )
    assert publish.json["result"]["publishedTaskIds"]
    assert active_after_publish.active_state == "published"
    assert len(published_tasks) == 1
    assert duplicate_publish.status == 200
    assert duplicate_publish.json["ok"] is True
    assert duplicate_publish.json["result"]["publishedTaskIds"] == (
        publish.json["result"]["publishedTaskIds"]
    )
    assert len(replayed_tasks) == 1


def test_main_page_sidecar_app_runs_fixed_route_tick_after_publish(
    tmp_path: Any,
) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(
            llm=_StubLLM(
                [
                    """
                    {
                      "intent_summary": "Build a quiet website",
                      "feasibility": {
                        "status": "ready",
                        "confidence": 0.95,
                        "suggested_next_action": "generate_task_tree"
                      }
                    }
                    """,
                    """
                    {
                      "assistant_message": "Drafted the first TaskTree.",
                      "roots": [
                        {
                          "title": "Plan structure",
                          "intent": "Plan the website structure.",
                          "required_capability": "general"
                        }
                      ]
                    }
                    """,
                ]
            ),
            default_agent=_FakeDefaultAgent(TaskRunResult(result_ref="result:plan")),
        ),
    )
    try:
        session_id = _create_session(app)
        generate = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/task-tree/generate",
            body={
                "commandId": "generate-executable",
                "sessionId": session_id,
                "payload": {"prompt": "Build a quiet personal website."},
            },
        )
        publish = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/task-tree/publish",
            body={
                "commandId": "publish-executable",
                "sessionId": session_id,
                "payload": {"startImmediately": False},
            },
        )
        pending_tasks = app.task_bus.list_for_session(session_id)
        tick = app.run_fixed_route_tick(session_id)
        done_tasks = app.task_bus.list_for_session(session_id)
        snapshot = _request(app, "GET", f"/api/v1/sessions/{session_id}/snapshot")
    finally:
        app.close()

    assert generate.status == 200
    assert publish.status == 200
    assert [task.status for task in pending_tasks] == ["pending"]
    assert tick.status == "completed"
    assert tick.completed_task_id == pending_tasks[0].task_id
    assert tick.result_ref == "result:plan"
    assert done_tasks[0].status == "done"
    assert done_tasks[0].claimed_by == "default_agent"
    assert done_tasks[0].result_ref == "result:plan"
    snapshot_node = snapshot.json["data"]["taskTree"]["nodes"][0]
    assert snapshot_node["status"] == "done"
    assert snapshot_node["execution"] == "done"
    assert snapshot_node["resultRef"] == "result:plan"
    assert snapshot_node["errorRef"] is None


def test_main_page_sidecar_app_publish_start_immediately_dispatches_background_execution(
    tmp_path: Any,
) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(
            llm=_StubLLM(
                [
                    """
                    {
                      "intent_summary": "Build a quiet website",
                      "feasibility": {
                        "status": "ready",
                        "confidence": 0.95,
                        "suggested_next_action": "generate_task_tree"
                      }
                    }
                    """,
                    """
                    {
                      "assistant_message": "Drafted the first TaskTree.",
                      "roots": [
                        {
                          "title": "Plan structure",
                          "intent": "Plan the website structure.",
                          "required_capability": "general"
                        }
                      ]
                    }
                    """,
                ]
            ),
            default_agent=_FakeDefaultAgent(TaskRunResult(result_ref="result:plan")),
        ),
    )
    try:
        session_id = _create_session(app)
        generate = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/task-tree/generate",
            body={
                "commandId": "generate-auto-executable",
                "sessionId": session_id,
                "payload": {"prompt": "Build a quiet personal website."},
            },
        )
        publish = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/task-tree/publish",
            body={
                "commandId": "publish-auto-executable",
                "sessionId": session_id,
                "payload": {},
            },
        )
        assert _wait_for(lambda: _first_task_status(app, session_id) == "done")
        snapshot = _request(app, "GET", f"/api/v1/sessions/{session_id}/snapshot")
    finally:
        app.close()

    assert generate.status == 200
    assert publish.status == 200
    assert publish.json["ok"] is True
    assert publish.json["result"]["debugRefs"]["dispatchStatus"] == "queued"
    snapshot_node = snapshot.json["data"]["taskTree"]["nodes"][0]
    assert snapshot_node["execution"] == "done"
    assert snapshot_node["resultRef"] == "result:plan"


def test_main_page_sidecar_app_fixed_route_tick_failure_path(tmp_path: Any) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(
            llm=_StubLLM(),
            default_agent=_FakeDefaultAgent(TaskRunResult(error_ref="agent:error")),
        ),
    )
    try:
        session_id = _create_session(app)
        app.task_bus.publish(_published_task("failing-task", session_id=session_id))

        tick = app.run_fixed_route_tick(session_id)
        task = app.task_bus.get(session_id, "failing-task")
        snapshot = _request(app, "GET", f"/api/v1/sessions/{session_id}/snapshot")
    finally:
        app.close()

    assert tick.status == "failed"
    assert tick.failed_task_id == "failing-task"
    assert tick.error_ref == "agent:error"
    assert task is not None
    assert task.status == "failed"
    assert task.error_ref == "agent:error"
    snapshot_node = snapshot.json["data"]["taskTree"]["nodes"][0]
    assert snapshot_node["status"] == "failed"
    assert snapshot_node["execution"] == "failed"
    assert snapshot_node["resultRef"] is None
    assert snapshot_node["errorRef"] == "agent:error"


def test_main_page_sidecar_app_fixed_route_tick_runs_agent_loop_default_agent(
    tmp_path: Any,
) -> None:
    llm = _AgentLoopLLM("Loop completed.")
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(llm=llm),
    )
    try:
        session_id = _create_session(app)
        app.task_bus.publish(_published_task("loop-task", session_id=session_id))

        tick = app.run_fixed_route_tick(session_id)
        task = app.task_bus.get(session_id, "loop-task")
        events_db = WorkspaceLayout(tmp_path).session_events_db(session_id)
    finally:
        app.close()

    assert tick.status == "completed"
    assert tick.result_ref == f"agent_loop:{session_id}:loop-task:no_tool_calls"
    assert task is not None
    assert task.status == "done"
    assert task.result_ref == f"agent_loop:{session_id}:loop-task:no_tool_calls"
    assert llm.calls[0]["messages"][1]["content"] == "Run loop-task"
    assert events_db.exists()


def test_main_page_sidecar_app_fixed_route_tick_reports_missing_default_agent(
    tmp_path: Any,
) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=tmp_path,
            port=0,
            enable_default_agent=False,
        ),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        session_id = _create_session(app)
        app.task_bus.publish(_published_task("waiting-task", session_id=session_id))

        tick = app.run_fixed_route_tick(session_id)
        task = app.task_bus.get(session_id, "waiting-task")
    finally:
        app.close()

    assert tick.status == "health_error"
    assert tick.error_ref == "default_agent_unavailable"
    assert task is not None
    assert task.status == "pending"
    assert task.claimed_by is None


def test_main_page_sidecar_app_writes_frontend_error_log_file(tmp_path: Any) -> None:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(workspace_root=tmp_path, port=0),
        MainPageSidecarDependencies(llm=_StubLLM()),
    )
    try:
        session_id = _create_session(app)
        response = _request(
            app,
            "POST",
            f"/api/v1/sessions/{session_id}/client-logs/errors",
            body={
                "entry": {
                    "createdAt": "2026-05-22T00:00:00.000Z",
                    "level": "error",
                    "message": "render.failed",
                    "namespace": "app-error-boundary",
                }
            },
        )
        log_path = (
            WorkspaceLayout(tmp_path).session_logs_dir(session_id)
            / "frontend-errors.jsonl"
        )
        rows = [json.loads(line) for line in log_path.read_text().splitlines()]
    finally:
        app.close()

    assert response.status == 200
    assert response.json["ok"] is True
    assert rows[0]["sessionId"] == session_id
    assert rows[0]["payload"]["entry"]["message"] == "render.failed"


def test_main_page_task_ref_resolver_prefers_draft_then_published(tmp_path: Any) -> None:
    draft_store = InMemoryDraftTaskStore()
    tree = draft_store.create_tree(
        "session-1",
        [
            DraftTaskNode(
                session_id="session-1",
                draft_tree_id="placeholder",
                title="Draft",
                intent="Draft task",
                required_capability="general",
            )
        ],
    )
    draft_id = tree.root_nodes[0].draft_task_id
    task_bus = SqliteTaskBus(tmp_path / "tasks.sqlite")
    try:
        resolver = MainPageTaskRefResolver(draft_store=draft_store, task_bus=task_bus)

        assert resolver.resolve("session-1", draft_id) == TaskRef.draft(draft_id)
        with pytest.raises(LookupError, match="not found"):
            resolver.resolve("session-1", "missing")
    finally:
        task_bus.close()


@dataclass(frozen=True)
class _HttpResult:
    status: int
    text: str

    @property
    def json(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.text))


class _StubLLM:
    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self.calls = 0

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> _LLMResponse:
        self.calls += 1
        if self._responses:
            return _LLMResponse(self._responses.pop(0))
        return _LLMResponse(
            """
            {
              "intent_summary": "Build a quiet website",
              "feasibility": {
                "status": "ready",
                "confidence": 0.95,
                "suggested_next_action": "generate_task_tree"
              },
              "constraints": ["quiet visual style"]
            }
            """
        )


class _AgentLoopLLM:
    def __init__(self, final_answer: str) -> None:
        self.final_answer = final_answer
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        self.calls.append(
            {
                "messages": list(messages),
                "tools": tools,
                "metadata": metadata,
            }
        )
        return ChatResponse(
            content=self.final_answer,
            tool_calls=[],
            raw_assistant_message={
                "role": "assistant",
                "content": self.final_answer,
            },
        )


@dataclass
class _FakeDefaultAgent:
    result: TaskRunResult
    seen: list[str] | None = None

    def run(self, task: TaskDomain) -> TaskRunResult:
        if self.seen is None:
            self.seen = []
        self.seen.append(task.task_id)
        return self.result


@dataclass(frozen=True)
class _LLMResponse:
    content: str


def _request(
    app: Any,
    method: str,
    path: str,
    *,
    body: dict[str, object] | None = None,
) -> _HttpResult:
    app.start_in_thread()
    raw_body = None if body is None else json.dumps(body).encode("utf-8")
    headers = {} if raw_body is None else {"content-type": "application/json"}
    host, port = app.server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request(method, path, body=raw_body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        return _HttpResult(status=response.status, text=raw.decode("utf-8"))
    finally:
        conn.close()


def _create_session(app: Any, name: str = "Demo session") -> str:
    response = _request(app, "POST", "/api/v1/sessions", body={"name": name})
    return cast(str, response.json["data"]["sessionId"])


def _published_task(task_id: str, *, session_id: str) -> TaskDomain:
    return TaskDomain(
        task_id=task_id,
        session_id=session_id,
        root_id=task_id,
        intent=f"Run {task_id}",
        required_capability="general",
        created_by="test",
    )


def _wait_for(predicate: Callable[[], bool], *, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def _first_task_status(app: Any, session_id: str) -> str | None:
    tasks = app.task_bus.list_for_session(session_id)
    return None if not tasks else tasks[0].status
