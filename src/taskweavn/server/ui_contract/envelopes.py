"""Query and command envelopes for the Plato UI contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import Field, model_validator

from taskweavn.server.ui_contract.base import UiContractModel, utcnow
from taskweavn.server.ui_contract.errors import ApiError
from taskweavn.server.ui_contract.refs import AffectedObjectRef, AffectedScope, ObjectRef
from taskweavn.task.models import TaskRef

CommandStatus = Literal["accepted", "rejected"]


def _new_id() -> str:
    return uuid4().hex


class QueryResponse[T](UiContractModel):
    request_id: str = Field(default_factory=_new_id, min_length=1)
    ok: bool
    data: T | None
    error: ApiError | None = None
    cursor: str | None = None
    generated_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _validate_envelope(self) -> QueryResponse[T]:
        if self.ok:
            if self.data is None:
                raise ValueError("successful QueryResponse requires data")
            if self.error is not None:
                raise ValueError("successful QueryResponse must not include error")
        elif self.error is None:
            raise ValueError("failed QueryResponse requires error")
        return self


class CommandRequest[T](UiContractModel):
    command_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    idempotency_key: str | None = Field(default=None, min_length=1)
    expected_version: int | None = Field(default=None, ge=1)
    payload: T


class CommandResult(UiContractModel):
    command_id: str = Field(default_factory=_new_id, min_length=1)
    status: CommandStatus
    message: str = Field(min_length=1)
    affected_task_refs: tuple[TaskRef, ...] = ()
    object_refs: tuple[ObjectRef, ...] = ()
    affected_objects: tuple[AffectedObjectRef, ...] = ()
    emitted_message_ids: tuple[str, ...] = ()
    published_task_ids: tuple[str, ...] = ()
    debug_refs: dict[str, str] = Field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"


class RefreshHint(UiContractModel):
    wait_for_events: bool = True
    suggested_queries: tuple[str, ...] = ()
    affected_task_refs: tuple[TaskRef, ...] = ()
    affected_scopes: tuple[AffectedScope, ...] = ()


class CommandResponse(UiContractModel):
    request_id: str = Field(default_factory=_new_id, min_length=1)
    ok: bool
    result: CommandResult | None
    error: ApiError | None = None
    refresh: RefreshHint = Field(default_factory=RefreshHint)

    @model_validator(mode="after")
    def _validate_envelope(self) -> CommandResponse:
        if self.ok:
            if self.result is None:
                raise ValueError("successful CommandResponse requires result")
            if self.result.status != "accepted":
                raise ValueError("successful CommandResponse requires accepted result")
            if self.error is not None:
                raise ValueError("successful CommandResponse must not include error")
        elif self.error is None:
            raise ValueError("failed CommandResponse requires error")
        return self
