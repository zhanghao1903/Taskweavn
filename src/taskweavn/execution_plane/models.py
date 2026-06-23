"""Service-level Execution Plane contract models.

These models intentionally sit above the current TaskBus implementation. Plato
Session/Plan/TaskNode facts may map into them, but external callers should not
need to know Plato UI contract shapes to publish or query executable work.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

TaskRequesterKind = Literal["plato", "external_app", "system", "test"]
TaskExecutionStatus = Literal[
    "accepted",
    "pending",
    "claimed",
    "running",
    "waiting_for_user",
    "done",
    "failed",
    "cancelled",
    "lease_expired",
    "rejected",
]
TaskEventKind = Literal[
    "task.accepted",
    "task.claimed",
    "task.started",
    "task.progress",
    "task.waiting_for_user",
    "task.result_ready",
    "task.failed",
    "task.cancelled",
    "task.lease_expired",
    "task.evidence_added",
]
EvidenceKind = Literal[
    "result_summary",
    "error_summary",
    "file_change_summary",
    "tool_observation",
    "screenshot",
    "text_extract",
    "diff",
    "audit_record",
]
CallbackMode = Literal["none", "poll", "sse", "webhook"]
ExecutionEnvStatus = Literal["online", "offline", "draining", "disabled"]
TaskLeaseStatus = Literal["active", "released", "expired", "revoked"]
RiskLevel = Literal["low", "medium", "high"]
EvidenceVisibility = Literal["visible", "permission_limited", "hidden"]

JsonObject = dict[str, Any]


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class ExecutionPlaneModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        validate_assignment=True,
    )


class TaskRequester(ExecutionPlaneModel):
    kind: TaskRequesterKind
    id: str = Field(min_length=1)
    display_name: str | None = Field(default=None, min_length=1)
    trust_scope: str | None = Field(default=None, min_length=1)

    @property
    def scoped_id(self) -> str:
        return f"{self.kind}:{self.id}"


class ExternalRef(ExecutionPlaneModel):
    system: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    id: str = Field(min_length=1)
    url: str | None = Field(default=None, min_length=1)


class CapabilityPolicy(ExecutionPlaneModel):
    required_capability: str = Field(min_length=1)
    allowed_tools: tuple[str, ...] = ()
    denied_tools: tuple[str, ...] = ()
    requires_human_confirmation: bool = False
    max_runtime_seconds: int | None = Field(default=None, gt=0)
    max_llm_tokens: int | None = Field(default=None, gt=0)
    workspace_scope: str | None = Field(default=None, min_length=1)
    risk_level: RiskLevel = "medium"

    @model_validator(mode="after")
    def _validate_tool_sets(self) -> CapabilityPolicy:
        overlap = set(self.allowed_tools).intersection(self.denied_tools)
        if overlap:
            raise ValueError("allowed_tools and denied_tools must not overlap")
        return self


class EvidenceRequirement(ExecutionPlaneModel):
    required: tuple[EvidenceKind, ...] = ("result_summary",)
    optional: tuple[EvidenceKind, ...] = ()
    retention_policy: str | None = Field(default=None, min_length=1)
    redact_for_diagnostics: bool = True


class CallbackPolicy(ExecutionPlaneModel):
    mode: CallbackMode = "none"
    url: str | None = Field(default=None, min_length=1)
    signing_key_ref: str | None = Field(default=None, min_length=1)
    event_kinds: tuple[TaskEventKind, ...] = ()

    @model_validator(mode="after")
    def _validate_callback_url(self) -> CallbackPolicy:
        if self.mode == "webhook" and self.url is None:
            raise ValueError("webhook callback requires url")
        if self.mode != "webhook" and self.signing_key_ref is not None:
            raise ValueError("signing_key_ref is only valid for webhook callbacks")
        return self


class TaskRequest(ExecutionPlaneModel):
    idempotency_key: str = Field(min_length=1)
    requester: TaskRequester
    external_ref: ExternalRef | None = None
    task_type: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_.:-]+$")
    intent: str = Field(min_length=1)
    input: JsonObject = Field(default_factory=dict)
    policy: CapabilityPolicy
    evidence: EvidenceRequirement = Field(default_factory=EvidenceRequirement)
    callback: CallbackPolicy = Field(default_factory=CallbackPolicy)
    metadata: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_task_request(self) -> TaskRequest:
        if self.task_type.count(".") < 1:
            raise ValueError("task_type must be namespaced, for example plato.default")
        if self.requester.kind == "external_app" and self.task_type.startswith("plato."):
            raise ValueError("external_app requester cannot publish plato.* task types")
        return self


class TaskExecution(ExecutionPlaneModel):
    execution_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    status: TaskExecutionStatus
    requester: TaskRequester
    external_ref: ExternalRef | None = None
    task_type: str = Field(min_length=1)
    required_capability: str = Field(min_length=1)
    env_id: str | None = Field(default=None, min_length=1)
    lease_id: str | None = Field(default=None, min_length=1)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_ref: str | None = Field(default=None, min_length=1)
    error_ref: str | None = Field(default=None, min_length=1)
    evidence_refs: tuple[str, ...] = ()
    session_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_execution_timestamps(self) -> TaskExecution:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        if self.completed_at is not None and self.completed_at < self.created_at:
            raise ValueError("completed_at must be >= created_at")
        return self


class TaskEvent(ExecutionPlaneModel):
    event_id: str = Field(default_factory=lambda: new_id("event"), min_length=1)
    execution_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    kind: TaskEventKind
    occurred_at: datetime = Field(default_factory=utcnow)
    summary: str = Field(min_length=1)
    data: JsonObject = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()


class TaskEventQuery(ExecutionPlaneModel):
    limit: int = Field(default=100, ge=1, le=500)
    cursor: str | None = Field(default=None, min_length=1)


class TaskEventPage(ExecutionPlaneModel):
    items: tuple[TaskEvent, ...]
    next_cursor: str | None = Field(default=None, min_length=1)


class TaskResult(ExecutionPlaneModel):
    result_ref: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    structured_payload: JsonObject = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utcnow)


class TaskError(ExecutionPlaneModel):
    error_ref: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool
    recovery_hint: str | None = Field(default=None, min_length=1)
    evidence_refs: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utcnow)


class EvidenceRef(ExecutionPlaneModel):
    evidence_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    kind: EvidenceKind
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    uri: str | None = Field(default=None, min_length=1)
    object_ref: JsonObject = Field(default_factory=dict)
    visibility: EvidenceVisibility = "visible"
    created_at: datetime = Field(default_factory=utcnow)


class EvidencePage(ExecutionPlaneModel):
    items: tuple[EvidenceRef, ...]
    next_cursor: str | None = Field(default=None, min_length=1)


class ExecutionEnv(ExecutionPlaneModel):
    env_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    status: ExecutionEnvStatus = "online"
    capabilities: tuple[str, ...] = ()
    tool_pool: tuple[str, ...] = ()
    permission_profile_id: str | None = Field(default=None, min_length=1)
    workspace_scope: str | None = Field(default=None, min_length=1)
    active_execution_id: str | None = Field(default=None, min_length=1)
    last_heartbeat_at: datetime | None = None
    runtime_version: str | None = Field(default=None, min_length=1)

    def supports(self, policy: CapabilityPolicy) -> bool:
        if self.status != "online":
            return False
        if policy.required_capability not in self.capabilities:
            return False
        if policy.allowed_tools:
            return set(policy.allowed_tools).issubset(self.tool_pool)
        return True


class TaskLease(ExecutionPlaneModel):
    lease_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    env_id: str = Field(min_length=1)
    status: TaskLeaseStatus = "active"
    claimed_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    renewed_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_lease_timestamps(self) -> TaskLease:
        if self.expires_at <= self.claimed_at:
            raise ValueError("expires_at must be after claimed_at")
        if self.renewed_at is not None and self.renewed_at < self.claimed_at:
            raise ValueError("renewed_at must be >= claimed_at")
        return self


class CancelTaskCommand(ExecutionPlaneModel):
    command_id: str = Field(default_factory=lambda: new_id("cancel"), min_length=1)
    reason: str = Field(default="cancel requested", min_length=1)


class RetryTaskCommand(ExecutionPlaneModel):
    command_id: str = Field(default_factory=lambda: new_id("retry"), min_length=1)
    instruction: str | None = Field(default=None, min_length=1)
