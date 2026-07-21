"""Product-path evidence for app-control permission failure projection."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from taskweavn.llm.contracts import ChatResponse
from taskweavn.server import (
    MainPageSidecarConfig,
    MainPageSidecarDependencies,
    build_main_page_sidecar_app,
)
from taskweavn.task import (
    InMemoryTaskExecutionSummaryStore,
    TaskDomain,
    TaskExecutionSummary,
    TaskRunResult,
)
from taskweavn.tools import ScriptedComputerUseBackend
from tests.fixtures.sidecar_smoke import request_sidecar


def test_missing_accessibility_reaches_conversation_without_desktop_action(
    tmp_path: Path,
) -> None:
    summaries = InMemoryTaskExecutionSummaryStore()
    backend = ScriptedComputerUseBackend()
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=tmp_path,
            port=0,
            enable_computer_use_tool=True,
            computer_use_backend_name="helper",
        ),
        MainPageSidecarDependencies(
            llm=_WeChatRouteLLM(),
            default_agent=_MissingAccessibilityAgent(summaries),
            result_summary_store=summaries,
            computer_use_backend=backend,
        ),
    )
    try:
        created = request_sidecar(
            app,
            "POST",
            "/api/v1/sessions",
            body={"name": "App control permission failure"},
        )
        session_id = created.json["data"]["sessionId"]
        content = '给微信的文件传输助手发送“你好”'

        routed = request_sidecar(
            app,
            "POST",
            f"/api/v1/workspaces/current/sessions/{session_id}/runtime-input/route",
            body={
                "commandId": "route-wechat-missing-accessibility",
                "sessionId": session_id,
                "content": content,
                "selection": {"scopeKind": "session"},
            },
        )

        assert routed.status == 200
        assert routed.json["ok"] is True
        assert routed.json["data"]["decision"]["dispatchTarget"] == (
            "execution_handoff"
        )
        assert routed.json["data"]["outcome"]["status"] == "dispatched"
        assert _wait_for_failed_task(app, session_id)

        snapshot = request_sidecar(
            app,
            "GET",
            f"/api/v1/sessions/{session_id}/snapshot",
        )
    finally:
        app.close()

    assert snapshot.status == 200
    messages = snapshot.json["data"]["messages"]
    assert any(
        message["title"] == "User input" and message["body"] == content
        for message in messages
    )
    failure = next(
        message
        for message in messages
        if message["kind"] == "error" and message["title"] == "Task failed"
    )
    assert "missing_accessibility" in failure["body"]
    assert "Plato Computer Use Helper" in failure["body"]
    assert "系统设置 > 隐私与安全性 > 辅助功能" in failure["body"]
    assert "没有发送消息" in failure["body"]
    assert backend.actions == []


@dataclass(frozen=True)
class _WeChatRouteLLM:
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        del messages, tools, metadata, kwargs
        return ChatResponse(
            content=json.dumps(
                {
                    "intent": "execution_request",
                    "dispatchTarget": "execution_handoff",
                    "scopeKind": "session",
                    "sideEffect": "state_effect",
                    "confidence": "high",
                    "visibleReasoningSummary": "Create one WeChat send task.",
                    "userMessage": "I will create a WeChat send task.",
                    "activatedSkillIds": ["internal:router-wechat-send"],
                    "taskRequestDraft": {
                        "taskType": "communication.wechat.send_message",
                        "instructions": "Send one WeChat message.",
                        "input": {
                            "contactDisplayName": "文件传输助手",
                            "messageText": "你好",
                        },
                        "policy": {
                            "requiredCapability": (
                                "communication.wechat_desktop_send"
                            ),
                            "requiresHumanConfirmation": True,
                            "riskLevel": "high",
                        },
                    },
                },
                ensure_ascii=False,
            ),
            tool_calls=[],
            raw_assistant_message={"role": "assistant", "content": "json"},
        )


@dataclass(frozen=True)
class _MissingAccessibilityAgent:
    summaries: InMemoryTaskExecutionSummaryStore

    def run(self, task: TaskDomain) -> TaskRunResult:
        error_ref = f"app-control:missing-accessibility:{task.task_id}"
        self.summaries.put(
            TaskExecutionSummary(
                summary_id=error_ref,
                session_id=task.session_id,
                task_id=task.task_id,
                kind="error",
                source="execution_bridge",
                title="Computer Use permission required",
                summary=(
                    "没有发送消息。missing_accessibility: "
                    "Plato Computer Use Helper 尚未获得辅助功能权限。"
                    "请在系统设置 > 隐私与安全性 > 辅助功能中授权后重试。"
                ),
                error_type="missing_accessibility",
                error_message="Plato Computer Use Helper lacks Accessibility permission.",
                metadata={
                    "failureKind": "missing_accessibility",
                    "recoveryHint": (
                        "Grant Accessibility to Plato Computer Use Helper."
                    ),
                    "sendAttempted": False,
                },
            )
        )
        return TaskRunResult(error_ref=error_ref)


def _wait_for_failed_task(app: Any, session_id: str) -> bool:
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        tasks = app.task_bus.list_for_session(session_id)
        if tasks and tasks[-1].status == "failed":
            return True
        time.sleep(0.01)
    return False
