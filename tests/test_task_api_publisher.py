"""Tests for transport-neutral API Task publisher adapter."""

from __future__ import annotations

from dataclasses import dataclass

from taskweavn.task import (
    ApiAuthContext,
    ApiPublishPolicy,
    ApiPublishRequest,
    ApiRateLimitDecision,
    ApiRateLimiter,
    ApiTaskPublisher,
    DefaultApiTaskPublisher,
    DefaultTaskPublisher,
    InMemoryPublishIdempotencyStore,
    InMemoryTaskBus,
    StaticAgentCapabilityCatalog,
    StaticCapabilityCatalog,
    TaskPublishOptions,
    TaskPublishService,
)


def test_api_publisher_and_rate_limiter_protocol_conformance() -> None:
    adapter = _adapter()
    limiter = _RateLimiter(allowed=True)

    assert isinstance(adapter, ApiTaskPublisher)
    assert isinstance(limiter, ApiRateLimiter)


def test_preview_validates_without_publishing() -> None:
    bus = InMemoryTaskBus()
    adapter = _adapter(bus=bus)

    preview = adapter.preview(_request(), auth=_auth())

    assert preview.ok
    assert preview.task_count == 1
    assert preview.normalized_tree is not None
    assert preview.normalized_tree.source.kind == "api"
    assert bus.list_for_session("s1") == []


def test_publish_writes_api_task_tree() -> None:
    bus = InMemoryTaskBus()
    adapter = _adapter(bus=bus)

    result = adapter.publish(_request(), auth=_auth())
    task = bus.list_for_session("s1")[0]

    assert result.accepted
    assert task.dispatch_constraints is not None
    assert task.dispatch_constraints.metadata["publisher_kind"] == "api"
    assert task.dispatch_constraints.metadata["api_actor_id"] == "api-key-1"


def test_api_dry_run_publish_does_not_write_task_bus() -> None:
    bus = InMemoryTaskBus()
    adapter = _adapter(bus=bus)
    request = _request(options=TaskPublishOptions(dry_run=True, require_confirmation=False))

    result = adapter.publish(request, auth=_auth())

    assert result.skipped
    assert result.reason == "dry run"
    assert bus.list_for_session("s1") == []


def test_missing_idempotency_key_is_rejected_by_default() -> None:
    adapter = _adapter()

    result = adapter.publish(_request(idempotency_key=None), auth=_auth())

    assert result.skipped
    assert result.reason == "API publish requires idempotency_key"


def test_missing_idempotency_key_can_be_allowed_by_policy() -> None:
    bus = InMemoryTaskBus()
    adapter = _adapter(
        bus=bus,
        policy=ApiPublishPolicy(require_idempotency_key=False),
    )

    result = adapter.publish(_request(idempotency_key=None), auth=_auth())

    assert result.accepted
    assert len(bus.list_for_session("s1")) == 1


def test_session_allowlist_rejects_unauthorized_session() -> None:
    adapter = _adapter()

    preview = adapter.preview(
        _request(session_id="s2"),
        auth=_auth(allowed_session_ids=("s1",)),
    )
    result = adapter.publish(
        _request(session_id="s2"),
        auth=_auth(allowed_session_ids=("s1",)),
    )

    assert not preview.ok
    assert "cannot publish to session" in preview.errors[0]
    assert result.skipped
    assert "cannot publish to session" in (result.reason or "")


def test_capability_allowlist_rejects_unauthorized_capability() -> None:
    adapter = _adapter(
        policy=ApiPublishPolicy(allowed_capabilities=("summarize",)),
    )

    request = _request(capability="testing", agent="agent.test")

    preview = adapter.preview(request, auth=_auth())
    result = adapter.publish(request, auth=_auth())

    assert not preview.ok
    assert "capability 'testing' is not allowed" in preview.errors[0]
    assert result.skipped
    assert "capability 'testing' is not allowed" in (result.reason or "")


def test_agent_allowlist_rejects_unauthorized_agent() -> None:
    adapter = _adapter(
        policy=ApiPublishPolicy(allowed_agent_refs=("agent.summary",)),
    )

    result = adapter.publish(_request(agent="agent.test"), auth=_auth())

    assert result.skipped
    assert "agent 'agent.test' is not allowed" in (result.reason or "")


def test_catalog_validation_rejects_unknown_capability() -> None:
    adapter = _adapter(capabilities=("summarize",))

    preview = adapter.preview(_request(capability="testing"), auth=_auth())

    assert not preview.ok
    assert "unknown capability 'testing'" in preview.errors[0]


def test_catalog_validation_rejects_agent_capability_mismatch() -> None:
    adapter = _adapter(
        capabilities=("testing", "summarize"),
        agents={"agent.summary": ("summarize",)},
    )

    result = adapter.publish(_request(capability="testing", agent="agent.summary"), auth=_auth())

    assert result.skipped
    assert "does not support capability 'testing'" in (result.reason or "")


def test_rate_limiter_rejects_publish_without_blocking_preview() -> None:
    bus = InMemoryTaskBus()
    adapter = _adapter(
        bus=bus,
        rate_limiter=_RateLimiter(allowed=False, reason="too many API publishes"),
    )

    preview = adapter.preview(_request(), auth=_auth())
    result = adapter.publish(_request(), auth=_auth())

    assert preview.ok
    assert result.skipped
    assert result.reason == "too many API publishes"
    assert bus.list_for_session("s1") == []


def test_invalid_task_tree_returns_rejected_preview_and_publish_result() -> None:
    adapter = _adapter()
    request = ApiPublishRequest(
        session_id="s1",
        task_tree={"tasks": [{"id": "bad", "title": "Bad"}]},
        idempotency_key="api-1",
    )

    preview = adapter.preview(request, auth=_auth())
    result = adapter.publish(request, auth=_auth())

    assert not preview.ok
    assert "requires required_capability or capability" in preview.errors[0]
    assert result.skipped
    assert "requires required_capability or capability" in (result.reason or "")


@dataclass(frozen=True)
class _RateLimiter:
    allowed: bool
    reason: str | None = None

    def check(self, auth: ApiAuthContext, request: ApiPublishRequest) -> ApiRateLimitDecision:  # noqa: ARG002
        return ApiRateLimitDecision(allowed=self.allowed, reason=self.reason)


def _adapter(
    *,
    bus: InMemoryTaskBus | None = None,
    policy: ApiPublishPolicy | None = None,
    capabilities: tuple[str, ...] = ("summarize", "testing"),
    agents: dict[str, tuple[str, ...]] | None = None,
    rate_limiter: ApiRateLimiter | None = None,
) -> DefaultApiTaskPublisher:
    bus = bus or InMemoryTaskBus()
    service = TaskPublishService(
        publisher=DefaultTaskPublisher(task_bus=bus),
        idempotency_store=InMemoryPublishIdempotencyStore(),
    )
    agent_bindings = agents or {
        "agent.summary": ("summarize",),
        "agent.test": ("testing",),
    }
    return DefaultApiTaskPublisher(
        publish_service=service,
        policy=policy,
        capability_catalog=StaticCapabilityCatalog(capabilities),
        agent_catalog=StaticAgentCapabilityCatalog(
            [
                {"agent_ref": agent_ref, "capabilities": agent_capabilities}
                for agent_ref, agent_capabilities in agent_bindings.items()
            ]
        ),
        rate_limiter=rate_limiter,
    )


def _request(
    *,
    session_id: str = "s1",
    idempotency_key: str | None = "api-1",
    capability: str = "summarize",
    agent: str = "agent.summary",
    options: TaskPublishOptions | None = None,
) -> ApiPublishRequest:
    return ApiPublishRequest(
        session_id=session_id,
        source_id="external-job-1",
        idempotency_key=idempotency_key,
        task_tree={
            "tasks": [
                {
                    "id": "summary",
                    "title": "Summary",
                    "intent": "Summarize session",
                    "capability": capability,
                    "agent": agent,
                }
            ]
        },
        options=options or TaskPublishOptions(require_confirmation=False),
    )


def _auth(
    *,
    allowed_session_ids: tuple[str, ...] = (),
    allowed_capabilities: tuple[str, ...] = (),
    allowed_agent_refs: tuple[str, ...] = (),
) -> ApiAuthContext:
    return ApiAuthContext(
        actor_id="api-key-1",
        allowed_session_ids=allowed_session_ids,
        allowed_capabilities=allowed_capabilities,
        allowed_agent_refs=allowed_agent_refs,
    )
