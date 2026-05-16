"""Pipeline Task expansion for publish flows."""

from __future__ import annotations

import json
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from taskweavn.task.publisher import (
    NormalizedTaskNode,
    NormalizedTaskTree,
    PublishRequest,
)

PipelineStage = Literal["task_before", "task_begin", "task_after"]


class _FrozenPipelineModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        validate_assignment=True,
    )


class PipelineContextPolicy(_FrozenPipelineModel):
    include_user_input: bool = True
    include_task_tree: bool = True
    include_workspace_summary: bool = False
    include_session_summary: bool = False
    max_messages: int | None = Field(default=None, gt=0)


class PipelineTaskSpec(_FrozenPipelineModel):
    """Template for one auto-loaded pipeline Task."""

    spec_id: str = Field(alias="id", min_length=1)
    title: str = Field(min_length=1)
    intent_template: str = Field(min_length=1)
    required_capability: str = Field(min_length=1)
    agent_ref: str | None = Field(default=None, min_length=1)
    context_policy: PipelineContextPolicy = Field(default_factory=PipelineContextPolicy)
    enabled: bool = True
    order: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineConfig(_FrozenPipelineModel):
    version: Literal["1"] = "1"
    enabled: bool = True
    task_before: tuple[PipelineTaskSpec, ...] = ()
    task_begin: tuple[PipelineTaskSpec, ...] = ()
    task_after: tuple[PipelineTaskSpec, ...] = ()


@runtime_checkable
class PipelineTaskLoader(Protocol):
    """Expands configured pipeline specs into ordinary normalized Tasks."""

    def expand_for_publish(self, request: PublishRequest) -> PublishRequest: ...


class DefaultPipelineTaskLoader:
    """First publish-time pipeline loader.

    This slice expands ``task_before`` and ``task_begin`` into ordinary root
    tasks before the requested root tree. ``task_after`` is modeled but not
    loaded here because it belongs to completion-time orchestration.
    """

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self._config = config or PipelineConfig()

    @property
    def config(self) -> PipelineConfig:
        return self._config

    def expand_for_publish(self, request: PublishRequest) -> PublishRequest:
        if not self._config.enabled or not request.options.allow_pipeline:
            return request
        tree = request.task_tree
        if tree is None:
            return request
        pipeline_roots = self._publish_time_roots(request)
        if not pipeline_roots:
            return request
        expanded = NormalizedTaskTree(
            root_nodes=(*pipeline_roots, *tree.root_nodes),
            source=tree.source,
            source_ref=tree.source_ref,
            metadata={
                **tree.metadata,
                "pipeline_enabled": True,
                "pipeline_task_count": len(pipeline_roots),
            },
        )
        return request.model_copy(update={"task_tree": expanded})

    def _publish_time_roots(self, request: PublishRequest) -> tuple[NormalizedTaskNode, ...]:
        roots: list[NormalizedTaskNode] = []
        roots.extend(
            _node_from_spec(spec, stage="task_before", request=request)
            for spec in _enabled_specs(self._config.task_before)
        )
        roots.extend(
            _node_from_spec(spec, stage="task_begin", request=request)
            for spec in _enabled_specs(self._config.task_begin)
        )
        return tuple(roots)


def _enabled_specs(specs: tuple[PipelineTaskSpec, ...]) -> tuple[PipelineTaskSpec, ...]:
    return tuple(sorted((spec for spec in specs if spec.enabled), key=lambda spec: spec.order))


def _node_from_spec(
    spec: PipelineTaskSpec,
    *,
    stage: PipelineStage,
    request: PublishRequest,
) -> NormalizedTaskNode:
    return NormalizedTaskNode(
        node_id=f"pipeline:{stage}:{spec.spec_id}",
        title=spec.title,
        intent=_render_intent(spec, request=request, stage=stage),
        required_capability=spec.required_capability,
        agent_ref=spec.agent_ref,
        metadata={
            "source": "pipeline",
            "pipeline_stage": stage,
            "pipeline_spec_id": spec.spec_id,
            "pipeline_order": spec.order,
            "pipeline_source_request_id": request.request_id,
            "pipeline_source_publisher_kind": request.publisher.kind,
            "pipeline_source_id": request.source.source_id,
            **spec.metadata,
        },
    )


def _render_intent(
    spec: PipelineTaskSpec,
    *,
    request: PublishRequest,
    stage: PipelineStage,
) -> str:
    tree = request.task_tree
    root_ids = () if tree is None else tree.root_ids
    task_tree_json = "" if tree is None else json.dumps(
        tree.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )
    values = {
        "session_id": request.session_id,
        "request_id": request.request_id,
        "publisher_kind": request.publisher.kind,
        "source_type": request.source.source_type,
        "source_id": request.source.source_id or "",
        "source_ref": "" if tree is None or tree.source_ref is None else tree.source_ref,
        "root_ids": ", ".join(root_ids),
        "task_count": 0 if tree is None else tree.task_count,
        "task_tree": task_tree_json,
        "pipeline_stage": stage,
    }
    return spec.intent_template.format(**values)


__all__ = [
    "DefaultPipelineTaskLoader",
    "PipelineConfig",
    "PipelineContextPolicy",
    "PipelineStage",
    "PipelineTaskLoader",
    "PipelineTaskSpec",
]
