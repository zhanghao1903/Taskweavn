"""Tests for LoggingManager and ObjectLogger."""

from __future__ import annotations

import json
from pathlib import Path

from taskweavn.observability import (
    LogContext,
    LoggingConfig,
    LoggingConfigPatch,
    LoggingManager,
    LogLevel,
    LogRule,
    LogSinkConfig,
    get_logging_manager,
    get_object_logger,
)


def _config(tmp_path: Path, *, llm_level: LogLevel = "INFO") -> LoggingConfig:
    return LoggingConfig(
        archive_root=str(tmp_path / "logs"),
        sinks={
            "session_file": LogSinkConfig(
                name="session_file",
                type="file",
                path_template="{archive_root}/sessions/{session_id}/{category}.jsonl",
            ),
        },
        rules={
            "llm": LogRule(
                category="llm",
                level=llm_level,
                sinks=("session_file",),
                payload_mode="full",
            ),
            "tool": LogRule(
                category="tool",
                level="INFO",
                sinks=("session_file",),
                payload_mode="off",
            ),
        },
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_default_manager_is_silent_until_configured() -> None:
    manager = LoggingManager()
    assert not manager.is_enabled("llm", "INFO")


def test_manager_writes_structured_jsonl(tmp_path: Path) -> None:
    manager = LoggingManager(_config(tmp_path))
    manager.emit(
        "llm",
        "INFO",
        "request",
        context=LogContext(session_id="s1", model="deepseek-chat"),
        data={"message_count": 2},
    )

    rows = _read_jsonl(tmp_path / "logs" / "sessions" / "s1" / "llm.jsonl")
    assert rows[0]["category"] == "llm"
    assert rows[0]["event"] == "request"
    assert rows[0]["msg"] == "request"
    assert rows[0]["context"] == {"session_id": "s1", "model": "deepseek-chat"}
    assert rows[0]["data"] == {"message_count": 2}


def test_lazy_payload_not_built_when_level_disabled(tmp_path: Path) -> None:
    manager = LoggingManager(_config(tmp_path, llm_level="INFO"))
    called = False

    def payload() -> dict[str, object]:
        nonlocal called
        called = True
        return {"raw_response": "large"}

    manager.emit(
        "llm",
        "DEBUG",
        "raw_response",
        context=LogContext(session_id="s1"),
        data=payload,
    )

    assert called is False
    assert not (tmp_path / "logs" / "sessions" / "s1" / "llm.jsonl").exists()


def test_payload_mode_off_skips_payload_and_file(tmp_path: Path) -> None:
    manager = LoggingManager(_config(tmp_path))
    called = False

    def payload() -> dict[str, object]:
        nonlocal called
        called = True
        return {"payload": "x"}

    manager.emit(
        "tool",
        "INFO",
        "invoke",
        context=LogContext(session_id="s1"),
        data=payload,
    )

    assert called is False
    assert not (tmp_path / "logs" / "sessions" / "s1" / "tool.jsonl").exists()


def test_session_override_only_affects_matching_session(tmp_path: Path) -> None:
    manager = LoggingManager(_config(tmp_path, llm_level="INFO"))
    manager.update_session_config(
        "debug-session",
        LoggingConfigPatch(
            rules={
                "llm": LogRule(
                    category="llm",
                    level="DEBUG",
                    sinks=("session_file",),
                    payload_mode="full",
                )
            }
        ),
    )

    manager.emit("llm", "DEBUG", "raw", context=LogContext(session_id="normal"))
    manager.emit("llm", "DEBUG", "raw", context=LogContext(session_id="debug-session"))

    assert not (tmp_path / "logs" / "sessions" / "normal" / "llm.jsonl").exists()
    assert (tmp_path / "logs" / "sessions" / "debug-session" / "llm.jsonl").exists()


def test_redaction_masks_secret_keys(tmp_path: Path) -> None:
    manager = LoggingManager(_config(tmp_path))
    manager.emit(
        "llm",
        "INFO",
        "request",
        context=LogContext(session_id="s1"),
        data={"api_key": "sk-secret", "nested": {"token": "abc"}},
    )

    row = _read_jsonl(tmp_path / "logs" / "sessions" / "s1" / "llm.jsonl")[0]
    assert row["data"] == {"api_key": "<redacted>", "nested": {"token": "<redacted>"}}


def test_object_logger_uses_global_manager(tmp_path: Path) -> None:
    get_logging_manager().apply_config(_config(tmp_path, llm_level="DEBUG"))
    logger = get_object_logger("llm")
    logger.debug(
        "raw_response",
        context=LogContext(session_id="s1"),
        data={"ok": True},
    )

    rows = _read_jsonl(tmp_path / "logs" / "sessions" / "s1" / "llm.jsonl")
    assert rows[-1]["event"] == "raw_response"
