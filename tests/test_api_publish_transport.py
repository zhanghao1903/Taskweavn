"""Tests for framework-neutral API publish HTTP transport."""

from __future__ import annotations

from pathlib import Path

from taskweavn.server import ApiPublishHttpTransport, HttpApiRequest
from taskweavn.task import (
    DefaultApiTaskPublisher,
    InMemoryTaskBus,
    SqliteTaskBus,
    StaticAgentCapabilityCatalog,
    StaticCapabilityCatalog,
    build_sqlite_publish_service,
)


def test_preview_route_returns_enveloped_preview_without_publishing() -> None:
    bus = InMemoryTaskBus()
    transport = _transport(bus=bus)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/sessions/s1/api-publish/preview",
            headers={"x-taskweavn-actor-id": "api-key-1"},
            body=_body(idempotency_key=None),
        )
    )

    assert response.status_code == 200
    assert response.body["ok"] is True
    assert response.body["data"]["valid"] is True
    assert response.body["data"]["task_count"] == 1
    assert bus.list_for_session("s1") == []


def test_publish_route_writes_task_and_uses_path_session() -> None:
    bus = InMemoryTaskBus()
    transport = _transport(bus=bus)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/sessions/s1/api-publish",
            headers={"x-taskweavn-actor-id": "api-key-1"},
            body=_body(),
        )
    )

    assert response.status_code == 200
    assert response.body["ok"] is True
    assert response.body["data"]["session_id"] == "s1"
    assert response.body["data"]["skipped"] is False
    assert len(bus.list_for_session("s1")) == 1


def test_idempotency_key_can_come_from_header() -> None:
    bus = InMemoryTaskBus()
    transport = _transport(bus=bus)

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/sessions/s1/api-publish",
            headers={
                "x-taskweavn-actor-id": "api-key-1",
                "idempotency-key": "api-header-key",
            },
            body=_body(idempotency_key=None),
        )
    )

    assert response.status_code == 200
    assert response.body["data"]["idempotency_key"] == "api-header-key"


def test_transport_rejects_missing_actor_header() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/sessions/s1/api-publish",
            body=_body(),
        )
    )

    assert response.status_code == 401
    assert response.body["ok"] is False
    assert response.body["error"]["code"] == "missing_actor"


def test_transport_rejects_session_mismatch() -> None:
    transport = _transport()
    body = _body()
    body["session_id"] = "other-session"

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/sessions/s1/api-publish",
            headers={"x-taskweavn-actor-id": "api-key-1"},
            body=body,
        )
    )

    assert response.status_code == 400
    assert response.body["error"]["code"] == "session_mismatch"


def test_transport_rejects_wrong_method_and_unknown_path() -> None:
    transport = _transport()

    wrong_method = transport.handle(
        HttpApiRequest(
            method="GET",
            path="/sessions/s1/api-publish",
            headers={"x-taskweavn-actor-id": "api-key-1"},
            body=_body(),
        )
    )
    unknown = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/sessions/s1/unknown",
            headers={"x-taskweavn-actor-id": "api-key-1"},
            body=_body(),
        )
    )

    assert wrong_method.status_code == 405
    assert wrong_method.headers["allow"] == "POST"
    assert unknown.status_code == 404


def test_transport_rejects_invalid_body() -> None:
    transport = _transport()

    response = transport.handle(
        HttpApiRequest(
            method="POST",
            path="/sessions/s1/api-publish",
            headers={"x-taskweavn-actor-id": "api-key-1"},
            body={"source_id": "external-job-1"},
        )
    )

    assert response.status_code == 400
    assert response.body["error"]["code"] == "invalid_body"
    assert response.body["error"]["details"]["errors"]


def test_transport_with_sqlite_service_replays_after_reopen(tmp_path: Path) -> None:
    task_db = tmp_path / "tasks.sqlite"
    publish_db = tmp_path / "publish.sqlite"
    first_bus = SqliteTaskBus(task_db)
    try:
        first_transport = _transport(
            service_bus=first_bus,
            publish_db_path=publish_db,
        )
        first = first_transport.handle(
            HttpApiRequest(
                method="POST",
                path="/sessions/s1/api-publish",
                headers={"x-taskweavn-actor-id": "api-key-1"},
                body=_body(),
            )
        )

        assert first.status_code == 200
        assert first.body["data"]["skipped"] is False
    finally:
        first_bus.close()

    second_bus = SqliteTaskBus(task_db)
    try:
        second_transport = _transport(
            service_bus=second_bus,
            publish_db_path=publish_db,
        )
        replay = second_transport.handle(
            HttpApiRequest(
                method="POST",
                path="/sessions/s1/api-publish",
                headers={"x-taskweavn-actor-id": "api-key-1"},
                body=_body(),
            )
        )

        assert replay.status_code == 200
        assert replay.body["data"] == first.body["data"]
        assert len(second_bus.list_for_session("s1")) == 1
    finally:
        second_bus.close()


def _transport(
    *,
    bus: InMemoryTaskBus | None = None,
    service_bus: SqliteTaskBus | None = None,
    publish_db_path: Path | None = None,
) -> ApiPublishHttpTransport:
    if service_bus is not None:
        assert publish_db_path is not None
        publish_service = build_sqlite_publish_service(
            task_bus=service_bus,
            publish_db_path=publish_db_path,
        )
    else:
        publish_service = build_sqlite_publish_service(
            task_bus=bus or InMemoryTaskBus(),
            publish_db_path=Path(":memory:"),
        )
    return ApiPublishHttpTransport(
        DefaultApiTaskPublisher(
            publish_service=publish_service,
            capability_catalog=StaticCapabilityCatalog(("summarize", "testing")),
            agent_catalog=StaticAgentCapabilityCatalog(
                [
                    {"agent_ref": "agent.summary", "capabilities": ("summarize",)},
                    {"agent_ref": "agent.test", "capabilities": ("testing",)},
                ]
            ),
        )
    )


def _body(*, idempotency_key: str | None = "api-1") -> dict[str, object]:
    body: dict[str, object] = {
        "source_id": "external-job-1",
        "task_tree": {
            "tasks": [
                {
                    "id": "summary",
                    "title": "Summary",
                    "intent": "Summarize session",
                    "capability": "summarize",
                    "agent": "agent.summary",
                }
            ]
        },
    }
    if idempotency_key is not None:
        body["idempotency_key"] = idempotency_key
    return body
