"""Durable execution ASK domain models and store protocol.

ASK is the execution-time mechanism for user-owned missing information. It is
not a normal MessageStream row and not a confirmation/actionable message:
MessageStream may record ASK history, but AskStore owns ASK state.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from threading import RLock
from typing import ClassVar, Literal, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

AskStatus = Literal["pending", "answered", "deferred", "cancelled", "expired"]
AskAnswerType = Literal["free_text", "single_choice", "multi_choice", "boolean"]
AskCommandKind = Literal["answer", "defer", "cancel", "expire"]
AskCommandResultStatus = Literal["accepted", "replayed", "rejected"]


def _new_id() -> str:
    return uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(UTC)


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class AskOption(_FrozenModel):
    option_id: str = Field(default_factory=_new_id, min_length=1)
    label: str = Field(min_length=1)
    description: str | None = None


class AskRequest(_FrozenModel):
    ask_id: str = Field(default_factory=_new_id, min_length=1)
    session_id: str = Field(min_length=1)
    task_id: str | None = Field(default=None, min_length=1)
    agent_id: str = Field(default="agent", min_length=1)

    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    suggested_options: tuple[AskOption, ...] = ()
    answer_type: AskAnswerType = "free_text"
    allow_free_text: bool = True
    allow_no_option_with_text: bool = True
    blocking: bool = True
    attachments_supported: Literal[False] = False

    status: AskStatus = "pending"
    answer_id: str | None = Field(default=None, min_length=1)
    resume_hint: str | None = Field(default=None, min_length=1)
    created_by: Literal["agent", "system"] = "agent"

    created_at: datetime = Field(default_factory=_utcnow)
    answered_at: datetime | None = None
    deferred_at: datetime | None = None
    cancelled_at: datetime | None = None
    expired_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_blocking_scope(self) -> AskRequest:
        if self.blocking and self.task_id is None:
            raise ValueError("blocking ASK requires task_id")
        return self

    @model_validator(mode="after")
    def _validate_answer_reference(self) -> AskRequest:
        if self.status == "answered" and (
            self.answer_id is None or self.answered_at is None
        ):
            raise ValueError("answered ASK requires answer_id and answered_at")
        if self.status != "answered" and self.answer_id is not None:
            raise ValueError("answer_id is only valid for answered ASK")
        return self


class AskAnswer(_FrozenModel):
    answer_id: str = Field(default_factory=_new_id, min_length=1)
    ask_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    task_id: str | None = Field(default=None, min_length=1)
    selected_option_ids: tuple[str, ...] = ()
    text: str | None = Field(default=None, min_length=1)
    attachments: tuple[object, ...] = ()
    answered_by: Literal["user"] = "user"
    idempotency_key: str | None = Field(default=None, min_length=1)
    created_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def _validate_content(self) -> AskAnswer:
        if self.attachments:
            raise ValueError("ASK answer attachments are not supported in Product 1.0")
        if not self.selected_option_ids and self.text is None:
            raise ValueError("ASK answer requires selected option or text")
        return self


class AskStoreCommandResult(_FrozenModel):
    status: AskCommandResultStatus
    message: str = Field(min_length=1)
    ask: AskRequest | None = None
    answer: AskAnswer | None = None
    command_kind: AskCommandKind
    idempotency_key: str | None = Field(default=None, min_length=1)

    @property
    def accepted(self) -> bool:
        return self.status in {"accepted", "replayed"}


class AskStoreError(RuntimeError):
    """Raised when an ASK store cannot complete a persistence operation."""


@runtime_checkable
class AskStore(Protocol):
    def create(self, request: AskRequest) -> AskRequest: ...

    def get(self, session_id: str, ask_id: str) -> AskRequest | None: ...

    def list_for_session(
        self,
        session_id: str,
        *,
        statuses: Iterable[AskStatus] | None = None,
        task_id: str | None = None,
    ) -> list[AskRequest]: ...

    def get_answer(self, session_id: str, ask_id: str) -> AskAnswer | None: ...

    def answer(
        self,
        session_id: str,
        ask_id: str,
        answer: AskAnswer,
        *,
        idempotency_key: str | None = None,
    ) -> AskStoreCommandResult: ...

    def defer(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> AskStoreCommandResult: ...

    def cancel(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str,
        idempotency_key: str | None = None,
    ) -> AskStoreCommandResult: ...

    def expire(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> AskStoreCommandResult: ...


class InMemoryAskStore:
    """Thread-safe in-memory ASK store for tests and early assembly."""

    def __init__(
        self,
        requests: Iterable[AskRequest] = (),
        answers: Iterable[AskAnswer] = (),
    ) -> None:
        self._lock = RLock()
        self._requests = {
            (request.session_id, request.ask_id): request for request in requests
        }
        self._answers = {(answer.session_id, answer.ask_id): answer for answer in answers}
        self._idempotency: dict[tuple[str, str], AskStoreCommandResult] = {}

    def create(self, request: AskRequest) -> AskRequest:
        with self._lock:
            key = (request.session_id, request.ask_id)
            if key in self._requests:
                raise AskStoreError(f"ASK {request.ask_id!r} already exists")
            self._requests[key] = request
            return request

    def get(self, session_id: str, ask_id: str) -> AskRequest | None:
        with self._lock:
            return self._requests.get((session_id, ask_id))

    def list_for_session(
        self,
        session_id: str,
        *,
        statuses: Iterable[AskStatus] | None = None,
        task_id: str | None = None,
    ) -> list[AskRequest]:
        status_set = None if statuses is None else set(statuses)
        with self._lock:
            requests = [
                request
                for request in self._requests.values()
                if request.session_id == session_id
                and (task_id is None or request.task_id == task_id)
                and (status_set is None or request.status in status_set)
            ]
        return sorted(requests, key=lambda request: (request.created_at, request.ask_id))

    def get_answer(self, session_id: str, ask_id: str) -> AskAnswer | None:
        with self._lock:
            return self._answers.get((session_id, ask_id))

    def answer(
        self,
        session_id: str,
        ask_id: str,
        answer: AskAnswer,
        *,
        idempotency_key: str | None = None,
    ) -> AskStoreCommandResult:
        with self._lock:
            replay = self._idempotency_replay(session_id, idempotency_key)
            if replay is not None:
                return replay
            result = _answer_request(
                self._requests.get((session_id, ask_id)),
                answer,
                idempotency_key=idempotency_key,
            )
            if result.status == "accepted" and result.ask is not None:
                assert result.answer is not None
                self._requests[(session_id, ask_id)] = result.ask
                self._answers[(session_id, ask_id)] = result.answer
            self._remember(session_id, idempotency_key, result)
            return result

    def defer(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> AskStoreCommandResult:
        return self._transition(
            session_id,
            ask_id,
            command_kind="defer",
            status="deferred",
            reason=reason,
            idempotency_key=idempotency_key,
        )

    def cancel(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str,
        idempotency_key: str | None = None,
    ) -> AskStoreCommandResult:
        return self._transition(
            session_id,
            ask_id,
            command_kind="cancel",
            status="cancelled",
            reason=reason,
            idempotency_key=idempotency_key,
        )

    def expire(
        self,
        session_id: str,
        ask_id: str,
        *,
        reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> AskStoreCommandResult:
        return self._transition(
            session_id,
            ask_id,
            command_kind="expire",
            status="expired",
            reason=reason,
            idempotency_key=idempotency_key,
        )

    def _transition(
        self,
        session_id: str,
        ask_id: str,
        *,
        command_kind: AskCommandKind,
        status: Literal["deferred", "cancelled", "expired"],
        reason: str | None,
        idempotency_key: str | None,
    ) -> AskStoreCommandResult:
        with self._lock:
            replay = self._idempotency_replay(session_id, idempotency_key)
            if replay is not None:
                return replay
            request = self._requests.get((session_id, ask_id))
            result = _transition_request(
                request,
                command_kind=command_kind,
                status=status,
                reason=reason,
                idempotency_key=idempotency_key,
            )
            if result.status == "accepted" and result.ask is not None:
                self._requests[(session_id, ask_id)] = result.ask
            self._remember(session_id, idempotency_key, result)
            return result

    def _idempotency_replay(
        self,
        session_id: str,
        idempotency_key: str | None,
    ) -> AskStoreCommandResult | None:
        if idempotency_key is None:
            return None
        result = self._idempotency.get((session_id, idempotency_key))
        if result is None:
            return None
        if result.status == "rejected":
            return result
        return result.model_copy(update={"status": "replayed"})

    def _remember(
        self,
        session_id: str,
        idempotency_key: str | None,
        result: AskStoreCommandResult,
    ) -> None:
        if idempotency_key is None:
            return
        self._idempotency[(session_id, idempotency_key)] = result


def _answer_request(
    request: AskRequest | None,
    answer: AskAnswer,
    *,
    idempotency_key: str | None,
) -> AskStoreCommandResult:
    if request is None:
        return _rejected("ASK not found", command_kind="answer", idempotency_key=idempotency_key)
    if answer.session_id != request.session_id or answer.ask_id != request.ask_id:
        return _rejected(
            "ASK answer target does not match request",
            command_kind="answer",
            ask=request,
            idempotency_key=idempotency_key,
        )
    if request.task_id != answer.task_id:
        return _rejected(
            "ASK answer task_id does not match request",
            command_kind="answer",
            ask=request,
            idempotency_key=idempotency_key,
        )
    if request.status != "pending":
        return _rejected(
            f"ASK is not pending: {request.status}",
            command_kind="answer",
            ask=request,
            idempotency_key=idempotency_key,
        )
    validation_error = _validate_answer_against_request(request, answer)
    if validation_error is not None:
        return _rejected(
            validation_error,
            command_kind="answer",
            ask=request,
            idempotency_key=idempotency_key,
        )
    effective_answer = answer
    if idempotency_key is not None and answer.idempotency_key != idempotency_key:
        if answer.idempotency_key is not None:
            return _rejected(
                "ASK answer idempotency_key does not match command",
                command_kind="answer",
                ask=request,
                idempotency_key=idempotency_key,
            )
        effective_answer = answer.model_copy(update={"idempotency_key": idempotency_key})
    updated = request.model_copy(
        update={
            "status": "answered",
            "answer_id": effective_answer.answer_id,
            "answered_at": effective_answer.created_at,
        }
    )
    return AskStoreCommandResult(
        status="accepted",
        message="ASK answered",
        ask=updated,
        answer=effective_answer,
        command_kind="answer",
        idempotency_key=idempotency_key,
    )


def _transition_request(
    request: AskRequest | None,
    *,
    command_kind: AskCommandKind,
    status: Literal["deferred", "cancelled", "expired"],
    reason: str | None,
    idempotency_key: str | None,
) -> AskStoreCommandResult:
    if request is None:
        return _rejected(
            "ASK not found",
            command_kind=command_kind,
            idempotency_key=idempotency_key,
        )
    if request.status != "pending":
        return _rejected(
            f"ASK is not pending: {request.status}",
            command_kind=command_kind,
            ask=request,
            idempotency_key=idempotency_key,
        )
    now = _utcnow()
    timestamp_field = {
        "deferred": "deferred_at",
        "cancelled": "cancelled_at",
        "expired": "expired_at",
    }[status]
    updated = request.model_copy(
        update={
            "status": status,
            timestamp_field: now,
            "resume_hint": reason,
        }
    )
    return AskStoreCommandResult(
        status="accepted",
        message=f"ASK {status}",
        ask=updated,
        command_kind=command_kind,
        idempotency_key=idempotency_key,
    )


def _validate_answer_against_request(
    request: AskRequest,
    answer: AskAnswer,
) -> str | None:
    option_ids = {option.option_id for option in request.suggested_options}
    unknown = sorted(set(answer.selected_option_ids) - option_ids)
    if unknown:
        return f"ASK answer selected unknown option ids: {', '.join(unknown)}"
    if answer.text is not None and not request.allow_free_text:
        return "ASK answer free text is not allowed"
    has_text = answer.text is not None and answer.text.strip() != ""
    selected_count = len(answer.selected_option_ids)
    if request.answer_type == "free_text":
        if selected_count:
            return "free_text ASK answer must not select options"
        if not has_text:
            return "free_text ASK answer requires text"
    elif request.answer_type == "single_choice":
        if selected_count > 1:
            return "single_choice ASK answer accepts at most one option"
        if selected_count == 0 and not (
            request.allow_no_option_with_text and has_text
        ):
            return "single_choice ASK answer requires one option"
    elif request.answer_type == "multi_choice":
        if selected_count == 0 and not (
            request.allow_no_option_with_text and has_text
        ):
            return "multi_choice ASK answer requires at least one option"
    elif request.answer_type == "boolean":
        if selected_count != 1:
            return "boolean ASK answer requires exactly one option"
    return None


def _rejected(
    message: str,
    *,
    command_kind: AskCommandKind,
    ask: AskRequest | None = None,
    idempotency_key: str | None = None,
) -> AskStoreCommandResult:
    return AskStoreCommandResult(
        status="rejected",
        message=message,
        ask=ask,
        command_kind=command_kind,
        idempotency_key=idempotency_key,
    )


__all__ = [
    "AskAnswer",
    "AskAnswerType",
    "AskCommandKind",
    "AskCommandResultStatus",
    "AskOption",
    "AskRequest",
    "AskStatus",
    "AskStore",
    "AskStoreCommandResult",
    "AskStoreError",
    "InMemoryAskStore",
]
