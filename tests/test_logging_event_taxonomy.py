"""Tests for structured log event naming stability."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from taskweavn.observability.events import (
    LOG_EVENTS_BY_CATEGORY,
    is_known_log_event,
    known_log_events,
)

PROJECT_ROOT = Path(__file__).parents[1]
SRC_ROOT = PROJECT_ROOT / "src" / "taskweavn"
LOGGER_METHODS = {"trace", "debug", "info", "warning", "error", "critical", "log"}
EVENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def test_event_taxonomy_names_are_snake_case() -> None:
    for category, events in LOG_EVENTS_BY_CATEGORY.items():
        assert known_log_events(category) == events
        for event in events:
            assert EVENT_NAME_RE.fullmatch(event), f"{category}.{event}"


def test_known_event_lookup() -> None:
    assert is_known_log_event("llm", "request")
    assert not is_known_log_event("llm", "surprise_event")


def test_current_object_logger_events_are_known() -> None:
    known_by_category = {
        str(category): set(events)
        for category, events in LOG_EVENTS_BY_CATEGORY.items()
    }
    failures: list[str] = []

    for path in sorted(SRC_ROOT.rglob("*.py")):
        for category, event, lineno in _collect_object_logger_events(path):
            if event not in known_by_category.get(category, set()):
                rel_path = path.relative_to(PROJECT_ROOT)
                failures.append(f"{rel_path}:{lineno} {category}.{event}")

    assert not failures, "Unknown structured log events:\n" + "\n".join(failures)


def _collect_object_logger_events(path: Path) -> list[tuple[str, str, int]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    logger_categories = _logger_categories(tree)
    events: list[tuple[str, str, int]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in LOGGER_METHODS:
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        category = logger_categories.get(node.func.value.id)
        if category is None or not node.args:
            continue
        event_arg = node.args[1] if node.func.attr == "log" and len(node.args) > 1 else node.args[0]
        if isinstance(event_arg, ast.Constant) and isinstance(event_arg.value, str):
            events.append((category, event_arg.value, node.lineno))

    return events


def _logger_categories(tree: ast.AST) -> dict[str, str]:
    categories: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        if not isinstance(node.value.func, ast.Name):
            continue
        if node.value.func.id != "get_object_logger":
            continue
        if not node.value.args:
            continue
        category_arg = node.value.args[0]
        if not (
            isinstance(category_arg, ast.Constant)
            and isinstance(category_arg.value, str)
        ):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                categories[target.id] = category_arg.value
    return categories
