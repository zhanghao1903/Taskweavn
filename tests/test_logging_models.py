"""Tests for structured logging configuration models."""

from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from taskweavn.observability import LoggingConfig, LogRule, LogSinkConfig
from taskweavn.observability.levels import level_enabled, normalize_level


def test_normalize_level_accepts_names_and_stdlib_values() -> None:
    assert normalize_level("debug") == "DEBUG"
    assert normalize_level(logging.INFO) == "INFO"
    assert normalize_level(5) == "TRACE"


def test_level_enabled_respects_off() -> None:
    assert level_enabled("ERROR", "INFO")
    assert not level_enabled("DEBUG", "INFO")
    assert not level_enabled("CRITICAL", "OFF")


def test_file_sink_requires_path_template() -> None:
    with pytest.raises(ValidationError, match="file sink requires path_template"):
        LogSinkConfig(name="session_file", type="file")


def test_logging_config_rejects_unknown_sink_reference() -> None:
    with pytest.raises(ValidationError, match="unknown sinks"):
        LoggingConfig(
            archive_root="./logs",
            sinks={},
            rules={
                "llm": LogRule(
                    category="llm",
                    sinks=("missing",),
                )
            },
        )


def test_log_rule_normalizes_level() -> None:
    rule = LogRule.model_validate({"category": "llm", "level": "debug", "sinks": []})
    assert rule.level == "DEBUG"
