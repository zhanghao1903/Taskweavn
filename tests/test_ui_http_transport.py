"""Tests for the framework-neutral Plato UI HTTP transport."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from taskweavn.server import (
    HttpApiRequest,
    InMemoryUiCommandResponseIdempotencyStore,
    PlatoUiHttpTransport,
    SidecarAuth,
    SqliteUiEventSource,
    StaticUiEventSource,
    UiEventSource,
)
from taskweavn.server.settings_config import (
    SettingsConfigFieldError,
    SettingsConfigValidationError,
)
from taskweavn.server.ui_contract import (
    ApiError,
    AskListResult,
    AskRequestView,
    AuditEntryContext,
    AuditOverview,
    AuditPageRequestView,
    AuditPageSnapshot,
    AuditRecord,
    AuditRecordDetail,
    AuditRecordsResult,
    AuditSessionScope,
    CommandRequest,
    CommandResponse,
    CommandResult,
    EvidenceDetail,
    EvidenceRef,
    MainPageReturnTarget,
    MainPageSnapshot,
    ProjectSummary,
    QueryResponse,
    SessionSummary,
    UiEvent,
    WorkflowSummary,
)
from taskweavn.task import ExecutionDispatchRequestResult

NOW = datetime(2026, 5, 21, 9, 0, tzinfo=UTC)


def test_root_route_returns_sidecar_api_hint() -> None:
    transport = _transport()

    response = transport.handle(HttpApiRequest(method="GET", path="/"))
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["name"] == "Plato Sidecar"
    assert body["data"]["api_base_path"] == "/api/v1"
    assert body["data"]["health_url"] == "/api/v1/health"
    assert body["data"]["settings_readiness_url"] == "/api/v1/settings/readiness"
    assert body["data"]["settings_config_url"] == "/api/v1/settings/config"
    assert body["data"]["settings_readiness_recheck_url"] == (
        "/api/v1/settings/readiness/recheck"
    )
    assert body["data"]["snapshot_url_template"] == (
        "/api/v1/sessions/{sessionId}/snapshot"
    )


def test_health_route_returns_sidecar_identity() -> None:
    transport = _transport()

    response = transport.handle(HttpApiRequest(method="GET", path="/api/v1/health"))
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"] == {"name": "Plato Sidecar", "version": "0.1.0"}


def test_settings_readiness_route_returns_gateway_payload() -> None:
    readiness = _SettingsReadinessGateway()
    transport = _transport(settings_readiness_gateway=readiness)

    response = transport.handle(
        HttpApiRequest(method="GET", path="/api/v1/settings/readiness")
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["schemaVersion"] == "plato.settings_readiness.v1"
    assert body["data"]["status"] == "ready"
    assert readiness.calls == 1


def test_settings_readiness_route_requires_gateway() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(method="GET", path="/api/v1/settings/readiness")
    )
    body = _dict_body(response.body)

    assert response.status_code == 503
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["details"]["route"] == "settings_readiness"


def test_settings_readiness_recheck_route_returns_refreshed_gateway_payload() -> None:
    settings = _SettingsConfigGateway()
    transport = _transport(settings_config_gateway=settings)

    response = transport.handle(
        HttpApiRequest(method="POST", path="/api/v1/settings/readiness/recheck")
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["schemaVersion"] == "plato.settings_readiness.v1"
    assert body["data"]["status"] == "ready"
    assert settings.recheck_calls == 1


def test_settings_config_route_returns_gateway_payload() -> None:
    settings = _SettingsConfigGateway()
    transport = _transport(settings_config_gateway=settings)

    response = transport.handle(
        HttpApiRequest(method="GET", path="/api/v1/settings/config")
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["schemaVersion"] == "plato.settings_config.v1"
    assert body["data"]["llm"]["apiKeyConfigured"] is False
    assert settings.config_calls == 1


def test_settings_config_route_patches_without_echoing_secret() -> None:
    settings = _SettingsConfigGateway()
    transport = _transport(settings_config_gateway=settings)

    response = transport.handle(
        HttpApiRequest(
            method="PATCH",
            path="/api/v1/settings/config",
            body={
                "llm": {
                    "provider": "litellm",
                    "model": "anthropic/test-model",
                    "apiKey": "sk-transport-secret",
                }
            },
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["schemaVersion"] == "plato.settings_config_update.v1"
    assert settings.update_calls == [
        {
            "llm": {
                "provider": "litellm",
                "model": "anthropic/test-model",
                "apiKey": "sk-transport-secret",
            }
        }
    ]
    assert "sk-transport-secret" not in str(body)


def test_settings_config_route_maps_validation_error_without_secret() -> None:
    settings = _SettingsConfigGateway(
        validation_error=SettingsConfigValidationError(
            (
                SettingsConfigFieldError(
                    path="llm.apiKey",
                    message="an API key is required for the selected provider",
                    env_vars=("LLM_API_KEY",),
                ),
            )
        )
    )
    transport = _transport(settings_config_gateway=settings)

    response = transport.handle(
        HttpApiRequest(
            method="PATCH",
            path="/api/v1/settings/config",
            body={
                "llm": {
                    "provider": "litellm",
                    "model": "anthropic/test-model",
                    "apiKey": "sk-validation-secret",
                }
            },
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 400
    assert body["error"]["code"] == "bad_request"
    assert body["error"]["details"]["productCategory"] == "llm_auth_or_config"
    assert body["error"]["details"]["fieldErrors"][0]["path"] == "llm.apiKey"
    assert "sk-validation-secret" not in str(body)


def test_settings_config_route_requires_gateway() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(method="GET", path="/api/v1/settings/config")
    )
    body = _dict_body(response.body)

    assert response.status_code == 503
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["details"]["route"] == "settings_config"


def test_diagnostics_export_route_returns_bundle_descriptor() -> None:
    diagnostics = _DiagnosticExportGateway()
    transport = _transport(diagnostic_export_gateway=diagnostics)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/diagnostics/export",
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["schemaVersion"] == "plato.diagnostics_export.v1"
    assert body["data"]["bundleId"] == "diagnostic-bundle-session 1"
    assert diagnostics.calls == ["session 1"]


def test_diagnostics_export_route_requires_gateway() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(method="POST", path="/api/v1/sessions/session-1/diagnostics/export")
    )
    body = _dict_body(response.body)

    assert response.status_code == 503
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["details"]["route"] == "diagnostics_export"


def test_snapshot_route_decodes_session_and_returns_contract_json() -> None:
    query = _QueryGateway()
    transport = _transport(query=query)

    response = transport.handle(
        HttpApiRequest(method="GET", path="/api/v1/sessions/session%201/snapshot")
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert query.snapshot_calls == ["session 1"]
    assert body["ok"] is True
    assert body["data"]["session"]["id"] == "session 1"
    assert body["data"]["generatedAt"] == "2026-05-21T09:00:00Z"


def test_snapshot_route_runs_best_effort_recovery_before_projection() -> None:
    query = _QueryGateway()
    recovery = _SnapshotRecoveryGateway()
    transport = _transport(query=query, snapshot_recovery_gateway=recovery)

    response = transport.handle(
        HttpApiRequest(method="GET", path="/api/v1/sessions/session%201/snapshot")
    )

    assert response.status_code == 200
    assert recovery.calls == ["session 1"]
    assert query.snapshot_calls == ["session 1"]


def test_snapshot_route_continues_when_recovery_fails() -> None:
    query = _QueryGateway()
    recovery = _SnapshotRecoveryGateway(raises=RuntimeError("recovery failed"))
    transport = _transport(query=query, snapshot_recovery_gateway=recovery)

    response = transport.handle(
        HttpApiRequest(method="GET", path="/api/v1/sessions/session%201/snapshot")
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert recovery.calls == ["session 1"]
    assert query.snapshot_calls == ["session 1"]
    assert body["ok"] is True


def test_audit_routes_decode_params_and_return_contract_json() -> None:
    query = _QueryGateway()
    transport = _transport(query=query)

    snapshot = transport.handle(
        HttpApiRequest(
            method="GET",
            path=(
                "/api/v1/sessions/session%201/tasks/task%201/audit"
                "?entry=from_task&filter=files&includeDetail=true"
                "&limit=25&recordId=record%201"
            ),
        )
    )
    records = transport.handle(
        HttpApiRequest(
            method="GET",
            path=(
                "/api/v1/sessions/session%201/tasks/task%201/audit/records"
                "?filter=files&kind=file_change&includeHiddenReasons=true"
            ),
        )
    )
    detail = transport.handle(
        HttpApiRequest(
            method="GET",
            path=(
                "/api/v1/sessions/session%201/audit/records/record%201"
                "?includeEvidence=true"
            ),
        )
    )
    evidence = transport.handle(
        HttpApiRequest(
            method="GET",
            path=(
                "/api/v1/sessions/session%201/audit/evidence/evidence%201"
                "?includeSanitizedPayload=false"
            ),
        )
    )

    assert snapshot.status_code == 200
    assert _dict_body(snapshot.body)["data"]["schemaVersion"] == "plato.audit.v1"
    assert records.status_code == 200
    assert _dict_body(records.body)["data"]["records"][0]["id"] == "record 1"
    assert detail.status_code == 200
    assert _dict_body(detail.body)["data"]["id"] == "record 1"
    assert evidence.status_code == 200
    assert _dict_body(evidence.body)["data"]["id"] == "evidence 1"
    assert query.audit_calls == [
        (
            "snapshot",
            "session 1",
            "task 1",
            "from_task",
            "files",
            "record 1",
            True,
            25,
        ),
        (
            "records",
            "session 1",
            "task 1",
            "files",
            "file_change",
            True,
        ),
        ("detail", "session 1", "record 1", True, False),
        ("evidence", "session 1", "evidence 1", False),
    ]


def test_ask_routes_decode_params_and_return_contract_json() -> None:
    query = _QueryGateway()
    transport = _transport(query=query)

    listed = transport.handle(
        HttpApiRequest(
            method="GET",
            path=(
                "/api/v1/sessions/session%201/asks"
                "?status=pending&taskNodeId=task%201"
            ),
        )
    )
    detail = transport.handle(
        HttpApiRequest(
            method="GET",
            path="/api/v1/sessions/session%201/asks/ask%201",
        )
    )

    assert listed.status_code == 200
    assert _dict_body(listed.body)["data"]["asks"][0]["id"] == "ask 1"
    assert _dict_body(listed.body)["data"]["activeAsk"]["id"] == "ask 1"
    assert detail.status_code == 200
    assert _dict_body(detail.body)["data"]["id"] == "ask 1"
    assert query.ask_calls == [
        ("list", "session 1", "pending", "task 1"),
        ("detail", "session 1", "ask 1"),
    ]


def test_session_lifecycle_routes_dispatch_to_gateway() -> None:
    lifecycle = _SessionLifecycleGateway()
    transport = _transport(session_lifecycle_gateway=lifecycle)

    listed = transport.handle(HttpApiRequest(method="GET", path="/api/v1/sessions"))
    created = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions",
            body={"name": "New session"},
        )
    )
    renamed = transport.handle(
        HttpApiRequest(
            method="PATCH",
            path="/api/v1/sessions/session%201",
            body={"name": "Renamed"},
        )
    )
    deleted = transport.handle(
        HttpApiRequest(method="POST", path="/api/v1/sessions/session%201/delete")
    )

    assert listed.status_code == 200
    assert _dict_body(listed.body)["data"]["sessions"][0]["id"] == "session-1"
    assert created.status_code == 200
    assert _dict_body(created.body)["data"]["sessionId"] == "created-session"
    assert renamed.status_code == 200
    assert _dict_body(renamed.body)["data"]["session"]["name"] == "Renamed"
    assert deleted.status_code == 200
    assert _dict_body(deleted.body)["data"]["nextSessionId"] == "next-session"
    assert lifecycle.calls == [
        ("list",),
        ("create", "New session"),
        ("rename", "session 1", "Renamed"),
        ("delete", "session 1"),
    ]


def test_command_routes_validate_and_dispatch_to_gateway_methods() -> None:
    commands = _CommandGateway()
    transport = _transport(commands=commands)

    cases = (
        (
            "POST",
            "/api/v1/sessions/session%201/input",
            _command_body("session 1", {"content": "Build a site", "mode": "generate_task_tree"}),
            "append_session_input",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/task-tree/generate",
            _command_body("session 1", {"prompt": "Build a site"}),
            "generate_task_tree",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/authoring/raw-tasks/raw%201/asks/answers",
            _command_body(
                "session 1",
                {
                    "answers": [
                        {"askId": "ask 1", "value": "Developers"},
                        {"askId": "ask 2", "value": "Portfolio"},
                    ]
                },
            ),
            "answer_authoring_ask_batch:raw 1",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/authoring/repair",
            _command_body("session 1", {"reason": "dirty_authoring_state"}),
            "repair_authoring_state",
        ),
        (
            "PATCH",
            "/api/v1/sessions/session%201/tasks/task%201",
            _command_body("session 1", {"summary": "Updated"}),
            "update_task_node:task 1",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/tasks/task%201/input",
            _command_body("session 1", {"content": "Use calmer copy", "mode": "guidance"}),
            "append_task_input:task 1",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/tasks/task%201/retry",
            _command_body(
                "session 1",
                {"instruction": "Try safer path", "startImmediately": False},
            ),
            "retry_task:task 1",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/tasks/task%201/stop",
            _command_body("session 1", {"reason": "user requested stop"}),
            "stop_task:task 1",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/task-tree/publish",
            _command_body("session 1", {"taskTreeId": "tree-1", "startImmediately": True}),
            "publish_task_tree",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/confirmations/confirm%201/respond",
            _command_body("session 1", {"value": "yes"}),
            "resolve_confirmation:confirm 1",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/asks/ask%201/answer",
            _command_body("session 1", {"text": "Use Vercel."}),
            "answer_ask:ask 1",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/asks/ask%201/defer",
            _command_body("session 1", {"reason": "Need more input later."}),
            "defer_ask:ask 1",
        ),
        (
            "POST",
            "/api/v1/sessions/session%201/asks/ask%201/cancel",
            _command_body("session 1", {"reason": "User cancelled the ASK."}),
            "cancel_ask:ask 1",
        ),
    )

    for method, path, body, _expected_call in cases:
        response = transport.handle(HttpApiRequest(method=method, path=path, body=body))
        assert response.status_code == 200
        assert _dict_body(response.body)["result"]["status"] == "accepted"

    assert commands.calls == [case[3] for case in cases]


def test_publish_start_immediately_requests_execution_dispatch() -> None:
    execution = _ExecutionTriggerGateway()
    transport = _transport(execution_trigger_gateway=execution)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/task-tree/publish",
            body=_command_body(
                "session 1",
                {"taskTreeId": "tree-1", "startImmediately": True},
                command_id="publish-1",
            ),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["result"]["debugRefs"]["dispatchStatus"] == "queued"
    assert body["result"]["debugRefs"]["dispatchReason"] == (
        "publish_start_immediately"
    )
    assert body["refresh"]["waitForEvents"] is True
    assert execution.calls == [
        ("session 1", "publish_start_immediately", "publish-1")
    ]


def test_publish_start_immediately_false_does_not_dispatch() -> None:
    execution = _ExecutionTriggerGateway()
    transport = _transport(execution_trigger_gateway=execution)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/task-tree/publish",
            body=_command_body(
                "session 1",
                {"taskTreeId": "tree-1", "startImmediately": False},
            ),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert "dispatchStatus" not in body["result"]["debugRefs"]
    assert execution.calls == []


def test_retry_start_immediately_requests_execution_dispatch() -> None:
    execution = _ExecutionTriggerGateway()
    transport = _transport(execution_trigger_gateway=execution)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/tasks/task%201/retry",
            body=_command_body(
                "session 1",
                {"instruction": "Try safer path", "startImmediately": True},
                command_id="retry-1",
            ),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["result"]["debugRefs"]["dispatchStatus"] == "queued"
    assert body["result"]["debugRefs"]["dispatchReason"] == "retry_start_immediately"
    assert execution.calls == [("session 1", "retry_start_immediately", "retry-1")]


def test_retry_start_immediately_false_does_not_dispatch() -> None:
    execution = _ExecutionTriggerGateway()
    transport = _transport(execution_trigger_gateway=execution)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/tasks/task%201/retry",
            body=_command_body(
                "session 1",
                {"instruction": "Try safer path", "startImmediately": False},
                command_id="retry-1",
            ),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert "dispatchStatus" not in body["result"]["debugRefs"]
    assert execution.calls == []


def test_answer_ask_requests_execution_dispatch_after_acceptance() -> None:
    execution = _ExecutionTriggerGateway()
    transport = _transport(execution_trigger_gateway=execution)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/asks/ask%201/answer",
            body=_command_body(
                "session 1",
                {"text": "Use Vercel."},
                command_id="answer-1",
            ),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["result"]["debugRefs"]["dispatchStatus"] == "queued"
    assert body["result"]["debugRefs"]["dispatchReason"] == "ask_answer_resume"
    assert execution.calls == [("session 1", "ask_answer_resume", "answer-1")]


def test_rejected_answer_ask_does_not_request_execution_dispatch() -> None:
    commands = _CommandGateway(reject_ask_answer=True)
    execution = _ExecutionTriggerGateway()
    transport = _transport(commands=commands, execution_trigger_gateway=execution)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/asks/ask%201/answer",
            body=_command_body(
                "session 1",
                {"text": "Use Vercel."},
                command_id="answer-1",
            ),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is False
    assert body["result"]["status"] == "rejected"
    assert execution.calls == []


def test_execution_dispatch_route_returns_accepted_command_response() -> None:
    execution = _ExecutionTriggerGateway()
    transport = _transport(execution_trigger_gateway=execution)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/execution/dispatch",
            body=_command_body("session 1", {}),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["result"]["status"] == "accepted"
    assert body["result"]["debugRefs"]["dispatchStatus"] == "queued"
    assert body["refresh"]["waitForEvents"] is True
    assert body["refresh"]["suggestedQueries"] == ["session.snapshot", "task.tree"]
    assert execution.calls == [("session 1", "manual_control_route", "command-1")]


def test_execution_dispatch_route_rejects_disabled_dispatcher() -> None:
    execution = _ExecutionTriggerGateway(status="disabled")
    transport = _transport(execution_trigger_gateway=execution)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/execution/dispatch",
            body=_command_body("session 1", {}, command_id="dispatch-1"),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is False
    assert body["result"]["status"] == "rejected"
    assert body["error"]["code"] == "command_rejected"
    assert body["error"]["details"]["dispatch_status"] == "disabled"
    assert body["refresh"]["waitForEvents"] is False


def test_command_route_rejects_path_body_session_mismatch() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session-1/input",
            body=_command_body("other-session", {"content": "Build", "mode": "global_guidance"}),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 400
    assert body["error"]["code"] == "bad_request"
    assert body["error"]["details"] == {
        "body_session_id": "other-session",
        "path_session_id": "session-1",
    }


def test_command_route_rejects_invalid_body_with_validation_details() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session-1/input",
            body=_command_body("session-1", {"content": "", "mode": "global_guidance"}),
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 400
    assert body["error"]["code"] == "bad_request"
    assert body["error"]["details"]["errors"]


def test_command_route_replays_idempotent_response_before_gateway_dispatch() -> None:
    commands = _CommandGateway()
    transport = _transport(
        commands=commands,
        command_idempotency_store=InMemoryUiCommandResponseIdempotencyStore(),
    )

    first = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/task-tree/generate",
            body=_command_body(
                "session 1",
                {"prompt": "Build a site"},
                command_id="command-1",
                idempotency_key="idem-1",
            ),
        )
    )
    replay = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/task-tree/generate",
            body=_command_body(
                "session 1",
                {"prompt": "Build a site"},
                command_id="command-2",
                idempotency_key="idem-1",
            ),
        )
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert _dict_body(replay.body) == _dict_body(first.body)
    assert commands.calls == ["generate_task_tree"]


def test_confirmation_route_replays_idempotent_response_before_gateway_dispatch() -> None:
    commands = _CommandGateway()
    transport = _transport(
        commands=commands,
        command_idempotency_store=InMemoryUiCommandResponseIdempotencyStore(),
    )

    first = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/confirmations/confirm%201/respond",
            body=_command_body(
                "session 1",
                {"value": "yes", "note": "Looks good"},
                command_id="command-1",
                idempotency_key="resolve-confirmation-1",
            ),
        )
    )
    replay = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/confirmations/confirm%201/respond",
            body=_command_body(
                "session 1",
                {"value": "yes", "note": "Looks good"},
                command_id="command-2",
                idempotency_key="resolve-confirmation-1",
            ),
        )
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert _dict_body(replay.body) == _dict_body(first.body)
    assert commands.calls == ["resolve_confirmation:confirm 1"]


def test_command_route_rejects_idempotency_key_reused_for_different_payload() -> None:
    commands = _CommandGateway()
    transport = _transport(
        commands=commands,
        command_idempotency_store=InMemoryUiCommandResponseIdempotencyStore(),
    )

    first = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/task-tree/generate",
            body=_command_body(
                "session 1",
                {"prompt": "Build a site"},
                command_id="command-1",
                idempotency_key="idem-1",
            ),
        )
    )
    conflict = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/task-tree/generate",
            body=_command_body(
                "session 1",
                {"prompt": "Build another site"},
                command_id="command-2",
                idempotency_key="idem-1",
            ),
        )
    )
    body = _dict_body(conflict.body)

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert body["requestId"] == "command-2"
    assert body["error"]["code"] == "idempotency_conflict"
    assert body["error"]["details"] == {
        "idempotency_key": "idem-1",
        "route": "generate_task_tree",
    }
    assert commands.calls == ["generate_task_tree"]


def test_method_mismatch_and_unknown_route_return_transport_errors() -> None:
    transport = _transport()

    wrong_method = transport.handle(
        HttpApiRequest(method="POST", path="/api/v1/sessions/session-1/snapshot")
    )
    unknown = transport.handle(HttpApiRequest(method="GET", path="/api/v1/unknown"))

    assert wrong_method.status_code == 405
    assert wrong_method.headers["allow"] == "GET"
    assert _dict_body(wrong_method.body)["error"]["code"] == "bad_request"
    assert unknown.status_code == 404
    assert _dict_body(unknown.body)["error"]["code"] == "not_found"


def test_auth_requires_bearer_for_json_routes_and_query_token_for_sse() -> None:
    event = UiEvent(session_id="session-1", event_type="message.appended", cursor="cursor-1")
    transport = _transport(
        auth=SidecarAuth("secret-token"),
        event_source=StaticUiEventSource((event,)),
    )

    rejected = transport.handle(HttpApiRequest(method="GET", path="/api/v1/health"))
    allowed = transport.handle(
        HttpApiRequest(
            method="GET",
            path="/api/v1/health",
            headers={"authorization": "Bearer secret-token"},
        )
    )
    sse = transport.handle(
        HttpApiRequest(
            method="GET",
            path="/api/v1/sessions/session-1/events?token=secret-token",
        )
    )

    assert rejected.status_code == 401
    assert allowed.status_code == 200
    assert sse.status_code == 200
    assert sse.headers["content-type"] == "text/event-stream"
    assert "event: message.appended" in _str_body(sse.body)


def test_event_route_uses_resync_fallback_by_default() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(method="GET", path="/api/v1/sessions/session-1/events?cursor=old")
    )
    body = _str_body(response.body)

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream"
    assert "event: session.resync_required" in body
    assert '"cursor":"old"' in body


def test_event_route_replays_from_workspace_event_source(tmp_path: Path) -> None:
    source = SqliteUiEventSource(tmp_path / "ui_events.sqlite")
    try:
        source.append(
            UiEvent(
                event_id="event-1",
                session_id="session-1",
                event_type="message.appended",
                cursor="cursor-1",
            )
        )
        source.append(
            UiEvent(
                event_id="event-2",
                session_id="session-1",
                event_type="audit.records_changed",
                cursor="cursor-2",
            )
        )
        transport = _transport(event_source=source)

        response = transport.handle(
            HttpApiRequest(
                method="GET",
                path="/api/v1/sessions/session-1/events?cursor=cursor-1",
            )
        )
        body = _str_body(response.body)
    finally:
        source.close()

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream"
    assert "event: audit.records_changed" in body
    assert "event: message.appended" not in body
    assert '"cursor":"cursor-2"' in body


def test_client_error_log_route_dispatches_to_sink() -> None:
    sink = _ClientErrorSink()
    transport = _transport(client_error_log_sink=sink)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session%201/client-logs/errors",
            body={
                "entry": {
                    "level": "error",
                    "message": "snapshot failed",
                    "namespace": "main-page",
                }
            },
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"] == {"stored": True}
    assert sink.calls == [
        (
            "session 1",
            {
                "entry": {
                    "level": "error",
                    "message": "snapshot failed",
                    "namespace": "main-page",
                }
            },
        )
    ]


def test_client_error_log_route_rejects_empty_body() -> None:
    transport = _transport(client_error_log_sink=_ClientErrorSink())

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session-1/client-logs/errors",
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 400
    assert body["error"]["code"] == "bad_request"


@dataclass
class _QueryGateway:
    snapshot_calls: list[str] = field(default_factory=list)
    ask_calls: list[tuple[Any, ...]] = field(default_factory=list)
    audit_calls: list[tuple[Any, ...]] = field(default_factory=list)

    def get_session_snapshot(
        self,
        session_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[MainPageSnapshot]:
        self.snapshot_calls.append(session_id)
        project = ProjectSummary(id="local", name="Local")
        workflow = WorkflowSummary(id="authoring", name="Authoring")
        session = SessionSummary(
            id=session_id,
            project_id=project.id,
            workflow_id=workflow.id,
            name="Session",
            status="new",
            created_at=NOW,
            updated_at=NOW,
        )
        snapshot = MainPageSnapshot(
            project=project,
            workflows=(workflow,),
            workflow=workflow,
            sessions=(session,),
            session=session,
            cursor="cursor-1",
            generated_at=NOW,
        )
        return QueryResponse[MainPageSnapshot](
            request_id=request_id or "request-snapshot",
            ok=True,
            data=snapshot,
            cursor=snapshot.cursor,
        )

    def list_asks(
        self,
        session_id: str,
        *,
        status: str | None = None,
        task_node_id: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[AskListResult]:
        self.ask_calls.append(("list", session_id, status, task_node_id))
        ask = _ask_view(session_id, ask_id="ask 1", task_node_id=task_node_id)
        return QueryResponse[AskListResult](
            request_id=request_id or "request-asks",
            ok=True,
            data=AskListResult(session_id=session_id, asks=(ask,), active_ask=ask),
        )

    def get_ask(
        self,
        session_id: str,
        ask_id: str,
        *,
        request_id: str | None = None,
    ) -> QueryResponse[AskRequestView]:
        self.ask_calls.append(("detail", session_id, ask_id))
        return QueryResponse[AskRequestView](
            request_id=request_id or "request-ask-detail",
            ok=True,
            data=_ask_view(session_id, ask_id=ask_id, task_node_id="task 1"),
        )

    def get_audit_snapshot(
        self,
        session_id: str,
        *,
        task_node_id: str | None = None,
        entry: str | None = None,
        filter_kind: str = "all",
        record_id: str | None = None,
        include_detail: bool | None = None,
        limit: int = 50,
        cursor: str | None = None,
        request_id: str | None = None,
    ) -> QueryResponse[AuditPageSnapshot]:
        del cursor
        self.audit_calls.append(
            (
                "snapshot",
                session_id,
                task_node_id,
                entry,
                filter_kind,
                record_id,
                include_detail,
                limit,
            )
        )
        snapshot = AuditPageSnapshot(
            request=AuditPageRequestView(
                filter="files",
                record_id="record 1",
                include_detail=True,
                limit=25,
            ),
            scope=AuditSessionScope(session_id=session_id),
            entry_context=AuditEntryContext(
                kind="from_task",
                session_id=session_id,
                task_node_id=task_node_id,
                source_route=f"/sessions/{session_id}",
                preferred_filter="files",
                preferred_record_id="record 1",
            ),
            return_target=MainPageReturnTarget(
                route_name="main.sessionFallback",
                session_id=session_id,
                task_node_id=task_node_id,
                focus="task",
                record_id="record 1",
            ),
            session=_session_summary(session_id),
            overview=AuditOverview(
                verdict="warning",
                completeness="partial",
                summary="Audit projection is partial.",
                record_counts={"all": 1, "files": 1},
                important_record_ids=("record 1",),
                generated_by="projection",
                updated_at=NOW,
            ),
            records=(_audit_record(session_id),),
            selected_record=_audit_record_detail(session_id),
            generated_at=NOW,
        )
        return QueryResponse[AuditPageSnapshot](
            request_id=request_id or "request-audit-snapshot",
            ok=True,
            data=snapshot,
            cursor=snapshot.cursor,
        )

    def list_audit_records(
        self,
        session_id: str,
        *,
        task_node_id: str | None = None,
        filter_kind: str = "all",
        kind: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
        include_hidden_reasons: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[AuditRecordsResult]:
        del from_time, to_time, limit, cursor
        self.audit_calls.append(
            (
                "records",
                session_id,
                task_node_id,
                filter_kind,
                kind,
                include_hidden_reasons,
            )
        )
        return QueryResponse[AuditRecordsResult](
            request_id=request_id or "request-audit-records",
            ok=True,
            data=AuditRecordsResult(
                records=(_audit_record(session_id),),
                total_count=1,
            ),
        )

    def get_audit_record_detail(
        self,
        session_id: str,
        record_id: str,
        *,
        include_evidence: bool = False,
        include_sanitized_payload: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[AuditRecordDetail]:
        self.audit_calls.append(
            (
                "detail",
                session_id,
                record_id,
                include_evidence,
                include_sanitized_payload,
            )
        )
        return QueryResponse[AuditRecordDetail](
            request_id=request_id or "request-audit-detail",
            ok=True,
            data=_audit_record_detail(session_id),
        )

    def get_evidence_detail(
        self,
        session_id: str,
        evidence_id: str,
        *,
        include_sanitized_payload: bool = False,
        request_id: str | None = None,
    ) -> QueryResponse[EvidenceDetail]:
        self.audit_calls.append(
            ("evidence", session_id, evidence_id, include_sanitized_payload)
        )
        return QueryResponse[EvidenceDetail](
            request_id=request_id or "request-evidence-detail",
            ok=True,
            data=EvidenceDetail(
                id=evidence_id,
                kind="file_change",
                label="File change",
                summary="Changed src/App.tsx.",
                source="task_projection",
                body="Changed src/App.tsx.",
            ),
        )


@dataclass
class _CommandGateway:
    calls: list[str] = field(default_factory=list)
    reject_ask_answer: bool = False

    def append_session_input(
        self,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append("append_session_input")
        return _accepted(request.command_id)

    def generate_task_tree(
        self,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append("generate_task_tree")
        return _accepted(request.command_id)

    def update_task_node(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"update_task_node:{task_node_id}")
        return _accepted(request.command_id)

    def append_task_input(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"append_task_input:{task_node_id}")
        return _accepted(request.command_id)

    def publish_task_tree(
        self,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append("publish_task_tree")
        return _accepted(request.command_id)

    def retry_task(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"retry_task:{task_node_id}")
        return _accepted(request.command_id)

    def stop_task(
        self,
        task_node_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"stop_task:{task_node_id}")
        return _accepted(request.command_id)

    def resolve_confirmation(
        self,
        confirmation_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"resolve_confirmation:{confirmation_id}")
        return _accepted(request.command_id)

    def answer_ask(
        self,
        ask_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"answer_ask:{ask_id}")
        if self.reject_ask_answer:
            return _rejected(request.command_id, message="ASK is not pending: answered")
        return _accepted(request.command_id)

    def answer_authoring_ask_batch(
        self,
        raw_task_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"answer_authoring_ask_batch:{raw_task_id}")
        return _accepted(request.command_id)

    def repair_authoring_state(
        self,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append("repair_authoring_state")
        return _accepted(request.command_id)

    def defer_ask(
        self,
        ask_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"defer_ask:{ask_id}")
        return _accepted(request.command_id)

    def cancel_ask(
        self,
        ask_id: str,
        request: CommandRequest[Any],
    ) -> CommandResponse:
        self.calls.append(f"cancel_ask:{ask_id}")
        return _accepted(request.command_id)


@dataclass
class _ClientErrorSink:
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def write_error(self, session_id: str, payload: dict[str, Any]) -> None:
        self.calls.append((session_id, payload))


@dataclass
class _SessionLifecycleGateway:
    calls: list[tuple[Any, ...]] = field(default_factory=list)

    def list_sessions(self) -> dict[str, Any]:
        self.calls.append(("list",))
        return {"sessions": [{"id": "session-1", "name": "Session 1"}]}

    def create_session(self, name: str) -> dict[str, Any]:
        self.calls.append(("create", name))
        return {"sessionId": "created-session", "session": {"name": name}}

    def rename_session(self, session_id: str, name: str) -> dict[str, Any]:
        self.calls.append(("rename", session_id, name))
        return {"sessionId": session_id, "session": {"id": session_id, "name": name}}

    def delete_session(self, session_id: str) -> dict[str, Any]:
        self.calls.append(("delete", session_id))
        return {"deletedSessionId": session_id, "nextSessionId": "next-session"}


def _session_summary(session_id: str) -> SessionSummary:
    return SessionSummary(
        id=session_id,
        project_id="local",
        workflow_id="authoring",
        name="Session",
        status="running",
        created_at=NOW,
        updated_at=NOW,
    )


def _audit_record(session_id: str) -> AuditRecord:
    return AuditRecord(
        id="record 1",
        scope=AuditSessionScope(session_id=session_id),
        kind="file_change",
        filter_kind="files",
        title="File changed",
        summary="Changed src/App.tsx.",
        actor="tool",
        source_label="Task projection",
        occurred_at=NOW,
        severity="warning",
        confidence="medium",
        verdict="warning",
        evidence_refs=(
            EvidenceRef(
                id="evidence 1",
                kind="file_change",
                label="File change",
                summary="Changed src/App.tsx.",
            ),
        ),
    )


def _audit_record_detail(session_id: str) -> AuditRecordDetail:
    return AuditRecordDetail(
        **_audit_record(session_id).model_dump(),
        body="Changed src/App.tsx.",
        why_it_matters="File changes must be attributable.",
    )


def _ask_view(
    session_id: str,
    *,
    ask_id: str,
    task_node_id: str | None,
) -> AskRequestView:
    return AskRequestView(
        id=ask_id,
        session_id=session_id,
        task_node_id=task_node_id,
        question="Which deployment target should be used?",
        reason="The agent needs a user-owned deployment decision.",
        answer_type="free_text",
        allow_free_text=True,
        allow_no_option_with_text=True,
        blocking=True,
        status="pending",
        created_at=NOW,
    )


@dataclass
class _ExecutionTriggerGateway:
    status: str = "queued"
    calls: list[tuple[str, str, str | None]] = field(default_factory=list)

    def request_dispatch(
        self,
        session_id: str,
        *,
        reason: str,
        request_id: str | None = None,
    ) -> ExecutionDispatchRequestResult:
        self.calls.append((session_id, reason, request_id))
        return ExecutionDispatchRequestResult(
            status=self.status,  # type: ignore[arg-type]
            session_id=session_id,
            reason=reason,  # type: ignore[arg-type]
            request_id=request_id,
            message=f"dispatch {self.status}",
            error_ref=None if self.status == "queued" else self.status,
        )


@dataclass
class _SnapshotRecoveryGateway:
    raises: Exception | None = None
    calls: list[str] = field(default_factory=list)

    def recover_session(self, session_id: str) -> object:
        self.calls.append(session_id)
        if self.raises is not None:
            raise self.raises
        return {"recovered": True}


@dataclass
class _SettingsReadinessGateway:
    calls: int = 0

    def get_readiness(self) -> dict[str, Any]:
        self.calls += 1
        return {
            "schemaVersion": "plato.settings_readiness.v1",
            "status": "ready",
        }


@dataclass
class _SettingsConfigGateway:
    validation_error: SettingsConfigValidationError | None = None
    config_calls: int = 0
    recheck_calls: int = 0
    update_calls: list[dict[str, Any]] = field(default_factory=list)

    def get_config(self) -> dict[str, Any]:
        self.config_calls += 1
        return {
            "schemaVersion": "plato.settings_config.v1",
            "llm": {
                "provider": "litellm",
                "apiKeyConfigured": False,
            },
        }

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.update_calls.append(payload)
        if self.validation_error is not None:
            raise self.validation_error
        return {
            "schemaVersion": "plato.settings_config_update.v1",
            "config": {
                "schemaVersion": "plato.settings_config.v1",
                "llm": {
                    "provider": "litellm",
                    "apiKeyConfigured": True,
                },
            },
            "readiness": {
                "schemaVersion": "plato.settings_readiness.v1",
                "status": "ready",
            },
        }

    def get_readiness(self) -> dict[str, Any]:
        return self.recheck_readiness()

    def recheck_readiness(self) -> dict[str, Any]:
        self.recheck_calls += 1
        return {
            "schemaVersion": "plato.settings_readiness.v1",
            "status": "ready",
        }


@dataclass
class _DiagnosticExportGateway:
    calls: list[str] = field(default_factory=list)

    def export_session(self, session_id: str) -> dict[str, Any]:
        self.calls.append(session_id)
        return {
            "schemaVersion": "plato.diagnostics_export.v1",
            "bundleId": f"diagnostic-bundle-{session_id}",
            "bundleDir": "/tmp/bundle",
            "bundleDirLabel": "workspace://current/.taskweavn/diagnostics/bundle",
            "zipPath": "/tmp/bundle.zip",
            "zipPathLabel": "workspace://current/.taskweavn/diagnostics/bundle.zip",
            "manifestPath": "/tmp/bundle/manifest.json",
            "manifestPathLabel": (
                "workspace://current/.taskweavn/diagnostics/bundle/manifest.json"
            ),
            "createdAt": "2026-05-21T09:00:00Z",
            "redactionProfile": "product_1_0_default",
            "includedSections": ["session"],
            "sections": [{"name": "session", "status": "included", "warnings": []}],
            "warnings": [],
            "fileCount": 1,
        }


def _transport(
    *,
    query: _QueryGateway | None = None,
    commands: _CommandGateway | None = None,
    event_source: UiEventSource | None = None,
    auth: SidecarAuth | None = None,
    client_error_log_sink: _ClientErrorSink | None = None,
    session_lifecycle_gateway: _SessionLifecycleGateway | None = None,
    command_idempotency_store: InMemoryUiCommandResponseIdempotencyStore | None = None,
    execution_trigger_gateway: _ExecutionTriggerGateway | None = None,
    snapshot_recovery_gateway: _SnapshotRecoveryGateway | None = None,
    settings_readiness_gateway: _SettingsReadinessGateway | None = None,
    settings_config_gateway: _SettingsConfigGateway | None = None,
    diagnostic_export_gateway: _DiagnosticExportGateway | None = None,
) -> PlatoUiHttpTransport:
    return PlatoUiHttpTransport(
        query_gateway=query or _QueryGateway(),
        command_gateway=commands or _CommandGateway(),
        event_source=event_source,
        auth=auth,
        client_error_log_sink=client_error_log_sink,
        session_lifecycle_gateway=session_lifecycle_gateway,
        command_idempotency_store=command_idempotency_store,
        execution_trigger_gateway=execution_trigger_gateway,
        snapshot_recovery_gateway=snapshot_recovery_gateway,
        settings_readiness_gateway=settings_readiness_gateway,
        settings_config_gateway=settings_config_gateway,
        diagnostic_export_gateway=diagnostic_export_gateway,
    )


def _accepted(command_id: str) -> CommandResponse:
    return CommandResponse(
        request_id=f"request-{command_id}",
        ok=True,
        result=CommandResult(
            command_id=command_id,
            status="accepted",
            message="accepted",
        ),
    )


def _rejected(command_id: str, *, message: str) -> CommandResponse:
    return CommandResponse(
        request_id=f"request-{command_id}",
        ok=False,
        result=CommandResult(
            command_id=command_id,
            status="rejected",
            message=message,
        ),
        error=ApiError(code="command_rejected", message=message),
    )


def _command_body(
    session_id: str,
    payload: dict[str, object],
    *,
    command_id: str = "command-1",
    idempotency_key: str | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "commandId": command_id,
        "sessionId": session_id,
        "payload": payload,
    }
    if idempotency_key is not None:
        body["idempotencyKey"] = idempotency_key
    return body


def _dict_body(body: dict[str, Any] | str) -> dict[str, Any]:
    assert isinstance(body, dict)
    return body


def _str_body(body: dict[str, Any] | str) -> str:
    assert isinstance(body, str)
    return body
