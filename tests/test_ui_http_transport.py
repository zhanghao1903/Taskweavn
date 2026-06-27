"""Tests for the framework-neutral Plato UI HTTP transport."""

from __future__ import annotations

from pathlib import Path

from taskweavn.runtime_config import (
    RuntimeConfigPatch,
    RuntimeConfigScope,
)
from taskweavn.server import (
    HttpApiRequest,
    InMemoryUiCommandResponseIdempotencyStore,
    SidecarAuth,
    SqliteUiEventSource,
    StaticUiEventSource,
)
from taskweavn.server.runtime_config_gateway import DefaultRuntimeConfigGateway
from taskweavn.server.settings_config import (
    SettingsConfigFieldError,
    SettingsConfigValidationError,
)
from taskweavn.server.ui_contract import (
    UiEvent,
)
from tests.fixtures.ui_http_transport import (
    _ClientErrorSink,
    _command_body,
    _CommandGateway,
    _DiagnosticExportGateway,
    _dict_body,
    _ExecutionTriggerGateway,
    _QueryGateway,
    _runtime_config_actor,
    _runtime_config_transport_fixture,
    _runtime_config_ts,
    _RuntimeInputRouter,
    _SessionLifecycleGateway,
    _SettingsConfigGateway,
    _SettingsReadinessGateway,
    _SnapshotRecoveryGateway,
    _str_body,
    _transport,
)


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
    assert body["data"]["runtime_config_schema_url"] == "/api/v1/runtime/config/schema"
    assert body["data"]["runtime_config_effective_url"] == (
        "/api/v1/runtime/config/effective"
    )
    assert body["data"]["runtime_config_explain_url_template"] == (
        "/api/v1/runtime/config/explain?key={key}"
    )
    assert body["data"]["runtime_config_changes_url"] == (
        "/api/v1/runtime/config/changes"
    )
    assert body["data"]["runtime_config_snapshot_url_template"] == (
        "/api/v1/runtime/config/snapshots/{configHash}"
    )
    assert body["data"]["settings_readiness_recheck_url"] == (
        "/api/v1/settings/readiness/recheck"
    )
    assert body["data"]["settings_recovery_action_url"] == (
        "/api/v1/settings/recovery-action"
    )
    assert body["data"]["snapshot_url_template"] == (
        "/api/v1/sessions/{sessionId}/snapshot"
    )
    assert body["data"]["activity_url_template"] == (
        "/api/v1/sessions/{sessionId}/activity"
    )


def test_health_route_returns_sidecar_identity() -> None:
    transport = _transport()

    response = transport.handle(HttpApiRequest(method="GET", path="/api/v1/health"))
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"] == {"name": "Plato Sidecar", "version": "0.1.0"}


def test_settings_recovery_action_route_rejects_non_executable_action() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/settings/recovery-action",
            body={"action": "erase_disk"},
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 400
    assert body["ok"] is False
    assert body["error"]["code"] == "bad_request"
    assert body["error"]["details"]["action"] == "erase_disk"


def test_runtime_input_route_returns_router_result() -> None:
    router = _RuntimeInputRouter()
    transport = _transport(runtime_input_router=router)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session-1/runtime-input/route",
            body={
                "commandId": "route-question",
                "sessionId": "session-1",
                "content": "What is this task doing?",
                "mode": "ask",
                "selection": {
                    "scopeKind": "session",
                },
            },
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["outcome"]["status"] == "answered"
    assert body["data"]["decision"]["dispatchTarget"] == "read_only_inquiry"
    assert router.calls[0].command_id == "route-question"


def test_workspace_runtime_input_route_injects_workspace_id() -> None:
    router = _RuntimeInputRouter()
    transport = _transport(runtime_input_router=router)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path=(
                "/api/v1/workspaces/workspace%201/sessions/session-1"
                "/runtime-input/route"
            ),
            body={
                "commandId": "route-question",
                "sessionId": "session-1",
                "content": "What is this task doing?",
                "selection": {
                    "scopeKind": "session",
                },
            },
        )
    )

    assert response.status_code == 200
    assert router.calls[0].workspace_id == "workspace 1"


def test_workspace_runtime_input_route_rejects_workspace_mismatch() -> None:
    router = _RuntimeInputRouter()
    transport = _transport(runtime_input_router=router)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path=(
                "/api/v1/workspaces/path-workspace/sessions/session-1"
                "/runtime-input/route"
            ),
            body={
                "commandId": "route-question",
                "sessionId": "session-1",
                "workspaceId": "body-workspace",
                "content": "What is this task doing?",
                "selection": {
                    "scopeKind": "session",
                },
            },
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 400
    assert body["error"]["code"] == "bad_request"
    assert body["error"]["details"] == {
        "body_workspace_id": "body-workspace",
        "path_workspace_id": "path-workspace",
    }
    assert router.calls == []


def test_runtime_input_route_requires_router() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/api/v1/sessions/session-1/runtime-input/route",
            body={
                "commandId": "route-question",
                "sessionId": "session-1",
                "content": "What is this task doing?",
                "selection": {
                    "scopeKind": "session",
                },
            },
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 503
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["details"]["route"] == "runtime_input_route"


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


def test_runtime_config_schema_route_returns_registered_keys() -> None:
    transport = _transport(runtime_config_gateway=DefaultRuntimeConfigGateway())

    response = transport.handle(
        HttpApiRequest(method="GET", path="/api/v1/runtime/config/schema")
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["schemaVersion"] == "plato.runtime_config_schema.v1"
    keys = {item["key"] for item in body["data"]["keys"]}
    assert "agent_loop.default_max_steps" in keys
    assert "computer_use.backend" in keys


def test_runtime_config_effective_route_returns_source_attribution() -> None:
    runtime_config_gateway = DefaultRuntimeConfigGateway.from_process_inputs(
        {
            "agent_loop.default_max_steps": 8,
            "computer_use.enabled": True,
            "logging.level": "DEBUG",
        },
        workspace_id="workspace-1",
        env={"LLM_PROVIDER": "deepseek", "LLM_MODEL": "deepseek-v4-pro"},
    )
    transport = _transport(runtime_config_gateway=runtime_config_gateway)

    response = transport.handle(
        HttpApiRequest(
            method="GET",
            path="/api/v1/runtime/config/effective?sessionId=session-1",
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    data = body["data"]
    assert data["schemaVersion"] == "plato.runtime_config.v1"
    assert data["scope"]["level"] == "session"
    assert data["scope"]["sessionId"] == "session-1"
    max_steps = data["values"]["agent_loop.default_max_steps"]
    assert max_steps["value"] == 8
    assert max_steps["source"]["kind"] == "process_input"
    llm_provider = data["values"]["llm.default_provider"]
    assert llm_provider["value"] == "deepseek"
    assert llm_provider["source"]["kind"] == "environment"


def test_runtime_config_explain_route_returns_one_key() -> None:
    runtime_config_gateway = DefaultRuntimeConfigGateway.from_process_inputs(
        {"agent_loop.default_max_steps": 12},
        workspace_id="workspace-1",
    )
    transport = _transport(runtime_config_gateway=runtime_config_gateway)

    response = transport.handle(
        HttpApiRequest(
            method="GET",
            path="/api/v1/runtime/config/explain?key=agent_loop.default_max_steps",
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["key"] == "agent_loop.default_max_steps"
    assert body["data"]["value"] == 12
    assert body["data"]["effectiveStatus"] == "active"


def test_runtime_config_changes_route_returns_scoped_history(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="workspace-1")
    patch = RuntimeConfigPatch(
        patch_id="patch-http-read-history",
        scope=scope,
        actor=_runtime_config_actor(),
        values={"logging.level": "DEBUG"},
        requested_at=_runtime_config_ts(),
    )

    with _runtime_config_transport_fixture(tmp_path / "runtime-config.db") as fixture:
        change = fixture.service.apply_patch(patch)

        response = fixture.transport.handle(
            HttpApiRequest(
                method="GET",
                path="/api/v1/runtime/config/changes?workspaceId=workspace-1",
            )
        )
        body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["schemaVersion"] == "plato.runtime_config_changes.v1"
    assert body["data"]["scope"] == {
        "level": "workspace",
        "workspaceId": "workspace-1",
        "sessionId": None,
        "taskId": None,
        "agentRunId": None,
    }
    assert body["data"]["totalCount"] == 1
    assert body["data"]["changes"][0]["changeId"] == change.change_id
    assert body["data"]["changes"][0]["acceptedValues"] == {"logging.level": "DEBUG"}


def test_runtime_config_snapshot_route_returns_snapshot_record(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="workspace-1")
    patch = RuntimeConfigPatch(
        patch_id="patch-http-read-snapshot",
        scope=scope,
        actor=_runtime_config_actor(),
        values={"logging.level": "DEBUG"},
        requested_at=_runtime_config_ts(),
    )

    with _runtime_config_transport_fixture(tmp_path / "runtime-config.db") as fixture:
        change = fixture.service.apply_patch(patch)
        assert change.resulting_config_hash is not None

        response = fixture.transport.handle(
            HttpApiRequest(
                method="GET",
                path=(
                    "/api/v1/runtime/config/snapshots/"
                    f"{change.resulting_config_hash}"
                ),
            )
        )
        body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["schemaVersion"] == "plato.runtime_config_snapshot.v1"
    assert body["data"]["snapshot"]["configHash"] == change.resulting_config_hash
    assert body["data"]["snapshot"]["createdByChangeId"] == change.change_id


def test_runtime_config_snapshot_route_returns_not_found_for_missing_hash() -> None:
    transport = _transport(runtime_config_gateway=DefaultRuntimeConfigGateway())

    response = transport.handle(
        HttpApiRequest(
            method="GET",
            path="/api/v1/runtime/config/snapshots/missing-hash",
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 404
    assert body["error"]["code"] == "not_found"
    assert body["error"]["details"]["configHash"] == "missing-hash"


def test_runtime_config_patch_route_accepts_and_persists_change(
    tmp_path: Path,
) -> None:
    with _runtime_config_transport_fixture(tmp_path / "runtime-config.db") as fixture:
        response = fixture.transport.handle(
            HttpApiRequest(
                method="PATCH",
                path="/api/v1/runtime/config",
                body={
                    "schemaVersion": "plato.runtime_config_patch_request.v1",
                    "idempotencyKey": "runtime-config-http-accepted",
                    "scope": {
                        "level": "workspace",
                        "workspaceId": "workspace-1",
                    },
                    "values": {"logging.level": "DEBUG"},
                    "reason": "enable debug logging",
                },
            )
        )
        body = _dict_body(response.body)

        changes = fixture.store.list_changes(
            RuntimeConfigScope(level="workspace", workspace_id="workspace-1")
        )

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["schemaVersion"] == "plato.runtime_config_patch_response.v1"
    assert body["data"]["change"]["status"] == "accepted"
    assert body["data"]["change"]["actor"] == {
        "actorType": "user",
        "actorId": "local-sidecar",
        "displayName": "Local Sidecar",
    }
    assert body["data"]["change"]["acceptedValues"] == {"logging.level": "DEBUG"}
    assert body["data"]["snapshotRef"]["configHash"] == (
        body["data"]["change"]["resultingConfigHash"]
    )
    assert body["data"]["replayed"] is False
    assert body["data"]["warnings"] == []
    assert len(changes) == 1


def test_runtime_config_patch_route_records_no_op(
    tmp_path: Path,
) -> None:
    with _runtime_config_transport_fixture(tmp_path / "runtime-config.db") as fixture:
        response = fixture.transport.handle(
            HttpApiRequest(
                method="PATCH",
                path="/api/v1/runtime/config",
                body={
                    "idempotencyKey": "runtime-config-http-no-op",
                    "scope": {
                        "level": "workspace",
                        "workspaceId": "workspace-1",
                    },
                    "values": {"agent_loop.default_max_steps": 20},
                },
            )
        )
        body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["change"]["status"] == "no_op"
    assert body["data"]["snapshotRef"]["configHash"] == (
        body["data"]["change"]["resultingConfigHash"]
    )


def test_runtime_config_patch_route_rejects_partial_by_default(
    tmp_path: Path,
) -> None:
    with _runtime_config_transport_fixture(tmp_path / "runtime-config.db") as fixture:
        response = fixture.transport.handle(
            HttpApiRequest(
                method="PATCH",
                path="/api/v1/runtime/config",
                body={
                    "idempotencyKey": "runtime-config-http-rejected",
                    "scope": {
                        "level": "workspace",
                        "workspaceId": "workspace-1",
                    },
                    "values": {
                        "logging.level": "DEBUG",
                        "unknown.key": "value",
                    },
                },
            )
        )
        body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["change"]["status"] == "rejected"
    assert body["data"]["change"]["acceptedValues"] == {}
    assert body["data"]["change"]["rejectedValues"]["unknown.key"]["code"] == (
        "unknown_key"
    )
    assert body["data"]["change"]["rejectedValues"]["logging.level"]["code"] == (
        "policy_denied"
    )
    assert body["data"]["snapshotRef"] is None


def test_runtime_config_patch_route_allows_explicit_partial_acceptance(
    tmp_path: Path,
) -> None:
    with _runtime_config_transport_fixture(tmp_path / "runtime-config.db") as fixture:
        response = fixture.transport.handle(
            HttpApiRequest(
                method="PATCH",
                path="/api/v1/runtime/config",
                body={
                    "idempotencyKey": "runtime-config-http-partial",
                    "scope": {
                        "level": "workspace",
                        "workspaceId": "workspace-1",
                    },
                    "values": {
                        "logging.level": "DEBUG",
                        "unknown.key": "value",
                    },
                    "allowPartialAcceptance": True,
                },
            )
        )
        body = _dict_body(response.body)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["change"]["status"] == "accepted"
    assert body["data"]["change"]["acceptedValues"] == {"logging.level": "DEBUG"}
    assert body["data"]["change"]["rejectedValues"]["unknown.key"]["code"] == (
        "unknown_key"
    )
    assert body["data"]["warnings"] == [
        {
            "code": "partial_acceptance",
            "message": "Runtime config patch was partially accepted.",
            "configKeys": ["unknown.key"],
        }
    ]


def test_runtime_config_patch_route_supports_dry_run_without_persistence(
    tmp_path: Path,
) -> None:
    scope = RuntimeConfigScope(level="workspace", workspace_id="workspace-1")
    with _runtime_config_transport_fixture(tmp_path / "runtime-config.db") as fixture:
        response = fixture.transport.handle(
            HttpApiRequest(
                method="PATCH",
                path="/api/v1/runtime/config",
                body={
                    "scope": {
                        "level": "workspace",
                        "workspaceId": "workspace-1",
                    },
                    "values": {"logging.level": "DEBUG"},
                    "dryRun": True,
                },
            )
        )
        body = _dict_body(response.body)
        changes = fixture.store.list_changes(scope)

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["data"]["change"]["status"] == "accepted"
    assert body["data"]["dryRun"] is True
    assert body["data"]["snapshotRef"] is None
    assert changes == ()


def test_runtime_config_patch_route_replays_matching_idempotency_key(
    tmp_path: Path,
) -> None:
    request_body = {
        "idempotencyKey": "runtime-config-http-replay",
        "scope": {
            "level": "workspace",
            "workspaceId": "workspace-1",
        },
        "values": {"logging.level": "DEBUG"},
    }
    with _runtime_config_transport_fixture(tmp_path / "runtime-config.db") as fixture:
        first_response = fixture.transport.handle(
            HttpApiRequest(
                method="PATCH",
                path="/api/v1/runtime/config",
                body=request_body,
            )
        )
        replay_response = fixture.transport.handle(
            HttpApiRequest(
                method="PATCH",
                path="/api/v1/runtime/config",
                body=request_body,
            )
        )
        first_body = _dict_body(first_response.body)
        replay_body = _dict_body(replay_response.body)
        changes = fixture.store.list_changes(
            RuntimeConfigScope(level="workspace", workspace_id="workspace-1")
        )

    assert replay_response.status_code == 200
    assert replay_body["data"]["replayed"] is True
    assert replay_body["data"]["change"]["changeId"] == (
        first_body["data"]["change"]["changeId"]
    )
    assert len(changes) == 1


def test_runtime_config_patch_route_rejects_idempotency_conflict(
    tmp_path: Path,
) -> None:
    with _runtime_config_transport_fixture(tmp_path / "runtime-config.db") as fixture:
        fixture.transport.handle(
            HttpApiRequest(
                method="PATCH",
                path="/api/v1/runtime/config",
                body={
                    "idempotencyKey": "runtime-config-http-conflict",
                    "scope": {
                        "level": "workspace",
                        "workspaceId": "workspace-1",
                    },
                    "values": {"logging.level": "DEBUG"},
                },
            )
        )
        response = fixture.transport.handle(
            HttpApiRequest(
                method="PATCH",
                path="/api/v1/runtime/config",
                body={
                    "idempotencyKey": "runtime-config-http-conflict",
                    "scope": {
                        "level": "workspace",
                        "workspaceId": "workspace-1",
                    },
                    "values": {"logging.level": "INFO"},
                },
            )
        )
        body = _dict_body(response.body)

    assert response.status_code == 409
    assert body["error"]["code"] == "idempotency_conflict"


def test_runtime_config_patch_route_requires_mutation_service() -> None:
    transport = _transport(runtime_config_gateway=DefaultRuntimeConfigGateway())

    response = transport.handle(
        HttpApiRequest(
            method="PATCH",
            path="/api/v1/runtime/config",
            body={
                "idempotencyKey": "runtime-config-http-missing-service",
                "scope": {"level": "workspace", "workspaceId": "workspace-1"},
                "values": {"logging.level": "DEBUG"},
            },
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 503
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["details"]["route"] == "runtime_config_patch"


def test_runtime_config_patch_route_requires_idempotency_key() -> None:
    with _runtime_config_transport_fixture(":memory:") as fixture:
        response = fixture.transport.handle(
            HttpApiRequest(
                method="PATCH",
                path="/api/v1/runtime/config",
                body={
                    "scope": {"level": "workspace", "workspaceId": "workspace-1"},
                    "values": {"logging.level": "DEBUG"},
                },
            )
        )
        body = _dict_body(response.body)

    assert response.status_code == 400
    assert body["error"]["code"] == "bad_request"


def test_runtime_config_routes_require_gateway() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(method="GET", path="/api/v1/runtime/config/effective")
    )
    body = _dict_body(response.body)

    assert response.status_code == 503
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["details"]["route"] == "runtime_config_effective"


def test_runtime_config_explain_requires_key() -> None:
    transport = _transport(runtime_config_gateway=DefaultRuntimeConfigGateway())

    response = transport.handle(
        HttpApiRequest(method="GET", path="/api/v1/runtime/config/explain")
    )
    body = _dict_body(response.body)

    assert response.status_code == 400
    assert body["error"]["code"] == "bad_request"

def test_runtime_config_explain_rejects_unknown_key() -> None:
    transport = _transport(runtime_config_gateway=DefaultRuntimeConfigGateway())

    response = transport.handle(
        HttpApiRequest(
            method="GET",
            path="/api/v1/runtime/config/explain?key=wechat.enabled",
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 400
    assert body["error"]["code"] == "bad_request"


def test_settings_config_route_patches_without_echoing_secret() -> None:
    settings = _SettingsConfigGateway()
    transport = _transport(settings_config_gateway=settings)

    response = transport.handle(
        HttpApiRequest(
            method="PATCH",
            path="/api/v1/settings/config",
            body={
                "llm": {
                    "provider": "deepseek",
                    "model": "deepseek-v4-pro",
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
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
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
                    env_vars=("DEEPSEEK_API_KEY", "LLM_API_KEY"),
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
                    "provider": "deepseek",
                    "model": "deepseek-v4-pro",
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


def test_session_activity_route_decodes_params_and_returns_contract_json() -> None:
    query = _QueryGateway()
    transport = _transport(query=query)

    response = transport.handle(
        HttpApiRequest(
            method="GET",
            path="/api/v1/sessions/session%201/activity?limit=2&cursor=4",
        )
    )
    body = _dict_body(response.body)

    assert response.status_code == 200
    assert query.activity_calls == [("session 1", 2, "4")]
    assert body["ok"] is True
    assert body["data"]["sessionId"] == "session 1"
    assert body["data"]["totalCount"] == 0


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
            "/api/v1/sessions/session%201/plans/plan%201/archive",
            _command_body("session 1", {"reason": "user archive"}),
            "archive_plan:plan 1",
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
