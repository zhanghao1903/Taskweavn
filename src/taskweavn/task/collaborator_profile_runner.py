"""Bounded Collaborator authoring profile runner."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import ValidationError

from taskweavn.core import LoopTerminalAction
from taskweavn.llm import ChatResponse, ToolCall, parse_tool_arguments
from taskweavn.llm.logging import log_agent_llm_input, log_agent_llm_output
from taskweavn.observability import LogContext
from taskweavn.task.collaborator_loop import (
    AUTHORING_READ_WORKSPACE_TOOL_NAME,
    AUTHORING_SEARCH_WORKSPACE_TOOL_NAME,
    COLLABORATOR_AUTHORING_FORBIDDEN_TOOL_NAMES,
    CollaboratorAuthoringLoopResult,
    CollaboratorAuthoringProfile,
    CollaboratorAuthoringProfileRequest,
)
from taskweavn.task.collaborator_workspace_context import (
    AuthoringReadWorkspaceRequest,
    AuthoringSearchWorkspaceRequest,
    CollaboratorWorkspaceContextSource,
)


@runtime_checkable
class CollaboratorProfileLLM(Protocol):
    """LLM surface needed by the Collaborator profile runner."""

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Any: ...


class CollaboratorAuthoringProfileRunner:
    """Run one Collaborator profile request with bounded read/search dispatch."""

    def __init__(
        self,
        *,
        llm: CollaboratorProfileLLM,
        profile: CollaboratorAuthoringProfile,
        actor_id: str,
        workspace_context_source: CollaboratorWorkspaceContextSource | None = None,
        max_context_steps: int = 3,
    ) -> None:
        if max_context_steps < 0:
            raise ValueError("max_context_steps must be non-negative")
        self._llm = llm
        self._profile = profile
        self._actor_id = actor_id
        self._workspace_context_source = workspace_context_source
        self._max_context_steps = max_context_steps

    def run(
        self,
        *,
        request: CollaboratorAuthoringProfileRequest,
        parse_response: Callable[[str], dict[str, Any]],
    ) -> CollaboratorAuthoringLoopResult:
        messages = self._profile.build_initial_messages(request)
        tools = self._tool_schemas()
        loop_id = uuid4().hex
        context_steps_used = 0
        evidence_refs: list[str] = []
        try:
            while True:
                response = self._chat(
                    request=request,
                    messages=messages,
                    tools=tools,
                    loop_id=loop_id,
                    step=context_steps_used,
                )
                messages.append(response.raw_assistant_message)
                if not response.tool_calls:
                    terminal_action = self._profile.finish_action(
                        proposal_kind=request.proposal_kind,
                        proposal=parse_response(response.content),
                        evidence_refs=tuple(evidence_refs),
                    )
                    return self._profile.map_terminal_action(terminal_action, request)

                terminal_call = self._single_terminal_call(response.tool_calls)
                if terminal_call is not None:
                    terminal_action = self._terminal_action_from_tool_call(
                        terminal_call,
                        evidence_refs=tuple(evidence_refs),
                    )
                    return self._profile.map_terminal_action(terminal_action, request)

                if context_steps_used >= self._max_context_steps:
                    raise ValueError("Collaborator context tool step limit exceeded")
                context_steps_used += 1
                for tool_call in response.tool_calls:
                    observation = self._dispatch_context_tool(
                        tool_call,
                        request=request,
                        loop_id=loop_id,
                    )
                    evidence_refs.extend(_observation_evidence_refs(observation))
                    messages.append(_tool_message(tool_call, observation))
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return self._profile.map_rejection(exc, request)

    def _tool_schemas(self) -> list[dict[str, Any]] | None:
        if self._workspace_context_source is None:
            return None
        return self._profile.tool_schemas(include_context_tools=True)

    def _chat(
        self,
        *,
        request: CollaboratorAuthoringProfileRequest,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        loop_id: str,
        step: int,
    ) -> ChatResponse:
        metadata = {
            "agent_kind": "collaborator",
            "agent_id": self._actor_id,
            "component": "collaborator_authoring",
            "loop_id": loop_id,
            "loop_profile_id": self._profile.profile_id,
            "request_purpose": request.request_purpose,
            "session_id": request.session_id,
            "step": step,
            "terminal_tool_name": self._profile.terminal_tool_name,
        }
        metadata.update(request.metadata)
        log_context = LogContext(
            session_id=request.session_id,
            agent_id=self._actor_id,
        )
        log_agent_llm_input(
            agent_kind="collaborator",
            request_purpose=request.request_purpose,
            messages=messages,
            tools=tools,
            metadata=metadata,
            context=log_context,
        )
        response = _coerce_chat_response(
            self._llm.chat(
                messages=messages,
                tools=tools,
                metadata=metadata,
            )
        )
        log_agent_llm_output(
            agent_kind="collaborator",
            request_purpose=request.request_purpose,
            response=response,
            metadata=metadata,
            context=log_context,
        )
        return response

    def _single_terminal_call(self, tool_calls: list[ToolCall]) -> ToolCall | None:
        terminal_tool_names = set(self._profile.terminal_tool_names)
        terminal_calls = [
            tool_call
            for tool_call in tool_calls
            if tool_call.name in terminal_tool_names
        ]
        if not terminal_calls:
            return None
        if len(tool_calls) > 1:
            raise ValueError("authoring terminal tool call must be the only tool call")
        return terminal_calls[0]

    def _terminal_action_from_tool_call(
        self,
        tool_call: ToolCall,
        *,
        evidence_refs: tuple[str, ...],
    ) -> LoopTerminalAction:
        arguments = parse_tool_arguments(tool_call.arguments)
        if evidence_refs and not arguments.get("evidence_refs"):
            arguments["evidence_refs"] = list(evidence_refs)
        return LoopTerminalAction(
            profile_id=self._profile.profile_id,
            tool_name=tool_call.name,
            arguments=arguments,
            tool_call_id=tool_call.id,
        )

    def _dispatch_context_tool(
        self,
        tool_call: ToolCall,
        *,
        request: CollaboratorAuthoringProfileRequest,
        loop_id: str,
    ) -> dict[str, Any]:
        if tool_call.name in COLLABORATOR_AUTHORING_FORBIDDEN_TOOL_NAMES:
            raise ValueError(f"Collaborator tool {tool_call.name!r} is forbidden")
        if self._workspace_context_source is None:
            raise ValueError("Collaborator workspace context source is not configured")
        arguments = parse_tool_arguments(tool_call.arguments)
        if tool_call.name == AUTHORING_READ_WORKSPACE_TOOL_NAME:
            read_observation = self._workspace_context_source.read_workspace(
                session_id=request.session_id,
                loop_id=loop_id,
                request=AuthoringReadWorkspaceRequest.model_validate(arguments),
            )
            return read_observation.model_dump(mode="json")
        if tool_call.name == AUTHORING_SEARCH_WORKSPACE_TOOL_NAME:
            search_observation = self._workspace_context_source.search_workspace(
                session_id=request.session_id,
                loop_id=loop_id,
                request=AuthoringSearchWorkspaceRequest.model_validate(arguments),
            )
            return search_observation.model_dump(mode="json")
        raise ValueError(f"Collaborator tool {tool_call.name!r} is not allowed")


def _coerce_chat_response(response: Any) -> ChatResponse:
    if isinstance(response, ChatResponse):
        content = response.content
        if not isinstance(content, str):
            raise TypeError("LLM response content must be a string")
        return response
    content_value = getattr(response, "content", None)
    if not isinstance(content_value, str):
        raise TypeError("LLM response content must be a string")
    return ChatResponse(
        content=content_value,
        tool_calls=[],
        raw_assistant_message={
            "role": "assistant",
            "content": content_value,
        },
    )


def _tool_message(tool_call: ToolCall, observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "name": tool_call.name,
        "content": json.dumps(
            {
                "observation": observation,
                "tool_name": tool_call.name,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    }


def _observation_evidence_refs(observation: dict[str, Any]) -> tuple[str, ...]:
    raw_refs = observation.get("evidence_refs", ())
    if not isinstance(raw_refs, list):
        return ()
    refs: list[str] = []
    for ref in raw_refs:
        if isinstance(ref, str):
            refs.append(ref)
    return tuple(refs)


__all__ = [
    "CollaboratorAuthoringProfileRunner",
    "CollaboratorProfileLLM",
]
