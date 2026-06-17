"""Tests for Execution Plane service-level contract models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from taskweavn.execution_plane import (
    CapabilityPolicy,
    ExecutionEnv,
    TaskRequest,
)


def test_task_request_accepts_service_level_shape_without_plato_session_fields() -> None:
    request = TaskRequest.model_validate(
        {
            "idempotencyKey": "crm:outreach:inf-123",
            "requester": {"kind": "external_app", "id": "ops-crm"},
            "externalRef": {
                "system": "ops-crm",
                "kind": "influencer",
                "id": "inf-123",
            },
            "taskType": "ecommerce.outreach.email_draft",
            "intent": "Draft a sample collaboration email.",
            "input": {"creatorName": "Test Creator"},
            "policy": {
                "requiredCapability": "outreach.email_draft",
                "allowedTools": ["browser_read", "email_draft"],
                "requiresHumanConfirmation": True,
            },
            "evidence": {
                "required": ["result_summary"],
                "optional": ["tool_observation"],
            },
        }
    )

    assert request.requester.scoped_id == "external_app:ops-crm"
    assert request.external_ref is not None
    assert request.external_ref.system == "ops-crm"
    assert request.policy.required_capability == "outreach.email_draft"
    assert request.model_dump(mode="json", by_alias=True)["idempotencyKey"] == (
        "crm:outreach:inf-123"
    )


def test_external_app_cannot_publish_plato_internal_task_type() -> None:
    with pytest.raises(ValidationError, match="external_app requester"):
        TaskRequest.model_validate(
            {
                "idempotencyKey": "key-1",
                "requester": {"kind": "external_app", "id": "ops-crm"},
                "taskType": "plato.default_execution",
                "intent": "Run a Plato internal task.",
                "policy": {"requiredCapability": "execute"},
            }
        )


def test_task_request_requires_namespaced_task_type() -> None:
    with pytest.raises(ValidationError, match="task_type must be namespaced"):
        TaskRequest.model_validate(
            {
                "idempotencyKey": "key-1",
                "requester": {"kind": "plato", "id": "workspace:local"},
                "taskType": "default",
                "intent": "Run a task.",
                "policy": {"requiredCapability": "execute"},
            }
        )


def test_capability_policy_rejects_allowed_and_denied_tool_overlap() -> None:
    with pytest.raises(ValidationError, match="must not overlap"):
        CapabilityPolicy(
            required_capability="execute",
            allowed_tools=("file_write",),
            denied_tools=("file_write",),
        )


def test_execution_env_supports_required_capability_and_allowed_tools() -> None:
    env = ExecutionEnv(
        env_id="local-default",
        display_name="Local",
        capabilities=("execute",),
        tool_pool=("file_read", "file_write"),
    )

    assert env.supports(
        CapabilityPolicy(
            required_capability="execute",
            allowed_tools=("file_read",),
        )
    )
    assert not env.supports(
        CapabilityPolicy(
            required_capability="execute",
            allowed_tools=("shell",),
        )
    )
    assert not env.model_copy(update={"status": "offline"}).supports(
        CapabilityPolicy(required_capability="execute")
    )
