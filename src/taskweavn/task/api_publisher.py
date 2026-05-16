"""Transport-neutral API publisher adapter."""

from __future__ import annotations

from typing import Any, ClassVar, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from taskweavn.task.authoring import CapabilityCatalog
from taskweavn.task.publisher import (
    PublisherRef,
    PublishPreview,
    PublishRequest,
    PublishResult,
    PublishSource,
    TaskPublishOptions,
)
from taskweavn.task.publisher_input import (
    AgentCapabilityCatalog,
    TaskTreeInputError,
    TaskTreeInputValidator,
    normalize_task_tree_input,
)
from taskweavn.task.publisher_service import TaskPublishService


def _new_id() -> str:
    return uuid4().hex


class _FrozenApiModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class ApiAuthContext(_FrozenApiModel):
    """Authenticated API caller context.

    Empty allowlists mean "not constrained at this layer"; deployments can
    narrow these per token/user without changing the publish adapter.
    """

    actor_id: str = Field(min_length=1)
    allowed_session_ids: tuple[str, ...] = ()
    allowed_capabilities: tuple[str, ...] = ()
    allowed_agent_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    def allows_session(self, session_id: str) -> bool:
        return not self.allowed_session_ids or session_id in self.allowed_session_ids


class ApiPublishPolicy(_FrozenApiModel):
    """Deployment-level API publish policy."""

    require_idempotency_key: bool = True
    allowed_capabilities: tuple[str, ...] = ()
    allowed_agent_refs: tuple[str, ...] = ()


class ApiRateLimitDecision(_FrozenApiModel):
    allowed: bool
    reason: str | None = Field(default=None, min_length=1)


@runtime_checkable
class ApiRateLimiter(Protocol):
    """Hook for API rate limiting before publish semantics run."""

    def check(self, auth: ApiAuthContext, request: ApiPublishRequest) -> ApiRateLimitDecision:
        ...


class AllowAllApiRateLimiter:
    """Default no-op rate limiter used until an HTTP layer is introduced."""

    def check(self, auth: ApiAuthContext, request: ApiPublishRequest) -> ApiRateLimitDecision:  # noqa: ARG002
        return ApiRateLimitDecision(allowed=True)


class ApiPublishRequest(_FrozenApiModel):
    """Transport-neutral request accepted by API publisher endpoints."""

    request_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    task_tree: dict[str, Any]
    source_id: str | None = Field(default=None, min_length=1)
    idempotency_key: str | None = Field(default=None, min_length=1)
    options: TaskPublishOptions = Field(
        default_factory=lambda: TaskPublishOptions(require_confirmation=False)
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class ApiTaskPublisher(Protocol):
    """Stable semantic entrypoint for future HTTP/RPC API publishing."""

    def preview(self, request: ApiPublishRequest, *, auth: ApiAuthContext) -> PublishPreview:
        ...

    def publish(self, request: ApiPublishRequest, *, auth: ApiAuthContext) -> PublishResult:
        ...


class DefaultApiTaskPublisher:
    """Default API adapter layered above TaskPublishService."""

    def __init__(
        self,
        *,
        publish_service: TaskPublishService,
        policy: ApiPublishPolicy | None = None,
        capability_catalog: CapabilityCatalog | None = None,
        agent_catalog: AgentCapabilityCatalog | None = None,
        rate_limiter: ApiRateLimiter | None = None,
    ) -> None:
        self._publish_service = publish_service
        self._policy = policy or ApiPublishPolicy()
        self._validator = TaskTreeInputValidator(
            capability_catalog=capability_catalog,
            agent_catalog=agent_catalog,
        )
        self._rate_limiter = rate_limiter or AllowAllApiRateLimiter()

    def preview(self, request: ApiPublishRequest, *, auth: ApiAuthContext) -> PublishPreview:
        build = self._build_publish_request(request, auth=auth, require_idempotency=False)
        if isinstance(build, PublishPreview):
            return build
        return self._publish_service.preview(build)

    def publish(self, request: ApiPublishRequest, *, auth: ApiAuthContext) -> PublishResult:
        if self._policy.require_idempotency_key and request.idempotency_key is None:
            return _publish_rejected(request, auth, "API publish requires idempotency_key")
        build = self._build_publish_request(request, auth=auth, require_idempotency=True)
        if isinstance(build, PublishPreview):
            return _publish_rejected(request, auth, "; ".join(build.errors))
        return self._publish_service.publish(build)

    def _build_publish_request(
        self,
        request: ApiPublishRequest,
        *,
        auth: ApiAuthContext,
        require_idempotency: bool,
    ) -> PublishRequest | PublishPreview:
        permission_errors = self._permission_errors(request, auth=auth)
        if permission_errors:
            return _preview_rejected(request, auth, permission_errors)
        if require_idempotency:
            rate_limit = self._rate_limiter.check(auth, request)
            if not rate_limit.allowed:
                return _preview_rejected(
                    request,
                    auth,
                    (rate_limit.reason or "API rate limit exceeded",),
                )

        publisher = PublisherRef(kind="api", actor_id=auth.actor_id)
        try:
            tree = normalize_task_tree_input(
                request.task_tree,
                publisher=publisher,
                source_ref=request.source_id,
                metadata={
                    "api_actor_id": auth.actor_id,
                    **request.metadata,
                },
            )
        except (TaskTreeInputError, ValueError) as exc:
            return _preview_rejected(request, auth, (str(exc),))

        validation = self._validator.validate(tree)
        errors = tuple(issue.message for issue in validation.errors)
        errors += _tree_policy_errors(
            tree.iter_nodes(),
            auth=auth,
            policy=self._policy,
        )
        if errors:
            return PublishPreview(
                request_id=request.request_id,
                session_id=request.session_id,
                publisher=publisher,
                normalized_tree=tree,
                valid=False,
                errors=errors,
                root_count=len(tree.root_nodes),
                task_count=tree.task_count,
            )

        return PublishRequest(
            request_id=request.request_id,
            session_id=request.session_id,
            publisher=publisher,
            source=PublishSource(
                source_type="api",
                source_id=request.source_id,
                metadata={
                    "api_actor_id": auth.actor_id,
                    "auth_metadata": dict(auth.metadata),
                },
            ),
            task_tree=tree,
            options=request.options,
            idempotency_key=request.idempotency_key,
        )

    def _permission_errors(
        self,
        request: ApiPublishRequest,
        *,
        auth: ApiAuthContext,
    ) -> tuple[str, ...]:
        errors: list[str] = []
        if not auth.allows_session(request.session_id):
            errors.append(
                f"actor {auth.actor_id!r} cannot publish to session {request.session_id!r}"
            )
        return tuple(errors)


def _tree_policy_errors(
    nodes: tuple[Any, ...],
    *,
    auth: ApiAuthContext,
    policy: ApiPublishPolicy,
) -> tuple[str, ...]:
    capability_allowlist = _merge_allowlists(auth.allowed_capabilities, policy.allowed_capabilities)
    agent_allowlist = _merge_allowlists(auth.allowed_agent_refs, policy.allowed_agent_refs)
    errors: list[str] = []
    for node in nodes:
        if capability_allowlist and node.required_capability not in capability_allowlist:
            errors.append(
                f"capability {node.required_capability!r} is not allowed for API publish"
            )
        if node.agent_ref is not None and agent_allowlist and node.agent_ref not in agent_allowlist:
            errors.append(f"agent {node.agent_ref!r} is not allowed for API publish")
    return tuple(errors)


def _merge_allowlists(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    if not left:
        return right
    if not right:
        return left
    return tuple(value for value in left if value in set(right))


def _preview_rejected(
    request: ApiPublishRequest,
    auth: ApiAuthContext,
    errors: tuple[str, ...],
) -> PublishPreview:
    return PublishPreview(
        request_id=request.request_id,
        session_id=request.session_id,
        publisher=PublisherRef(kind="api", actor_id=auth.actor_id),
        valid=False,
        errors=errors,
    )


def _publish_rejected(
    request: ApiPublishRequest,
    auth: ApiAuthContext,
    reason: str,
) -> PublishResult:
    return PublishResult(
        request_id=request.request_id,
        session_id=request.session_id,
        publisher=PublisherRef(kind="api", actor_id=auth.actor_id),
        skipped=True,
        reason=reason or "API publish rejected",
        idempotency_key=request.idempotency_key,
    )


__all__ = [
    "AllowAllApiRateLimiter",
    "ApiAuthContext",
    "ApiPublishPolicy",
    "ApiPublishRequest",
    "ApiRateLimitDecision",
    "ApiRateLimiter",
    "ApiTaskPublisher",
    "DefaultApiTaskPublisher",
]
