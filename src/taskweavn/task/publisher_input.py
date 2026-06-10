"""Parser and validator for custom Task Tree publish input."""

from __future__ import annotations

import importlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from taskweavn.task.authoring import CapabilityCatalog
from taskweavn.task.publisher import (
    NormalizedTaskNode,
    NormalizedTaskTree,
    PublisherRef,
)

TaskTreeInputFormat = Literal["auto", "json", "yaml"]
TaskTreeValidationSeverity = Literal["error", "warning"]


class TaskTreeInputError(ValueError):
    """Raised when custom Task Tree input cannot be parsed or normalized."""


class _FrozenInputModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class AgentCapabilityBinding(_FrozenInputModel):
    """Static agent-to-capability binding for publish validation."""

    agent_ref: str = Field(min_length=1)
    capabilities: tuple[str, ...] = Field(min_length=1)


@runtime_checkable
class AgentCapabilityCatalog(Protocol):
    """Read side for checking whether an Agent can handle a capability."""

    def supports(self, agent_ref: str, capability: str) -> bool: ...


class StaticAgentCapabilityCatalog:
    """Deterministic in-memory AgentCapabilityCatalog for tests/config."""

    def __init__(self, bindings: Sequence[AgentCapabilityBinding | Mapping[str, Any]]) -> None:
        self._capabilities_by_agent: dict[str, tuple[str, ...]] = {}
        for binding_like in bindings:
            binding = AgentCapabilityBinding.model_validate(binding_like)
            self._capabilities_by_agent[binding.agent_ref] = binding.capabilities

    def supports(self, agent_ref: str, capability: str) -> bool:
        return capability in self._capabilities_by_agent.get(agent_ref, ())


class TaskTreeValidationIssue(_FrozenInputModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    path: tuple[str, ...] = ()
    severity: TaskTreeValidationSeverity = "error"


class TaskTreeValidation(_FrozenInputModel):
    issues: tuple[TaskTreeValidationIssue, ...] = ()

    @property
    def errors(self) -> tuple[TaskTreeValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[TaskTreeValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def valid(self) -> bool:
        return not self.errors


class TaskTreeInputValidator:
    """Capability and agent_ref validator for normalized publish trees."""

    def __init__(
        self,
        *,
        capability_catalog: CapabilityCatalog | None = None,
        agent_catalog: AgentCapabilityCatalog | None = None,
    ) -> None:
        self._capability_catalog = capability_catalog
        self._agent_catalog = agent_catalog

    def validate(self, tree: NormalizedTaskTree) -> TaskTreeValidation:
        issues: list[TaskTreeValidationIssue] = []
        for node in tree.iter_nodes():
            path = _node_path(node)
            if self._capability_catalog is not None and not self._capability_catalog.contains(
                node.required_capability
            ):
                issues.append(
                    TaskTreeValidationIssue(
                        code="unknown_capability",
                        message=f"unknown capability {node.required_capability!r}",
                        path=path,
                    )
                )
            if (
                node.agent_ref is not None
                and self._agent_catalog is not None
                and not self._agent_catalog.supports(node.agent_ref, node.required_capability)
            ):
                issues.append(
                    TaskTreeValidationIssue(
                        code="agent_capability_mismatch",
                        message=(
                            f"agent {node.agent_ref!r} does not support "
                            f"capability {node.required_capability!r}"
                        ),
                        path=path,
                    )
                )
        return TaskTreeValidation(issues=tuple(issues))


def parse_task_tree_input(
    content: str | bytes,
    *,
    publisher: PublisherRef,
    source_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
    input_format: TaskTreeInputFormat = "auto",
) -> NormalizedTaskTree:
    """Parse JSON/YAML custom Task Tree input into a NormalizedTaskTree."""

    text = content.decode() if isinstance(content, bytes) else content
    parsed = _parse_text(text, input_format)
    return normalize_task_tree_input(
        parsed,
        publisher=publisher,
        source_ref=source_ref,
        metadata=metadata,
    )


def normalize_task_tree_input(
    data: Mapping[str, Any],
    *,
    publisher: PublisherRef,
    source_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> NormalizedTaskTree:
    """Normalize a dict-like custom Task Tree payload."""

    task_payloads = _task_payloads(data)
    root_nodes = (
        _normalize_flat_task_payloads(task_payloads)
        if _has_parent_links(task_payloads)
        else tuple(
            _normalize_node(payload, parent_id=None, path=("tasks", str(index)))
            for index, payload in enumerate(task_payloads)
        )
    )
    return NormalizedTaskTree(
        root_nodes=root_nodes,
        source=publisher,
        source_ref=source_ref or _optional_str(data, "id") or _optional_str(data, "name"),
        metadata={**_metadata(data, ("metadata",)), **dict(metadata or {})},
    )


def _parse_text(text: str, input_format: TaskTreeInputFormat) -> Mapping[str, Any]:
    fmt = _detect_format(text, input_format)
    try:
        if fmt == "json":
            loaded = json.loads(text)
        else:
            yaml = importlib.import_module("yaml")
            safe_load = yaml.__dict__["safe_load"]
            loaded = safe_load(text)
    except Exception as exc:  # noqa: BLE001 - normalized as input error
        raise TaskTreeInputError(f"failed to parse {fmt} task tree input: {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise TaskTreeInputError("task tree input must be an object")
    return loaded


def _detect_format(text: str, input_format: TaskTreeInputFormat) -> Literal["json", "yaml"]:
    if input_format == "json":
        return "json"
    if input_format == "yaml":
        return "yaml"
    stripped = text.lstrip()
    return "json" if stripped.startswith("{") or stripped.startswith("[") else "yaml"


def _task_payloads(data: Mapping[str, Any]) -> Sequence[Any]:
    payloads = data.get("tasks", data.get("root_nodes", data.get("roots")))
    if not isinstance(payloads, Sequence) or isinstance(payloads, (str, bytes)):
        raise TaskTreeInputError("task tree input requires a tasks/root_nodes list")
    if not payloads:
        raise TaskTreeInputError("task tree input requires at least one task")
    return payloads


def _normalize_node(
    payload: Any,
    *,
    parent_id: str | None,
    path: tuple[str, ...],
) -> NormalizedTaskNode:
    if not isinstance(payload, Mapping):
        raise TaskTreeInputError(f"{'.'.join(path)} must be an object")
    node_id = _required_str(payload, ("node_id", "id"), path)
    capability = _required_str(payload, ("required_capability", "capability"), path)
    children_payload = payload.get("children", ())
    if not isinstance(children_payload, Sequence) or isinstance(children_payload, (str, bytes)):
        raise TaskTreeInputError(f"{'.'.join((*path, 'children'))} must be a list")
    return NormalizedTaskNode(
        node_id=node_id,
        parent_id=parent_id,
        title=_required_str(payload, ("title",), path),
        intent=_required_str(payload, ("intent",), path),
        summary=_optional_str(payload, "summary"),
        instructions=_optional_str(payload, "instructions"),
        acceptance_criteria=_optional_str_tuple(payload, "acceptance_criteria", path),
        required_capability=capability,
        agent_ref=_optional_str(payload, "agent_ref") or _optional_str(payload, "agent"),
        children=tuple(
            _normalize_node(
                child,
                parent_id=node_id,
                path=(*path, "children", str(index)),
            )
            for index, child in enumerate(children_payload)
        ),
        metadata=_metadata(payload, (*path, "metadata")),
    )


def _normalize_flat_task_payloads(payloads: Sequence[Any]) -> tuple[NormalizedTaskNode, ...]:
    payload_by_id: dict[str, Mapping[str, Any]] = {}
    parent_by_id: dict[str, str | None] = {}
    children_by_parent: dict[str | None, list[str]] = {}
    for index, payload in enumerate(payloads):
        path = ("tasks", str(index))
        if not isinstance(payload, Mapping):
            raise TaskTreeInputError(f"{'.'.join(path)} must be an object")
        if payload.get("children"):
            raise TaskTreeInputError("flat parent_id task input must not include children")
        node_id = _required_str(payload, ("node_id", "id"), path)
        if node_id in payload_by_id:
            raise TaskTreeInputError(f"duplicate task id {node_id!r}")
        parent_id = _optional_str(payload, "parent_id")
        payload_by_id[node_id] = payload
        parent_by_id[node_id] = parent_id
        children_by_parent.setdefault(parent_id, []).append(node_id)

    for node_id, parent_id in parent_by_id.items():
        if parent_id is not None and parent_id not in payload_by_id:
            raise TaskTreeInputError(f"task {node_id!r} references unknown parent {parent_id!r}")
    root_ids = children_by_parent.get(None, [])
    if not root_ids:
        raise TaskTreeInputError("flat task input has no root tasks")

    visiting: set[str] = set()
    visited: set[str] = set()
    roots = tuple(
        _normalize_flat_node(
            node_id,
            parent_id=None,
            payload_by_id=payload_by_id,
            children_by_parent=children_by_parent,
            visiting=visiting,
            visited=visited,
        )
        for node_id in root_ids
    )
    if len(visited) != len(payload_by_id):
        raise TaskTreeInputError("flat task input contains a cycle or unreachable task")
    return roots


def _normalize_flat_node(
    node_id: str,
    *,
    parent_id: str | None,
    payload_by_id: dict[str, Mapping[str, Any]],
    children_by_parent: dict[str | None, list[str]],
    visiting: set[str],
    visited: set[str],
) -> NormalizedTaskNode:
    if node_id in visiting:
        raise TaskTreeInputError(f"flat task input contains a cycle at {node_id!r}")
    visiting.add(node_id)
    payload = payload_by_id[node_id]
    node = NormalizedTaskNode(
        node_id=node_id,
        parent_id=parent_id,
        title=_required_str(payload, ("title",), ("tasks", node_id)),
        intent=_required_str(payload, ("intent",), ("tasks", node_id)),
        summary=_optional_str(payload, "summary"),
        instructions=_optional_str(payload, "instructions"),
        acceptance_criteria=_optional_str_tuple(payload, "acceptance_criteria", ("tasks", node_id)),
        required_capability=_required_str(
            payload,
            ("required_capability", "capability"),
            ("tasks", node_id),
        ),
        agent_ref=_optional_str(payload, "agent_ref") or _optional_str(payload, "agent"),
        children=tuple(
            _normalize_flat_node(
                child_id,
                parent_id=node_id,
                payload_by_id=payload_by_id,
                children_by_parent=children_by_parent,
                visiting=visiting,
                visited=visited,
            )
            for child_id in children_by_parent.get(node_id, ())
        ),
        metadata=_metadata(payload, ("tasks", node_id, "metadata")),
    )
    visiting.remove(node_id)
    visited.add(node_id)
    return node


def _has_parent_links(payloads: Sequence[Any]) -> bool:
    return any(isinstance(payload, Mapping) and "parent_id" in payload for payload in payloads)


def _required_str(
    payload: Mapping[str, Any],
    keys: tuple[str, ...],
    path: tuple[str, ...],
) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    label = " or ".join(keys)
    raise TaskTreeInputError(f"{'.'.join(path)} requires {label}")


def _optional_str(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _optional_str_tuple(
    payload: Mapping[str, Any],
    key: str,
    path: tuple[str, ...],
) -> tuple[str, ...]:
    value = payload.get(key, ())
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TaskTreeInputError(f"{'.'.join((*path, key))} must be a list")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise TaskTreeInputError(
                f"{'.'.join((*path, key, str(index)))} must be a non-empty string"
            )
        result.append(item.strip())
    return tuple(result)


def _metadata(payload: Mapping[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    value = payload.get("metadata", {})
    if not isinstance(value, Mapping):
        raise TaskTreeInputError(f"{'.'.join(path)} must be an object")
    return dict(value)


def _node_path(node: NormalizedTaskNode) -> tuple[str, ...]:
    return ("task", node.node_id)


__all__ = [
    "AgentCapabilityBinding",
    "AgentCapabilityCatalog",
    "StaticAgentCapabilityCatalog",
    "TaskTreeInputError",
    "TaskTreeInputFormat",
    "TaskTreeInputValidator",
    "TaskTreeValidation",
    "TaskTreeValidationIssue",
    "TaskTreeValidationSeverity",
    "normalize_task_tree_input",
    "parse_task_tree_input",
]
