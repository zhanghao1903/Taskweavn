from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from taskweavn.observability import RuntimeConfigLoggingConsumer
from taskweavn.observability.models import LogCategory
from taskweavn.runtime_config import (
    DefaultRuntimeConfigMutationService,
    RuntimeConfigActor,
    RuntimeConfigBusConsumerResult,
    RuntimeConfigBusEvent,
    RuntimeConfigMutationServiceConfig,
    RuntimeConfigPatch,
    RuntimeConfigScope,
    SqliteRuntimeConfigChangeStore,
    runtime_config_bus_event_from_change,
)


def test_runtime_config_logging_consumer_applies_active_logging_level(
    tmp_path: Path,
) -> None:
    manager = _FakeLoggingManager()
    consumer = RuntimeConfigLoggingConsumer(
        manager=manager,
        categories=("tool", "config"),
    )
    event = _event(
        tmp_path,
        scope=RuntimeConfigScope(level="workspace", workspace_id="w1"),
        values={"logging.level": "DEBUG"},
    )

    result = consumer.handle_runtime_config_change(event)

    assert result == RuntimeConfigBusConsumerResult(
        consumer_id=consumer.consumer_id,
        status="applied",
        applied_keys=("logging.level",),
        message="Applied live logging config keys.",
    )
    assert manager.calls == (
        _SetLevelCall(session_id=None, category="tool", level="DEBUG"),
        _SetLevelCall(session_id=None, category="config", level="DEBUG"),
    )


def test_runtime_config_logging_consumer_uses_session_scope_when_available(
    tmp_path: Path,
) -> None:
    manager = _FakeLoggingManager()
    consumer = RuntimeConfigLoggingConsumer(
        manager=manager,
        categories=("tool",),
    )
    event = _event(
        tmp_path,
        scope=RuntimeConfigScope(
            level="session",
            workspace_id="w1",
            session_id="s1",
        ),
        values={"logging.level": "WARNING"},
    )

    result = consumer.handle_runtime_config_change(event)

    assert result.status == "applied"
    assert manager.calls == (
        _SetLevelCall(session_id="s1", category="tool", level="WARNING"),
    )


def test_runtime_config_logging_consumer_skips_pending_and_unsupported_keys(
    tmp_path: Path,
) -> None:
    manager = _FakeLoggingManager()
    consumer = RuntimeConfigLoggingConsumer(
        manager=manager,
        categories=("tool",),
    )
    event = _event(
        tmp_path,
        scope=RuntimeConfigScope(level="workspace", workspace_id="w1"),
        values={
            "logging.profile": "debug-llm",
            "agent_loop.default_max_steps": 8,
        },
    )

    result = consumer.handle_runtime_config_change(event)

    assert result == RuntimeConfigBusConsumerResult(
        consumer_id=consumer.consumer_id,
        status="skipped",
        skipped_keys=("logging.profile", "agent_loop.default_max_steps"),
        message="No supported active logging config keys to apply.",
    )
    assert manager.calls == ()


def test_runtime_config_logging_consumer_reports_mixed_apply_and_skip(
    tmp_path: Path,
) -> None:
    manager = _FakeLoggingManager()
    consumer = RuntimeConfigLoggingConsumer(
        manager=manager,
        categories=("tool",),
    )
    event = _event(
        tmp_path,
        scope=RuntimeConfigScope(level="workspace", workspace_id="w1"),
        values={
            "logging.level": "ERROR",
            "logging.profile": "debug-llm",
            "agent_loop.default_max_steps": 8,
        },
    )

    result = consumer.handle_runtime_config_change(event)

    assert result == RuntimeConfigBusConsumerResult(
        consumer_id=consumer.consumer_id,
        status="applied",
        applied_keys=("logging.level",),
        skipped_keys=("logging.profile", "agent_loop.default_max_steps"),
        message="Applied live logging config keys; skipped non-live or unsupported keys.",
    )
    assert manager.calls == (
        _SetLevelCall(session_id=None, category="tool", level="ERROR"),
    )


def _event(
    tmp_path: Path,
    *,
    scope: RuntimeConfigScope,
    values: dict[str, object],
) -> RuntimeConfigBusEvent:
    patch = RuntimeConfigPatch(
        patch_id=f"patch-{len(values)}",
        scope=scope,
        actor=_actor(),
        values=values,
        requested_at=_ts(),
    )
    with SqliteRuntimeConfigChangeStore(tmp_path / "runtime-config.db") as store:
        service = DefaultRuntimeConfigMutationService(
            RuntimeConfigMutationServiceConfig(store=store)
        )
        change = service.apply_patch(patch)
    return runtime_config_bus_event_from_change(change)


def _actor() -> RuntimeConfigActor:
    return RuntimeConfigActor(
        actor_type="test",
        actor_id="test-suite",
        display_name="Runtime config logging consumer tests",
    )


def _ts() -> datetime:
    return datetime(2026, 6, 24, 15, 0, tzinfo=UTC)


@dataclass(frozen=True)
class _SetLevelCall:
    session_id: str | None
    category: LogCategory
    level: str | int


@dataclass
class _FakeLoggingManager:
    calls: tuple[_SetLevelCall, ...] = field(default_factory=tuple)

    def set_level(
        self,
        *,
        session_id: str | None,
        category: LogCategory,
        level: str | int,
        duration_seconds: float | None = None,
    ) -> None:
        self.calls = (
            *self.calls,
            _SetLevelCall(
                session_id=session_id,
                category=category,
                level=level,
            ),
        )
