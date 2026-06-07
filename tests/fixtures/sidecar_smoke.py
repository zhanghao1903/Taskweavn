"""Repeatable sidecar fixture for Audit-to-Diagnostics integration smoke tests."""

from __future__ import annotations

import argparse
import http.client
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

from taskweavn.core import SqliteEventStream
from taskweavn.server import (
    MainPageSidecarApp,
    MainPageSidecarConfig,
    MainPageSidecarDependencies,
    build_main_page_sidecar_app,
)
from taskweavn.server.settings_config import DefaultSettingsConfigGateway
from taskweavn.task import TaskDomain, TaskExecutionSummary
from taskweavn.tools.fs import FileWriteObservation

SMOKE_TASK_ID = "diagnostic-export-task"
SMOKE_ERROR_REF = "provider:rate_limit"
SMOKE_FRONTEND_ERROR_MESSAGE = "diagnostics.route.render.failed"
SMOKE_LOG_RECORD_ID = "record-log-frontend-errors.jsonl"
FIRST_RUN_CONFIGURED_ENV = {
    "LLM_PROVIDER": "litellm",
    "LLM_MODEL": "anthropic/test-model",
    "LLM_API_KEY": "test-sidecar-readiness-key",
}


@dataclass(frozen=True)
class SidecarSmokeHttpResult:
    status: int
    text: str

    @property
    def json(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.text))


@dataclass
class SidecarSmokeFixture:
    """A seeded sidecar app with real Audit data and session logs."""

    app: MainPageSidecarApp
    session_id: str
    task_id: str
    log_record_id: str
    diagnostics_log_href: str

    @property
    def base_url(self) -> str:
        return self.app.base_url

    @property
    def diagnostic_export_path(self) -> str:
        return f"/api/v1/sessions/{quote(self.session_id, safe='')}/diagnostics/export"

    @property
    def diagnostic_export_url(self) -> str:
        return f"{self.base_url}{self.diagnostic_export_path}"

    @property
    def diagnostics_log_url(self) -> str:
        return f"{self.base_url}{self.diagnostics_log_href}"

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
    ) -> SidecarSmokeHttpResult:
        return request_sidecar(self.app, method, path, body=body)

    def close(self) -> None:
        self.app.close()


def build_audit_sidecar_smoke_fixture(
    workspace_root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    settings_readiness_env: Mapping[str, str] | None = None,
) -> SidecarSmokeFixture:
    """Create a deterministic real-sidecar session for frontend integration checks."""

    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=workspace_root,
            host=host,
            port=port,
            enable_default_agent=False,
            enable_execution_dispatcher=False,
        ),
        MainPageSidecarDependencies(
            llm=_StubLLM(),
            settings_config_gateway=(
                None
                if settings_readiness_env is None
                else DefaultSettingsConfigGateway(
                    workspace_root=workspace_root,
                    env=settings_readiness_env,
                )
            ),
        ),
    )
    try:
        session_id = _create_session(app)
        task = _published_task(SMOKE_TASK_ID, session_id=session_id)
        app.task_bus.publish(task)
        claimed = app.task_bus.claim_next(
            session_id,
            capability="general",
            agent_id="smoke-agent",
        )
        if claimed is None:
            raise AssertionError("sidecar smoke task was not claimable")
        _seed_result_and_file_evidence(app, session_id, task)
        app.task_bus.fail(session_id, SMOKE_TASK_ID, error_ref=SMOKE_ERROR_REF)
        _write_frontend_error_log(app, session_id)
        diagnostics_log_href = _require_related_log_href(app, session_id)
        return SidecarSmokeFixture(
            app=app,
            session_id=session_id,
            task_id=SMOKE_TASK_ID,
            log_record_id=SMOKE_LOG_RECORD_ID,
            diagnostics_log_href=diagnostics_log_href,
        )
    except Exception:
        app.close()
        raise


def request_sidecar(
    app: MainPageSidecarApp,
    method: str,
    path: str,
    *,
    body: dict[str, object] | None = None,
) -> SidecarSmokeHttpResult:
    app.start_in_thread()
    raw_body = None if body is None else json.dumps(body).encode("utf-8")
    headers = {} if raw_body is None else {"content-type": "application/json"}
    host, port = app.server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request(method, path, body=raw_body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        return SidecarSmokeHttpResult(
            status=response.status,
            text=raw.decode("utf-8"),
        )
    finally:
        conn.close()


def _create_session(app: MainPageSidecarApp, name: str = "Diagnostics smoke") -> str:
    response = request_sidecar(app, "POST", "/api/v1/sessions", body={"name": name})
    if response.status != 200:
        raise AssertionError(f"session creation failed: {response.text}")
    return cast(str, response.json["data"]["sessionId"])


def _seed_result_and_file_evidence(
    app: MainPageSidecarApp,
    session_id: str,
    task: TaskDomain,
) -> None:
    app.result_summary_store.put(
        TaskExecutionSummary(
            summary_id=SMOKE_ERROR_REF,
            session_id=session_id,
            task_id=task.task_id,
            kind="error",
            source="execution_bridge",
            title="Task execution failed",
            summary="Provider rate limit prevented task completion.",
            error_type="provider_rate_limit",
            error_message="Provider rate limit prevented task completion.",
            metadata={
                "requiredCapability": task.required_capability,
                "smokeFixture": "audit_result_file_evidence",
            },
        )
    )
    with SqliteEventStream(app.layout.session_events_db(session_id)) as stream:
        stream.append(
            FileWriteObservation(
                event_id="file-write-observation-1",
                action_id="file-write-action-1",
                path="diagnostics-summary.md",
                bytes_written=42,
                created=True,
            ),
            task_id=task.task_id,
        )


def _write_frontend_error_log(app: MainPageSidecarApp, session_id: str) -> None:
    response = request_sidecar(
        app,
        "POST",
        f"/api/v1/sessions/{quote(session_id, safe='')}/client-logs/errors",
        body={
            "entry": {
                "createdAt": "2026-06-05T12:00:00.000Z",
                "level": "error",
                "message": SMOKE_FRONTEND_ERROR_MESSAGE,
                "namespace": "diagnostics-route",
            }
        },
    )
    if response.status != 200:
        raise AssertionError(f"frontend error log write failed: {response.text}")


def _require_related_log_href(app: MainPageSidecarApp, session_id: str) -> str:
    response = request_sidecar(
        app,
        "GET",
        (
            f"/api/v1/sessions/{quote(session_id, safe='')}/audit/records/"
            f"{quote(SMOKE_LOG_RECORD_ID, safe='')}?includeEvidence=true"
        ),
    )
    if response.status != 200:
        raise AssertionError(f"audit record lookup failed: {response.text}")
    links = response.json["data"]["relatedLogs"]
    if not links:
        raise AssertionError("audit record did not expose related diagnostics logs")
    href = links[0]["href"]
    if not links[0]["enabled"]:
        raise AssertionError(f"related diagnostics link disabled: {links[0]}")
    return cast(str, href)


def _published_task(task_id: str, *, session_id: str) -> TaskDomain:
    return TaskDomain(
        task_id=task_id,
        session_id=session_id,
        root_id=task_id,
        intent=f"Run {task_id}",
        required_capability="general",
        created_by="sidecar-smoke",
    )


class _StubLLM:
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> _LLMResponse:
        return _LLMResponse(
            """
            {
              "intent_summary": "Diagnostics smoke",
              "feasibility": {
                "status": "ready",
                "confidence": 0.95,
                "suggested_next_action": "generate_task_tree"
              },
              "constraints": []
            }
            """
        )


@dataclass(frozen=True)
class _LLMResponse:
    content: str


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start a seeded Plato sidecar for Audit/Diagnostics smoke checks.",
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        help="Keep the seeded sidecar running until interrupted.",
    )
    parser.add_argument(
        "--ready-file",
        type=Path,
        help="Write the seeded sidecar descriptor to this JSON file.",
    )
    first_run_group = parser.add_mutually_exclusive_group()
    first_run_group.add_argument(
        "--first-run-unconfigured",
        action="store_true",
        help=(
            "Force Settings readiness to a missing local LLM configuration state "
            "for frontend first-run checks."
        ),
    )
    first_run_group.add_argument(
        "--first-run-configured",
        action="store_true",
        help=(
            "Force Settings readiness to a deterministic configured local LLM "
            "state for frontend first-run checks."
        ),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument(
        "--serve-existing",
        action="store_true",
        help="Serve an already seeded workspace without creating another session.",
    )
    args = parser.parse_args(argv)

    if args.serve_existing:
        return _serve_existing_workspace(args)

    fixture = build_audit_sidecar_smoke_fixture(
        args.workspace,
        host=args.host,
        port=args.port,
        settings_readiness_env=_settings_readiness_env_from_args(args),
    )
    try:
        ready_payload = _ready_payload(fixture)
        if args.ready_file is not None:
            args.ready_file.parent.mkdir(parents=True, exist_ok=True)
            args.ready_file.write_text(
                json.dumps(ready_payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        print(
            json.dumps(ready_payload, indent=2, sort_keys=True),
            flush=True,
        )
        if args.keep_alive:
            while True:
                time.sleep(3600)
    except KeyboardInterrupt:
        return 0
    finally:
        fixture.close()
    return 0


def _serve_existing_workspace(args: argparse.Namespace) -> int:
    app = build_main_page_sidecar_app(
        MainPageSidecarConfig(
            workspace_root=args.workspace,
            host=args.host,
            port=args.port,
            enable_default_agent=False,
            enable_execution_dispatcher=False,
        ),
        MainPageSidecarDependencies(
            llm=_StubLLM(),
            settings_config_gateway=DefaultSettingsConfigGateway(
                workspace_root=args.workspace,
                env=_settings_readiness_env_from_args(args) or {},
            ),
        ),
    )
    try:
        app.start_in_thread()
        ready_payload = {"baseUrl": app.base_url}
        if args.ready_file is not None:
            args.ready_file.parent.mkdir(parents=True, exist_ok=True)
            args.ready_file.write_text(
                json.dumps(ready_payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        print(json.dumps(ready_payload, indent=2, sort_keys=True), flush=True)
        if args.keep_alive:
            while True:
                time.sleep(3600)
    except KeyboardInterrupt:
        return 0
    finally:
        app.close()
    return 0


def _ready_payload(fixture: SidecarSmokeFixture) -> dict[str, str]:
    return {
        "baseUrl": fixture.base_url,
        "diagnosticExportUrl": fixture.diagnostic_export_url,
        "diagnosticsLogUrl": fixture.diagnostics_log_url,
        "logRecordId": fixture.log_record_id,
        "sessionId": fixture.session_id,
        "taskId": fixture.task_id,
    }


def _settings_readiness_env_from_args(
    args: argparse.Namespace,
) -> Mapping[str, str] | None:
    if args.first_run_unconfigured:
        return {}
    if args.first_run_configured:
        return FIRST_RUN_CONFIGURED_ENV
    return None


if __name__ == "__main__":
    raise SystemExit(main())
