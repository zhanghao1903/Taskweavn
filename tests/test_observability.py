"""Tests for observability/setup and end-to-end log emission."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from taskweavn.core.event_stream import InMemoryEventStream
from taskweavn.observability import CHANNELS, configure_logging, get_channel_logger
from taskweavn.runtime.local import LocalRuntime
from taskweavn.tools.fs import ReadFileTool, WriteFileAction, WriteFileTool
from taskweavn.tools.workspace import Workspace
from taskweavn.types import AgentFinishAction


@pytest.fixture()
def log_dir(tmp_path: Path) -> Iterator[Path]:
    configure_logging(tmp_path / "logs")
    yield tmp_path / "logs"
    # Tear down: remove file handlers attached during the test so other tests
    # (and a leftover handler pointing at a deleted tmp path) don't leak.
    for channel in CHANNELS:
        logger = get_channel_logger(channel)
        for handler in list(logger.handlers):
            if isinstance(handler, logging.FileHandler):
                handler.close()
                logger.removeHandler(handler)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_configure_logging_creates_files(tmp_path: Path) -> None:
    paths = configure_logging(tmp_path / "logs")
    assert set(paths.keys()) == set(CHANNELS)
    for channel, path in paths.items():
        assert path == tmp_path / "logs" / f"{channel}.log"
        # File handler should have created the file already.
        assert path.exists()


def test_configure_logging_unknown_channel_lookup_raises() -> None:
    with pytest.raises(ValueError, match="unknown logging channel"):
        get_channel_logger("nope")


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    configure_logging(tmp_path / "logs")
    configure_logging(tmp_path / "logs")
    for channel in CHANNELS:
        logger = get_channel_logger(channel)
        file_handlers = [
            h for h in logger.handlers if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) == 1


def test_runtime_logs_invoke_and_result(log_dir: Path, tmp_path: Path) -> None:
    ws = Workspace(tmp_path)
    rt = LocalRuntime()
    WriteFileTool(ws).register(rt)

    rt.execute(WriteFileAction(path="hello.txt", content="hi"))

    tool_entries = _read_jsonl(log_dir / "tool.log")
    msgs = [e["msg"] for e in tool_entries]
    assert msgs == ["invoke", "result"]
    assert tool_entries[0]["category"] == "tool"
    assert tool_entries[0]["event"] == "invoke"
    assert tool_entries[0]["level"] == "INFO"
    invoke = tool_entries[0]["data"]
    assert invoke["action_kind"] == "WriteFileAction"
    assert invoke["payload"]["path"] == "hello.txt"
    result = tool_entries[1]["data"]
    assert result["action_kind"] == "WriteFileAction"
    assert result["result_kind"] == "FileWriteObservation"
    assert result["success"] is True
    assert "duration_ms" in result


def test_runtime_logs_no_executor_as_error(log_dir: Path) -> None:
    rt = LocalRuntime()
    rt.execute(AgentFinishAction(final_answer="x"))  # no executor registered

    tool_entries = _read_jsonl(log_dir / "tool.log")
    result_entry = next(e for e in tool_entries if e["msg"] == "result")
    assert result_entry["data"]["result_kind"] == "ErrorObservation"
    assert result_entry["data"]["success"] is False


def test_event_stream_logs_action_and_observation(
    log_dir: Path, tmp_path: Path
) -> None:
    ws = Workspace(tmp_path)
    stream = InMemoryEventStream()

    action = WriteFileAction(path="a.txt", content="x")
    stream.append(action)
    observation = WriteFileTool(ws).execute(action)
    stream.append(observation)

    actions = _read_jsonl(log_dir / "action.log")
    observations = _read_jsonl(log_dir / "observation.log")

    assert len(actions) == 1
    assert actions[0]["data"]["kind"] == "WriteFileAction"
    assert actions[0]["data"]["path"] == "a.txt"

    assert len(observations) == 1
    assert observations[0]["data"]["kind"] == "FileWriteObservation"
    assert observations[0]["data"]["bytes_written"] == 1


def test_loggers_silent_without_configure(tmp_path: Path) -> None:
    """Without configure_logging, no file handler is attached and emissions are dropped."""
    # Pre-condition: ensure the module's NullHandler is the only handler.
    for channel in CHANNELS:
        logger = get_channel_logger(channel)
        for h in list(logger.handlers):
            if isinstance(h, logging.FileHandler):
                logger.removeHandler(h)
                h.close()

    ws = Workspace(tmp_path)
    rt = LocalRuntime()
    WriteFileTool(ws).register(rt)
    rt.execute(WriteFileAction(path="x.txt", content="y"))
    # Nothing to assert about files — the call simply must not raise and no
    # log directory is created.
    assert not (tmp_path / "logs").exists()


def test_unknown_channel_in_configure_path_is_caught() -> None:
    # configure_logging only iterates known CHANNELS so this is a
    # direct check of get_channel_logger validation.
    with pytest.raises(ValueError):
        get_channel_logger("bogus")


def test_workspace_round_trip_with_read_tool(log_dir: Path, tmp_path: Path) -> None:
    """Sanity: a successful read also emits invoke + result with success=True."""
    (tmp_path / "f.txt").write_text("body")
    ws = Workspace(tmp_path)
    rt = LocalRuntime()
    ReadFileTool(ws).register(rt)

    from taskweavn.tools.fs import ReadFileAction

    rt.execute(ReadFileAction(path="f.txt"))
    tool_entries = _read_jsonl(log_dir / "tool.log")
    assert tool_entries[-1]["data"]["success"] is True
    assert tool_entries[-1]["data"]["result_kind"] == "FileContentObservation"
