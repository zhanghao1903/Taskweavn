"""LLM provider helpers for Main Page workspace runtime assembly."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from taskweavn.llm.agent_config import AgentLlmRole
from taskweavn.llm.agent_resolver import SettingsBackedAgentLlmResolver
from taskweavn.server.main_page_usage import task_plan_resolver
from taskweavn.server.settings_config import effective_web_search_settings
from taskweavn.task import CollaboratorLLM, SqliteTaskBus
from taskweavn.usage import SqliteTokenUsageStore, UsageRecordingLLM
from taskweavn.web_retrieval import TavilyWebSearchProvider, WebSearchProvider


class WorkspaceLlmConfig(Protocol):
    @property
    def workspace_root(self) -> Path: ...

    @property
    def current_workspace_id(self) -> str | None: ...


class WorkspaceLlmDependencies(Protocol):
    @property
    def llm_factory(self) -> Callable[[Path], CollaboratorLLM] | None: ...

    @property
    def llm(self) -> CollaboratorLLM | None: ...


@dataclass(frozen=True)
class WorkspaceAgentLlms:
    execution: Any
    collaborator: Any
    read_only_inquiry: Any
    router: Any


def workspace_agent_llms(
    config: WorkspaceLlmConfig,
    dependencies: WorkspaceLlmDependencies,
    *,
    settings_store: Any,
    token_usage_store: SqliteTokenUsageStore,
    task_bus: SqliteTaskBus,
) -> WorkspaceAgentLlms:
    shared_llm = workspace_llm_if_configured(config.workspace_root, dependencies)
    workspace_id = config.current_workspace_id or "current"
    plan_resolver = task_plan_resolver(task_bus)
    if shared_llm is not None:
        usage_llm = UsageRecordingLLM(
            shared_llm,
            workspace_id=workspace_id,
            sink=token_usage_store,
            task_plan_resolver=plan_resolver,
        )
        return WorkspaceAgentLlms(
            execution=usage_llm,
            collaborator=usage_llm,
            read_only_inquiry=usage_llm,
            router=usage_llm,
        )

    resolver = SettingsBackedAgentLlmResolver(
        settings_store=settings_store,
        base_env=os.environ,
        workspace_id=workspace_id,
        usage_sink=token_usage_store,
        task_plan_resolver=plan_resolver,
    )

    def client(role: AgentLlmRole) -> Any:
        return resolver.client_for(role)

    return WorkspaceAgentLlms(
        execution=client("execution_agent"),
        collaborator=client("collaborator"),
        read_only_inquiry=client("read_only_inquiry"),
        router=client("runtime_input_router"),
    )


def workspace_llm_if_configured(
    workspace_root: Path,
    dependencies: WorkspaceLlmDependencies,
) -> CollaboratorLLM | None:
    if dependencies.llm_factory is not None:
        return dependencies.llm_factory(workspace_root)
    return dependencies.llm


def read_only_inquiry_web_search_provider(
    settings_store: Any,
) -> WebSearchProvider | None:
    settings = effective_web_search_settings(
        config=settings_store.read_config(),
        base_env=os.environ,
        store=settings_store,
    )
    if settings.status != "ready" or settings.provider != "tavily":
        return None
    return TavilyWebSearchProvider(api_key=settings.api_key or "")
