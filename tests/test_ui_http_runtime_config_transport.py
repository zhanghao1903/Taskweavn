"""Runtime config route tests for the framework-neutral Plato UI HTTP transport."""

from __future__ import annotations

from pathlib import Path

from taskweavn.runtime_config import (
    RuntimeConfigPatch,
    RuntimeConfigScope,
)
from taskweavn.server import HttpApiRequest
from taskweavn.server.runtime_config_gateway import DefaultRuntimeConfigGateway
from tests.fixtures.ui_http_transport import (
    _dict_body,
    _runtime_config_actor,
    _runtime_config_transport_fixture,
    _runtime_config_ts,
    _transport,
)


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
