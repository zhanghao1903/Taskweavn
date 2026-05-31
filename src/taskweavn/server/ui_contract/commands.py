"""Command payload models for Plato UI command requests."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from taskweavn.server.ui_contract.base import UiContractModel


class AppendSessionInputPayload(UiContractModel):
    content: str = Field(min_length=1)
    mode: Literal["global_guidance", "generate_task_tree"]


class GenerateTaskTreePayload(UiContractModel):
    prompt: str | None = Field(default=None, min_length=1)
    raw_task_id: str | None = Field(default=None, min_length=1)
    context: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_source(self) -> GenerateTaskTreePayload:
        if self.prompt is None and self.raw_task_id is None:
            raise ValueError("generate task tree requires prompt or raw_task_id")
        return self


class UpdateTaskNodePayload(UiContractModel):
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = Field(default=None, min_length=1)
    full_intent: str | None = Field(default=None, min_length=1)
    constraints: tuple[str, ...] | None = None
    update_mode: Literal["node_fields", "replace_children", "replace_subtree"] = (
        "node_fields"
    )
    preserve_root_id: bool = True

    @model_validator(mode="after")
    def _validate_non_empty_patch(self) -> UpdateTaskNodePayload:
        if (
            self.title is None
            and self.summary is None
            and self.full_intent is None
            and self.constraints is None
        ):
            raise ValueError("update task node payload must contain at least one field")
        return self


class AppendTaskInputPayload(UiContractModel):
    content: str = Field(min_length=1)
    mode: Literal["guidance", "revision_request", "clarification_answer"]


class PublishTaskTreePayload(UiContractModel):
    task_tree_id: str | None = Field(default=None, min_length=1)
    start_immediately: bool = True


class RetryTaskPayload(UiContractModel):
    instruction: str | None = Field(default=None, min_length=1)
    start_immediately: bool = True


class DispatchExecutionPayload(UiContractModel):
    reason: Literal["manual_control_route"] = "manual_control_route"


class ResolveConfirmationPayload(UiContractModel):
    value: str = Field(min_length=1)
    note: str | None = Field(default=None, min_length=1)
