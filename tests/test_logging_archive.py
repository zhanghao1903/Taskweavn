"""Tests for session log archive layout and entry points."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from taskweavn.core.event_stream import InMemoryEventStream
from taskweavn.observability import (
    LogArchiveManifest,
    LogContext,
    LoggingConfigPatch,
    LoggingManager,
    LogRule,
    LogSinkConfig,
    configure_session_logging,
    get_logging_manager,
    load_logging_config,
    use_log_context,
)
from taskweavn.observability.manager import build_session_logging_config
from taskweavn.runtime.local import LocalRuntime
from taskweavn.tools.fs import WriteFileAction, WriteFileTool
from taskweavn.tools.workspace import Workspace


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_configure_session_logging_writes_manifest(tmp_path: Path) -> None:
    manifest = configure_session_logging(tmp_path / "logs", session_id="s1")

    manifest_path = tmp_path / "logs" / "sessions" / "s1" / "manifest.json"
    assert manifest_path.exists()
    from_disk = LogArchiveManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    assert from_disk == manifest
    assert from_disk.session_id == "s1"
    assert from_disk.files["llm"] == "llm.jsonl"
    assert from_disk.files["tool"] == "tool.jsonl"
    assert from_disk.templates == {}
    assert from_disk.rotation["enabled"] is True


def test_manifest_uses_effective_session_rule_templates(tmp_path: Path) -> None:
    base_config = build_session_logging_config(tmp_path / "logs")
    sinks = dict(base_config.sinks)
    sinks["task_file"] = LogSinkConfig(
        name="task_file",
        type="file",
        path_template=(
            "{archive_root}/sessions/{session_id}/tasks/{task_id}/{category}.jsonl"
        ),
    )
    manager = LoggingManager(base_config.model_copy(update={"sinks": sinks}))
    manager.update_session_config(
        "s1",
        LoggingConfigPatch(
            rules={
                "llm": LogRule(
                    category="llm",
                    level="DEBUG",
                    sinks=("task_file",),
                    payload_mode="full",
                )
            }
        ),
    )

    manifest = manager.write_session_manifest("s1")

    assert "llm" not in manifest.files
    assert manifest.templates["llm"] == "tasks/{task_id}/llm.jsonl"
    assert manifest.files["tool"] == "tool.jsonl"


def test_session_logging_writes_category_file_under_session(tmp_path: Path) -> None:
    configure_session_logging(tmp_path / "logs", session_id="s1")
    get_logging_manager().emit(
        "llm",
        "INFO",
        "request",
        context=LogContext(session_id="s1", model="deepseek-chat"),
        data={"message_count": 2},
    )

    rows = _read_jsonl(tmp_path / "logs" / "sessions" / "s1" / "llm.jsonl")
    assert rows[0]["category"] == "llm"
    assert rows[0]["context"] == {"session_id": "s1", "model": "deepseek-chat"}


def test_ambient_context_routes_core_object_logs_to_session_archive(
    tmp_path: Path,
) -> None:
    configure_session_logging(tmp_path / "logs", session_id="s1")
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    workspace = Workspace(workspace_root)
    runtime = LocalRuntime()
    WriteFileTool(workspace).register(runtime)
    stream = InMemoryEventStream()
    action = WriteFileAction(path="hello.txt", content="hi")

    with use_log_context(LogContext(session_id="s1", task_id="task-1")):
        stream.append(action)
        observation = runtime.execute(action)
        stream.append(observation)

    action_rows = _read_jsonl(tmp_path / "logs" / "sessions" / "s1" / "action.jsonl")
    tool_rows = _read_jsonl(tmp_path / "logs" / "sessions" / "s1" / "tool.jsonl")
    observation_rows = _read_jsonl(
        tmp_path / "logs" / "sessions" / "s1" / "observation.jsonl"
    )
    action_context = action_rows[0]["context"]
    tool_context = tool_rows[0]["context"]
    observation_context = observation_rows[0]["context"]
    assert isinstance(action_context, dict)
    assert isinstance(tool_context, dict)
    assert isinstance(observation_context, dict)

    assert action_context["task_id"] == "task-1"
    assert action_context["action_id"] == action.event_id
    assert tool_context["tool_name"] == "WriteFileAction"
    assert tool_context["session_id"] == "s1"
    assert observation_context["observation_id"] == observation.event_id


def test_debug_llm_profile_is_session_scoped(tmp_path: Path) -> None:
    configure_session_logging(
        tmp_path / "logs",
        session_id="debug-session",
        profile="debug-llm",
    )
    manager = get_logging_manager()
    manager.emit(
        "llm",
        "DEBUG",
        "raw",
        context=LogContext(session_id="normal"),
        data={"raw_response": "hidden"},
    )
    manager.emit(
        "llm",
        "DEBUG",
        "raw",
        context=LogContext(session_id="debug-session"),
        data={"raw_response": "visible"},
    )

    assert not (tmp_path / "logs" / "sessions" / "normal" / "llm.jsonl").exists()
    rows = _read_jsonl(
        tmp_path / "logs" / "sessions" / "debug-session" / "llm.jsonl"
    )
    assert rows[-1]["data"] == {"raw_response": "visible"}


def test_close_session_archive_marks_manifest_closed(tmp_path: Path) -> None:
    configure_session_logging(tmp_path / "logs", session_id="s1")
    closed = get_logging_manager().close_session_archive("s1")

    assert closed.closed_at is not None
    from_disk = LogArchiveManifest.model_validate_json(
        (tmp_path / "logs" / "sessions" / "s1" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert from_disk.closed_at == closed.closed_at


def test_load_logging_config_rejects_yaml_until_config_layer_owns_it(
    tmp_path: Path,
) -> None:
    path = tmp_path / "logging.yaml"
    path.write_text("logging: {}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="YAML logging config"):
        load_logging_config(path)


def test_load_logging_config_accepts_json(tmp_path: Path) -> None:
    config = build_session_logging_config(tmp_path / "logs")
    path = tmp_path / "logging.json"
    path.write_text(config.model_dump_json(), encoding="utf-8")

    loaded = load_logging_config(path)
    assert loaded == config
