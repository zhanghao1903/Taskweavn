"""Context source adapters for Product 1.0 execution facts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, TypeGuard

from taskweavn.context.models import (
    AskFact,
    ContextBuildRequest,
    CurrentStepContext,
    EventSummary,
    ExecutionContextState,
    ExecutionControls,
    ExecutionFacts,
    ExecutionGuidance,
    FileSnippet,
    InterruptionContext,
    ToolResultSummary,
    WorkspaceRef,
)
from taskweavn.context.policy import estimate_tokens
from taskweavn.core.event_stream import EventStream
from taskweavn.tools.fs import FileContentObservation
from taskweavn.types.base import BaseAction, BaseEvent, BaseObservation

if TYPE_CHECKING:
    from taskweavn.interaction import AskStore
    from taskweavn.task.bus import TaskBus
    from taskweavn.task.models import TaskDomain


class ContextSourceError(RuntimeError):
    """Raised when a required context source cannot produce facts."""


class TaskEventStream(Protocol):
    def iter_for_task(self, task_id: str) -> Iterator[BaseEvent]: ...


def has_iter_for_task(stream: object) -> TypeGuard[TaskEventStream]:
    return callable(getattr(stream, "iter_for_task", None))


@dataclass(frozen=True)
class TaskContextSource:
    task_bus: TaskBus

    def load_task(self, request: ContextBuildRequest) -> TaskDomain:
        task = self.task_bus.get(request.session_id, request.task_id)
        if task is None:
            raise ContextSourceError(f"task {request.task_id!r} not found")
        return task

    def execution_state(
        self,
        task: TaskDomain,
        request: ContextBuildRequest,
    ) -> ExecutionContextState:
        interruption = None
        if task.interrupt_requested:
            interruption = InterruptionContext(
                requested=True,
                request_id=task.interrupt_request_id,
                reason=task.interrupt_reason,
                requested_by=task.interrupt_requested_by,
                requested_at=task.interrupt_requested_at,
            )
        return ExecutionContextState(
            status=task.status,
            claimed_by=task.claimed_by,
            current_step=CurrentStepContext(
                step_id=task.task_id,
                objective=task.intent,
            ),
            latest_user_instruction=request.latest_user_instruction,
            interruption=interruption,
        )


@dataclass(frozen=True)
class EventStreamFacts:
    events: tuple[EventSummary, ...] = ()
    tool_results: tuple[ToolResultSummary, ...] = ()
    file_snippets: tuple[FileSnippet, ...] = ()


@dataclass(frozen=True)
class EventStreamContextSource:
    event_stream: EventStream
    workspace_id: str | None = None

    def collect(self, request: ContextBuildRequest) -> EventStreamFacts:
        events = tuple(self._iter_events(request.task_id))
        summaries = tuple(_event_summary(event) for event in events)
        tool_results = tuple(
            _tool_result_summary(event)
            for event in events
            if isinstance(event, BaseObservation)
        )
        snippets = tuple(
            _file_snippet(event, request, workspace_id=self.workspace_id)
            for event in events
            if isinstance(event, FileContentObservation)
        )
        return EventStreamFacts(
            events=summaries,
            tool_results=tool_results,
            file_snippets=snippets,
        )

    def _iter_events(self, task_id: str) -> Iterator[BaseEvent]:
        if has_iter_for_task(self.event_stream):
            yield from self.event_stream.iter_for_task(task_id)
            return
        yield from self.event_stream


@dataclass(frozen=True)
class WorkspaceEvidenceContextSource:
    workspace_refs: tuple[WorkspaceRef, ...] = ()
    file_snippets: tuple[FileSnippet, ...] = ()

    def collect(self, request: ContextBuildRequest) -> ExecutionFacts:
        del request
        return ExecutionFacts(
            workspace_refs=self.workspace_refs,
            selected_file_snippets=self.file_snippets,
        )


@dataclass(frozen=True)
class AskContextSource:
    ask_store: AskStore

    def collect(self, request: ContextBuildRequest) -> ExecutionFacts:
        asks = self.ask_store.list_for_session(
            request.session_id,
            statuses=("pending", "answered"),
            task_id=request.task_id,
        )
        return ExecutionFacts(
            ask_facts=tuple(_ask_fact(self.ask_store, request.session_id, ask) for ask in asks)
        )


@dataclass(frozen=True)
class ControlContextSource:
    allowed_tools: tuple[str, ...] = ()
    denied_tools: tuple[str, ...] = ()
    requires_approval: tuple[str, ...] = ()
    file_scopes: tuple[str, ...] = ()

    def collect(self, request: ContextBuildRequest) -> ExecutionControls:
        del request
        return ExecutionControls(
            allowed_tools=self.allowed_tools,
            denied_tools=self.denied_tools,
            requires_approval=self.requires_approval,
            pending_approval=None,
            file_scopes=self.file_scopes,
        )


@dataclass(frozen=True)
class GuidanceContextSource:
    guidance: ExecutionGuidance = field(default_factory=ExecutionGuidance)

    def collect(self, request: ContextBuildRequest) -> ExecutionGuidance:
        del request
        return self.guidance


def merge_facts(*facts: ExecutionFacts) -> ExecutionFacts:
    return ExecutionFacts(
        recent_events=tuple(_chain(fact.recent_events for fact in facts)),
        recent_tool_results=tuple(_chain(fact.recent_tool_results for fact in facts)),
        workspace_refs=tuple(_chain(fact.workspace_refs for fact in facts)),
        selected_file_snippets=tuple(
            _chain(fact.selected_file_snippets for fact in facts)
        ),
        ask_facts=tuple(_chain(fact.ask_facts for fact in facts)),
        changed_artifacts=tuple(_chain(fact.changed_artifacts for fact in facts)),
    )


def _chain[T](values: Iterable[Iterable[T]]) -> Iterator[T]:
    for group in values:
        yield from group


def _event_summary(event: BaseEvent) -> EventSummary:
    family: Literal["action", "observation", "event"]
    if isinstance(event, BaseAction):
        family = "action"
    elif isinstance(event, BaseObservation):
        family = "observation"
    else:
        family = "event"
    payload = event.to_dict()
    return EventSummary(
        event_id=event.event_id,
        kind=event.kind or type(event).__name__,
        family=family,
        timestamp=event.timestamp,
        summary=_summarize_payload(payload),
        raw_ref=f"event:{event.event_id}",
    )


def _tool_result_summary(observation: BaseObservation) -> ToolResultSummary:
    payload = observation.to_dict()
    summary = _summarize_payload(payload)
    return ToolResultSummary(
        observation_id=observation.event_id,
        action_id=observation.action_id,
        kind=observation.kind or type(observation).__name__,
        success=observation.success,
        summary=summary,
        raw_ref=f"event:{observation.event_id}",
        token_estimate=estimate_tokens(summary),
        observed_at=observation.timestamp,
    )


def _file_snippet(
    observation: FileContentObservation,
    request: ContextBuildRequest,
    *,
    workspace_id: str | None,
) -> FileSnippet:
    content = observation.content
    if len(content) > request.budget.max_file_snippet_chars:
        content = content[: request.budget.max_file_snippet_chars]
        reason = "latest explicit read_file observation for this task; truncated"
    else:
        reason = "latest explicit read_file observation for this task"
    return FileSnippet(
        snippet_id=f"file:{observation.path}:read_file:{observation.event_id}",
        workspace_id=workspace_id,
        path=observation.path,
        source="tool_result",
        content=content,
        start_line=1 if content else None,
        end_line=_line_count(content) if content else None,
        file_hash=None,
        content_hash=_hash_text(content),
        raw_ref=f"event:{observation.event_id}",
        reason=reason,
        token_estimate=estimate_tokens(content),
        observed_at=observation.timestamp,
        stale=False,
        can_act_as_instruction=False,
    )


def _ask_fact(
    ask_store: AskStore,
    session_id: str,
    ask: object,
) -> AskFact:
    from taskweavn.interaction import AskRequest

    if not isinstance(ask, AskRequest):
        ask = AskRequest.model_validate(ask)
    answer = ask_store.get_answer(session_id, ask.ask_id)
    return AskFact(
        ask_id=ask.ask_id,
        task_id=ask.task_id,
        status=ask.status,
        question=ask.question,
        reason=ask.reason,
        selected_option_ids=() if answer is None else answer.selected_option_ids,
        answer_text=None if answer is None else answer.text,
        answer_id=ask.answer_id,
        blocking=ask.blocking,
        created_at=ask.created_at,
        answered_at=ask.answered_at,
    )


def _summarize_payload(payload: dict[str, object]) -> str:
    safe_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"content", "stdout", "stderr"}
    }
    for key in ("content", "stdout", "stderr"):
        value = payload.get(key)
        if isinstance(value, str):
            safe_payload[f"{key}_chars"] = len(value)
    return json.dumps(safe_payload, ensure_ascii=False, sort_keys=True)


def _hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _line_count(text: str) -> int:
    return len(text.splitlines()) if text else 0
