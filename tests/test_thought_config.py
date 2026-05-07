"""Tests for ThoughtConfig + build_store (Phase 2.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from code_agent.memory import (
    NullThoughtStore,
    SqliteThoughtStore,
    ThoughtConfig,
    ThoughtConfigError,
    build_store,
)


def test_defaults_are_off_and_null() -> None:
    cfg = ThoughtConfig()
    assert cfg.enabled is False
    assert cfg.backend == "null"
    assert cfg.db_path is None
    assert cfg.phases is None


def test_unknown_backend_rejected() -> None:
    with pytest.raises(ThoughtConfigError):
        ThoughtConfig(backend="redis")  # type: ignore[arg-type]


def test_sqlite_requires_db_path_when_enabled() -> None:
    with pytest.raises(ThoughtConfigError):
        ThoughtConfig(enabled=True, backend="sqlite", db_path=None)


def test_sqlite_db_path_unused_when_disabled() -> None:
    cfg = ThoughtConfig(enabled=False, backend="sqlite", db_path=None)
    # Must not raise: disabled configs always materialize as NullThoughtStore.
    assert isinstance(build_store(cfg), NullThoughtStore)


def test_build_store_returns_null_for_disabled(tmp_path: Path) -> None:
    cfg = ThoughtConfig(
        enabled=False, backend="sqlite", db_path=tmp_path / "x.sqlite"
    )
    assert isinstance(build_store(cfg), NullThoughtStore)


def test_build_store_returns_sqlite_when_enabled(tmp_path: Path) -> None:
    db = tmp_path / "x.sqlite"
    cfg = ThoughtConfig(enabled=True, backend="sqlite", db_path=db)
    store = build_store(cfg)
    assert isinstance(store, SqliteThoughtStore)
    try:
        assert store.db_path == db
    finally:
        store.close()


def test_build_store_passes_phase_filter(tmp_path: Path) -> None:
    db = tmp_path / "x.sqlite"
    cfg = ThoughtConfig(
        enabled=True,
        backend="sqlite",
        db_path=db,
        phases=("plan",),
    )
    store = build_store(cfg)
    assert isinstance(store, SqliteThoughtStore)
    try:
        # Filter is applied — non-allowed phases are dropped.
        from datetime import UTC, datetime

        from code_agent.memory import ThoughtRecord

        store.write(
            ThoughtRecord(
                event_id="e",
                phase="reason",
                content="dropped",
                timestamp=datetime(2026, 5, 4, tzinfo=UTC),
            )
        )
        store.write(
            ThoughtRecord(
                event_id="e",
                phase="plan",
                content="kept",
                timestamp=datetime(2026, 5, 4, tzinfo=UTC),
            )
        )
        assert len(store) == 1
    finally:
        store.close()


# ---------------------------------------------------------------------------
# from_env()
# ---------------------------------------------------------------------------


def test_from_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "THOUGHTS_ENABLED",
        "THOUGHTS_BACKEND",
        "THOUGHTS_DB_PATH",
        "THOUGHTS_PHASES",
    ):
        monkeypatch.delenv(var, raising=False)
    cfg = ThoughtConfig.from_env()
    assert cfg.enabled is False
    assert cfg.backend == "null"
    assert cfg.db_path is None
    assert cfg.phases is None


def test_from_env_full(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite"
    monkeypatch.setenv("THOUGHTS_ENABLED", "yes")
    monkeypatch.setenv("THOUGHTS_BACKEND", "sqlite")
    monkeypatch.setenv("THOUGHTS_DB_PATH", str(db))
    monkeypatch.setenv("THOUGHTS_PHASES", "plan, reason ,")
    cfg = ThoughtConfig.from_env()
    assert cfg.enabled is True
    assert cfg.backend == "sqlite"
    assert cfg.db_path == db
    assert cfg.phases == ("plan", "reason")


def test_from_env_rejects_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THOUGHTS_BACKEND", "redis")
    with pytest.raises(ThoughtConfigError):
        ThoughtConfig.from_env()


def test_from_env_truthy_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    for v in ("1", "true", "TRUE", "YES", "on"):
        monkeypatch.setenv("THOUGHTS_ENABLED", v)
        assert ThoughtConfig.from_env().enabled is True
    for v in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("THOUGHTS_ENABLED", v)
        assert ThoughtConfig.from_env().enabled is False
