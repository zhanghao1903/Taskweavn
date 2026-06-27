"""Trace-safe helpers for Plato UI HTTP transport diagnostics."""

from __future__ import annotations

from typing import Any


def safe_query(query: dict[str, str]) -> dict[str, str]:
    return {
        key: "<redacted>" if "token" in key.lower() or key == "cursor" else value
        for key, value in query.items()
    }


def path_without_query(path: str) -> str:
    return path.split("?", 1)[0]


def snapshot_response_summary(response: Any) -> dict[str, Any]:
    data = getattr(response, "data", None)
    error = getattr(response, "error", None)
    summary: dict[str, Any] = {
        "ok": getattr(response, "ok", None),
        "request_id": getattr(response, "request_id", None),
    }
    if error is not None:
        summary["error_code"] = getattr(error, "code", None)
        summary["error_message"] = getattr(error, "message", None)
        return summary
    if data is None:
        return summary

    session = getattr(data, "session", None)
    task_tree = getattr(data, "task_tree", None)
    nodes = tuple(getattr(task_tree, "nodes", ()) or ())
    summary.update(
        {
            "session_status": getattr(session, "status", None),
            "task_node_count": len(nodes),
            "task_nodes": tuple(_task_node_summary(node) for node in nodes),
            "task_tree_status": getattr(task_tree, "status", None),
        }
    )
    return summary


def _task_node_summary(node: Any) -> dict[str, Any]:
    return {
        "error_ref": getattr(node, "error_ref", None),
        "execution": getattr(node, "execution", None),
        "id": getattr(node, "id", None),
        "interruption_requested": getattr(node, "interruption_requested", None),
        "status": getattr(node, "status", None),
        "title": _short_text(getattr(node, "title", "")),
    }


def _short_text(value: Any, *, limit: int = 80) -> str:
    text = str(value)
    return text if len(text) <= limit else f"{text[:limit]}..."
