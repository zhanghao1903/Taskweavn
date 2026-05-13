"""Tests for the same-process logging control surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from taskweavn.observability import (
    LogArchiveManifest,
    LoggingControlService,
    LoggingManager,
    build_session_logging_config,
)


def _manager(tmp_path: Path) -> LoggingManager:
    return LoggingManager(build_session_logging_config(tmp_path / "logs"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_control_lists_profiles(tmp_path: Path) -> None:
    service = LoggingControlService(_manager(tmp_path))

    profiles = service.list_profiles()
    names = {profile.name for profile in profiles}

    assert "debug-llm" in names
    assert "full-debug" in names
    assert all(profile.description for profile in profiles)


def test_apply_profile_updates_effective_rule_and_manifest(tmp_path: Path) -> None:
    service = LoggingControlService(_manager(tmp_path))

    result = service.apply_profile(session_id="s1", profile_name="debug-llm")

    assert result.operation == "apply_profile"
    assert result.profile == "debug-llm"
    assert result.manifest is not None
    assert result.manifest.session_id == "s1"
    assert service.get_effective_rule(category="llm", session_id="s1").level == "DEBUG"
    assert service.get_effective_rule(category="llm", session_id="normal").level == "INFO"
    assert (tmp_path / "logs" / "sessions" / "s1" / "manifest.json").exists()


def test_set_session_level_is_scoped(tmp_path: Path) -> None:
    service = LoggingControlService(_manager(tmp_path))

    result = service.set_level(session_id="s1", category="bus", level="DEBUG")

    assert result.operation == "set_level"
    assert result.session_id == "s1"
    assert result.category == "bus"
    assert result.level == "DEBUG"
    assert result.manifest is not None
    assert service.get_effective_rule(category="bus", session_id="s1").level == "DEBUG"
    assert service.get_effective_rule(category="bus", session_id="s2").level == "INFO"


def test_set_global_level_affects_all_sessions(tmp_path: Path) -> None:
    service = LoggingControlService(_manager(tmp_path))

    result = service.set_level(category="tool", level="ERROR")

    assert result.session_id is None
    assert result.manifest is None
    assert service.get_effective_rule(category="tool", session_id="s1").level == "ERROR"
    assert service.get_effective_rule(category="tool", session_id="s2").level == "ERROR"


def test_set_level_zero_duration_expires_immediately(tmp_path: Path) -> None:
    service = LoggingControlService(_manager(tmp_path))

    result = service.set_level(
        session_id="s1",
        category="llm",
        level="DEBUG",
        duration_seconds=0,
    )

    assert result.duration_seconds == 0
    assert service.get_effective_rule(category="llm", session_id="s1").level == "INFO"


def test_set_level_rejects_negative_duration(tmp_path: Path) -> None:
    service = LoggingControlService(_manager(tmp_path))

    with pytest.raises(ValueError, match="duration_seconds"):
        service.set_level(
            session_id="s1",
            category="llm",
            level="DEBUG",
            duration_seconds=-1,
        )


def test_control_close_session_archive_marks_closed(tmp_path: Path) -> None:
    service = LoggingControlService(_manager(tmp_path))
    service.apply_profile(session_id="s1", profile_name="debug-llm")

    result = service.close_session_archive(session_id="s1")

    assert result.operation == "close_session"
    assert result.manifest is not None
    assert result.manifest.closed_at is not None
    from_disk = LogArchiveManifest.model_validate_json(
        (tmp_path / "logs" / "sessions" / "s1" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert from_disk.closed_at == result.manifest.closed_at


def test_control_writes_config_events(tmp_path: Path) -> None:
    service = LoggingControlService(_manager(tmp_path))

    service.apply_profile(session_id="s1", profile_name="debug-llm")
    service.set_level(session_id="s1", category="bus", level="DEBUG")

    rows = _read_jsonl(tmp_path / "logs" / "sessions" / "s1" / "config.jsonl")
    events = [row["event"] for row in rows]
    assert "profile_applied" in events
    assert "level_set" in events
