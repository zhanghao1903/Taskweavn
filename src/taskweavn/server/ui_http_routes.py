"""HTTP route matching helpers for Plato UI transport."""

from __future__ import annotations

from dataclasses import dataclass, replace
from urllib.parse import unquote, urlsplit


@dataclass(frozen=True)
class _Route:
    name: str
    method: str
    workspace_id: str = ""
    session_id: str = ""
    raw_task_id: str = ""
    task_node_id: str = ""
    confirmation_id: str = ""
    ask_id: str = ""
    record_id: str = ""
    evidence_id: str = ""


def _match_route(path: str) -> _Route | None:
    parts = _path_parts(path)
    if parts == ():
        return _Route(name="root", method="GET")
    if parts == ("api", "v1", "health"):
        return _Route(name="health", method="GET")
    if parts == ("api", "v1", "settings", "readiness"):
        return _Route(name="settings_readiness", method="GET")
    if parts == ("api", "v1", "settings", "readiness", "recheck"):
        return _Route(name="settings_readiness_recheck", method="POST")
    if parts == ("api", "v1", "settings", "config"):
        return _Route(name="settings_config", method="*")
    if parts == ("api", "v1", "workspaces"):
        return _Route(name="workspaces", method="GET")
    workspace_route = _match_workspace_route(parts)
    if workspace_route is not None:
        return workspace_route
    if parts == ("api", "v1", "usage", "token-summary"):
        return _Route(name="usage_token_summary", method="GET")
    if parts == ("api", "v1", "inspection", "status"):
        return _Route(name="workspace_inspection_status", method="GET")
    if parts == ("api", "v1", "inspection", "diff"):
        return _Route(name="workspace_inspection_diff", method="GET")
    if parts == ("api", "v1", "inspection", "evidence"):
        return _Route(name="workspace_inspection_evidence", method="POST")
    if parts == ("api", "v1", "files", "content"):
        return _Route(name="workspace_file_content", method="GET")
    if parts == ("api", "v1", "sessions"):
        return _Route(name="sessions", method="*")
    if len(parts) < 4 or parts[:3] != ("api", "v1", "sessions"):
        return None
    session_id = parts[3]
    suffix = parts[4:]
    if suffix == ("snapshot",):
        return _Route(name="snapshot", method="GET", session_id=session_id)
    if suffix == ("activity",):
        return _Route(name="session_activity", method="GET", session_id=session_id)
    if suffix == ("runtime-input", "route"):
        return _Route(name="runtime_input_route", method="POST", session_id=session_id)
    if suffix == ("audit",):
        return _Route(name="audit_snapshot", method="GET", session_id=session_id)
    if suffix == ("audit", "records"):
        return _Route(name="audit_records", method="GET", session_id=session_id)
    if len(suffix) == 3 and suffix[:2] == ("audit", "records"):
        return _Route(
            name="audit_record_detail",
            method="GET",
            session_id=session_id,
            record_id=suffix[2],
        )
    if len(suffix) == 3 and suffix[:2] == ("audit", "evidence"):
        return _Route(
            name="audit_evidence_detail",
            method="GET",
            session_id=session_id,
            evidence_id=suffix[2],
        )
    if suffix == ():
        return _Route(name="rename_session", method="PATCH", session_id=session_id)
    if suffix == ("delete",):
        return _Route(name="delete_session", method="POST", session_id=session_id)
    if suffix == ("input",):
        return _Route(name="append_session_input", method="POST", session_id=session_id)
    if suffix == ("task-tree", "generate"):
        return _Route(name="generate_task_tree", method="POST", session_id=session_id)
    if suffix == ("task-tree", "publish"):
        return _Route(name="publish_task_tree", method="POST", session_id=session_id)
    if suffix == ("authoring", "repair"):
        return _Route(name="repair_authoring_state", method="POST", session_id=session_id)
    if (
        len(suffix) == 5
        and suffix[0] == "authoring"
        and suffix[1] == "raw-tasks"
        and suffix[3:] == ("asks", "answers")
    ):
        return _Route(
            name="answer_authoring_ask_batch",
            method="POST",
            session_id=session_id,
            raw_task_id=suffix[2],
        )
    if suffix == ("execution", "dispatch"):
        return _Route(name="dispatch_execution", method="POST", session_id=session_id)
    if suffix == ("events",):
        return _Route(name="events", method="GET", session_id=session_id)
    if suffix == ("client-logs", "errors"):
        return _Route(name="client_error_log", method="POST", session_id=session_id)
    if suffix == ("diagnostics", "export"):
        return _Route(name="diagnostics_export", method="POST", session_id=session_id)
    if len(suffix) == 2 and suffix[0] == "tasks":
        return _Route(
            name="update_task_node",
            method="PATCH",
            session_id=session_id,
            task_node_id=suffix[1],
        )
    if len(suffix) == 3 and suffix[0] == "tasks" and suffix[2] == "input":
        return _Route(
            name="append_task_input",
            method="POST",
            session_id=session_id,
            task_node_id=suffix[1],
        )
    if len(suffix) == 3 and suffix[0] == "tasks" and suffix[2] == "audit":
        return _Route(
            name="audit_snapshot",
            method="GET",
            session_id=session_id,
            task_node_id=suffix[1],
        )
    if (
        len(suffix) == 4
        and suffix[0] == "tasks"
        and suffix[2:] == ("audit", "records")
    ):
        return _Route(
            name="audit_records",
            method="GET",
            session_id=session_id,
            task_node_id=suffix[1],
        )
    if len(suffix) == 3 and suffix[0] == "tasks" and suffix[2] == "retry":
        return _Route(
            name="retry_task",
            method="POST",
            session_id=session_id,
            task_node_id=suffix[1],
        )
    if len(suffix) == 3 and suffix[0] == "tasks" and suffix[2] == "stop":
        return _Route(
            name="stop_task",
            method="POST",
            session_id=session_id,
            task_node_id=suffix[1],
        )
    if len(suffix) == 3 and suffix[0] == "confirmations" and suffix[2] == "respond":
        return _Route(
            name="resolve_confirmation",
            method="POST",
            session_id=session_id,
            confirmation_id=suffix[1],
        )
    if suffix == ("asks",):
        return _Route(name="asks", method="GET", session_id=session_id)
    if len(suffix) == 2 and suffix[0] == "asks":
        return _Route(
            name="ask_detail",
            method="GET",
            session_id=session_id,
            ask_id=suffix[1],
        )
    if len(suffix) == 3 and suffix[0] == "asks" and suffix[2] == "answer":
        return _Route(
            name="answer_ask",
            method="POST",
            session_id=session_id,
            ask_id=suffix[1],
        )
    if len(suffix) == 3 and suffix[0] == "asks" and suffix[2] == "defer":
        return _Route(
            name="defer_ask",
            method="POST",
            session_id=session_id,
            ask_id=suffix[1],
        )
    if len(suffix) == 3 and suffix[0] == "asks" and suffix[2] == "cancel":
        return _Route(
            name="cancel_ask",
            method="POST",
            session_id=session_id,
            ask_id=suffix[1],
        )
    return None


def _match_workspace_route(parts: tuple[str, ...]) -> _Route | None:
    if len(parts) < 5 or parts[:3] != ("api", "v1", "workspaces"):
        return None
    workspace_id = parts[3]
    active_workspace_parts = ("api", "v1", *parts[4:])
    active_workspace_route = _match_route("/" + "/".join(active_workspace_parts))
    if active_workspace_route is None:
        return None
    return replace(active_workspace_route, workspace_id=workspace_id)


def _path_parts(path: str) -> tuple[str, ...]:
    split = urlsplit(path)
    raw_path = split.path or path
    return tuple(unquote(part) for part in raw_path.strip("/").split("/") if part)
