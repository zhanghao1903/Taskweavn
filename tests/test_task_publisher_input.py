"""Tests for custom Task Tree parser and validation boundaries."""

from __future__ import annotations

import json

import pytest

from taskweavn.task import (
    AgentCapabilityCatalog,
    NormalizedTaskTree,
    PublisherRef,
    StaticAgentCapabilityCatalog,
    StaticCapabilityCatalog,
    TaskTreeInputError,
    TaskTreeInputValidator,
    normalize_task_tree_input,
    parse_task_tree_input,
)


def test_agent_capability_catalog_protocol_conformance() -> None:
    catalog = StaticAgentCapabilityCatalog(
        [{"agent_ref": "agent.summary", "capabilities": ("summarize", "testing")}]
    )

    assert isinstance(catalog, AgentCapabilityCatalog)
    assert catalog.supports("agent.summary", "summarize")
    assert not catalog.supports("agent.summary", "release")


def test_parse_json_nested_task_tree() -> None:
    publisher = _publisher()
    payload = {
        "id": "tree-1",
        "metadata": {"origin": "fixture", "override": "payload"},
        "tasks": [
            {
                "id": "inspect",
                "title": "Inspect",
                "intent": "Inspect project",
                "required_capability": "summarize",
                "agent": "agent.summary",
                "children": [
                    {
                        "id": "tests",
                        "title": "Tests",
                        "intent": "Inspect tests",
                        "capability": "testing",
                        "metadata": {"scope": "tests"},
                    }
                ],
            }
        ],
    }

    tree = parse_task_tree_input(
        json.dumps(payload),
        publisher=publisher,
        metadata={"override": "caller", "caller": True},
    )
    root = tree.root_nodes[0]
    child = root.children[0]

    assert isinstance(tree, NormalizedTaskTree)
    assert tree.source == publisher
    assert tree.source_ref == "tree-1"
    assert tree.metadata == {
        "origin": "fixture",
        "override": "caller",
        "caller": True,
    }
    assert root.node_id == "inspect"
    assert root.parent_id is None
    assert root.agent_ref == "agent.summary"
    assert child.node_id == "tests"
    assert child.parent_id == "inspect"
    assert child.required_capability == "testing"
    assert child.metadata["scope"] == "tests"


def test_parse_yaml_task_tree() -> None:
    tree = parse_task_tree_input(
        """
        name: nightly
        tasks:
          - id: summarize
            title: Summarize
            intent: Summarize the current session
            capability: summarize
            agent_ref: agent.summary
        """,
        publisher=_publisher(),
        input_format="yaml",
    )

    assert tree.source_ref == "nightly"
    assert tree.root_nodes[0].node_id == "summarize"
    assert tree.root_nodes[0].agent_ref == "agent.summary"


def test_parse_auto_detects_json_bytes() -> None:
    payload = {
        "tasks": [
            {
                "id": "root",
                "title": "Root",
                "intent": "Do root",
                "capability": "general",
            }
        ]
    }

    tree = parse_task_tree_input(json.dumps(payload).encode(), publisher=_publisher())

    assert tree.root_ids == ("root",)


def test_normalize_flat_parent_id_tree() -> None:
    tree = normalize_task_tree_input(
        {
            "tasks": [
                {
                    "id": "root",
                    "title": "Root",
                    "intent": "Do root",
                    "capability": "general",
                },
                {
                    "id": "child",
                    "parent_id": "root",
                    "title": "Child",
                    "intent": "Do child",
                    "capability": "testing",
                    "agent": "agent.test",
                },
            ]
        },
        publisher=_publisher(),
    )

    assert tree.root_ids == ("root",)
    assert tree.root_nodes[0].children[0].node_id == "child"
    assert tree.root_nodes[0].children[0].parent_id == "root"
    assert tree.root_nodes[0].children[0].agent_ref == "agent.test"


def test_parse_rejects_malformed_json() -> None:
    with pytest.raises(TaskTreeInputError, match="failed to parse json"):
        parse_task_tree_input("{not json", publisher=_publisher(), input_format="json")


def test_parse_rejects_non_object_input() -> None:
    with pytest.raises(TaskTreeInputError, match="must be an object"):
        parse_task_tree_input("[]", publisher=_publisher(), input_format="json")


def test_parse_rejects_missing_task_list() -> None:
    with pytest.raises(TaskTreeInputError, match="requires a tasks/root_nodes list"):
        parse_task_tree_input("{}", publisher=_publisher(), input_format="json")


def test_parse_rejects_missing_intent() -> None:
    with pytest.raises(TaskTreeInputError, match="requires intent"):
        normalize_task_tree_input(
            {
                "tasks": [
                    {
                        "id": "root",
                        "title": "Root",
                        "capability": "general",
                    }
                ]
            },
            publisher=_publisher(),
        )


def test_parse_rejects_missing_capability() -> None:
    with pytest.raises(TaskTreeInputError, match="requires required_capability or capability"):
        normalize_task_tree_input(
            {
                "tasks": [
                    {
                        "id": "root",
                        "title": "Root",
                        "intent": "Do root",
                    }
                ]
            },
            publisher=_publisher(),
        )


def test_parse_rejects_non_object_metadata() -> None:
    with pytest.raises(TaskTreeInputError, match="metadata must be an object"):
        normalize_task_tree_input(
            {
                "metadata": ["bad"],
                "tasks": [
                    {
                        "id": "root",
                        "title": "Root",
                        "intent": "Do root",
                        "capability": "general",
                    }
                ],
            },
            publisher=_publisher(),
        )


def test_nested_tree_rejects_duplicate_node_id() -> None:
    with pytest.raises(ValueError, match="duplicate normalized task node id"):
        normalize_task_tree_input(
            {
                "tasks": [
                    {
                        "id": "root",
                        "title": "Root",
                        "intent": "Do root",
                        "capability": "general",
                        "children": [
                            {
                                "id": "root",
                                "title": "Duplicate",
                                "intent": "Duplicate root",
                                "capability": "general",
                            }
                        ],
                    }
                ]
            },
            publisher=_publisher(),
        )


def test_flat_tree_rejects_duplicate_node_id() -> None:
    payload = {
        "tasks": [
            {
                "id": "root",
                "title": "Root",
                "intent": "Do root",
                "capability": "general",
            },
            {
                "id": "root",
                "parent_id": "parent",
                "title": "Duplicate",
                "intent": "Duplicate root",
                "capability": "general",
            },
        ]
    }

    with pytest.raises(TaskTreeInputError, match="duplicate task id"):
        normalize_task_tree_input(payload, publisher=_publisher())


def test_flat_tree_rejects_unknown_parent() -> None:
    payload = {
        "tasks": [
            {
                "id": "child",
                "parent_id": "missing",
                "title": "Child",
                "intent": "Do child",
                "capability": "general",
            }
        ]
    }

    with pytest.raises(TaskTreeInputError, match="unknown parent"):
        normalize_task_tree_input(payload, publisher=_publisher())


def test_flat_tree_rejects_cycle_without_root() -> None:
    payload = {
        "tasks": [
            {
                "id": "a",
                "parent_id": "b",
                "title": "A",
                "intent": "Do A",
                "capability": "general",
            },
            {
                "id": "b",
                "parent_id": "a",
                "title": "B",
                "intent": "Do B",
                "capability": "general",
            },
        ]
    }

    with pytest.raises(TaskTreeInputError, match="no root tasks"):
        normalize_task_tree_input(payload, publisher=_publisher())


def test_validator_reports_unknown_capability() -> None:
    tree = _tree_with_capability("testing")
    validator = TaskTreeInputValidator(capability_catalog=StaticCapabilityCatalog(["summarize"]))

    validation = validator.validate(tree)

    assert not validation.valid
    assert validation.errors[0].code == "unknown_capability"
    assert validation.errors[0].path == ("task", "root")


def test_validator_reports_agent_capability_mismatch() -> None:
    tree = _tree_with_capability("testing", agent_ref="agent.summary")
    validator = TaskTreeInputValidator(
        capability_catalog=StaticCapabilityCatalog(["testing"]),
        agent_catalog=StaticAgentCapabilityCatalog(
            [{"agent_ref": "agent.summary", "capabilities": ("summarize",)}]
        ),
    )

    validation = validator.validate(tree)

    assert not validation.valid
    assert validation.errors[0].code == "agent_capability_mismatch"


def test_validator_accepts_known_capability_and_matching_agent() -> None:
    tree = _tree_with_capability("testing", agent_ref="agent.test")
    validator = TaskTreeInputValidator(
        capability_catalog=StaticCapabilityCatalog(["testing"]),
        agent_catalog=StaticAgentCapabilityCatalog(
            [{"agent_ref": "agent.test", "capabilities": ("testing",)}]
        ),
    )

    validation = validator.validate(tree)

    assert validation.valid
    assert validation.errors == ()
    assert validation.warnings == ()


def _tree_with_capability(
    capability: str,
    *,
    agent_ref: str | None = None,
) -> NormalizedTaskTree:
    payload = {
        "tasks": [
            {
                "id": "root",
                "title": "Root",
                "intent": "Do root",
                "capability": capability,
                "agent_ref": agent_ref,
            }
        ]
    }
    return normalize_task_tree_input(payload, publisher=_publisher())


def _publisher() -> PublisherRef:
    return PublisherRef(kind="custom_tree", actor_id="user-1")
