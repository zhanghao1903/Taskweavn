"""Scheduled Task publisher adapter."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, time, timedelta
from threading import RLock
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

from taskweavn.task.publisher import (
    PublisherRef,
    PublishRequest,
    PublishResult,
    PublishSource,
    TaskPublishOptions,
)
from taskweavn.task.publisher_input import normalize_task_tree_input
from taskweavn.task.publisher_service import TaskPublishService

ScheduleExpressionKind = Literal["interval", "daily", "cron"]
SessionSelectorMode = Literal["fixed", "current"]
IdempotencyPolicyMode = Literal["schedule_tick", "constant", "none"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class _FrozenSchedulerModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        validate_assignment=True,
    )


class ScheduleExpression(_FrozenSchedulerModel):
    """When a scheduled publisher should fire."""

    type: ScheduleExpressionKind
    every_seconds: int | None = Field(default=None, gt=0)
    time_of_day: str | None = Field(default=None, min_length=1)
    cron: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_shape(self) -> ScheduleExpression:
        if self.type == "interval" and self.every_seconds is None:
            raise ValueError("interval schedule requires every_seconds")
        if self.type == "daily" and self.time_of_day is None:
            raise ValueError("daily schedule requires time_of_day")
        if self.type == "cron" and self.cron is None:
            raise ValueError("cron schedule requires cron")
        return self


class SessionSelector(_FrozenSchedulerModel):
    """Selects which session a scheduled publish targets."""

    mode: SessionSelectorMode = "fixed"
    session_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_selector(self) -> SessionSelector:
        if self.mode == "fixed" and self.session_id is None:
            raise ValueError("fixed session selector requires session_id")
        return self


class IdempotencyPolicy(_FrozenSchedulerModel):
    """Builds stable idempotency keys for scheduler ticks."""

    mode: IdempotencyPolicyMode = "schedule_tick"
    key_template: str | None = Field(default=None, min_length=1)


class ScheduledPublishConfig(_FrozenSchedulerModel):
    """Configuration for one scheduled Task publish."""

    schedule_id: str = Field(alias="id", min_length=1)
    enabled: bool = True
    schedule: ScheduleExpression
    session_selector: SessionSelector
    task_tree: dict[str, Any]
    idempotency_policy: IdempotencyPolicy = Field(default_factory=IdempotencyPolicy)
    timezone: str = Field(default="Asia/Shanghai", min_length=1)
    options: TaskPublishOptions = Field(
        default_factory=lambda: TaskPublishOptions(require_confirmation=False)
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_timezone(self) -> ScheduledPublishConfig:
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone {self.timezone!r}") from exc
        return self


class ScheduledPublishState(_FrozenSchedulerModel):
    """Mutable scheduler state persisted outside the config."""

    schedule_id: str = Field(min_length=1)
    enabled: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_result: PublishResult | None = None
    updated_at: datetime = Field(default_factory=_utcnow)


class ScheduledPublishTickResult(_FrozenSchedulerModel):
    """Result of evaluating one schedule during a tick."""

    schedule_id: str = Field(min_length=1)
    due: bool
    published: bool = False
    result: PublishResult | None = None
    next_run_at: datetime | None = None
    reason: str | None = Field(default=None, min_length=1)


@runtime_checkable
class ScheduledPublishStore(Protocol):
    """Config + state persistence for scheduled publishers."""

    def upsert_config(self, config: ScheduledPublishConfig) -> ScheduledPublishConfig: ...

    def get_config(self, schedule_id: str) -> ScheduledPublishConfig | None: ...

    def list_configs(self) -> tuple[ScheduledPublishConfig, ...]: ...

    def set_enabled(self, schedule_id: str, enabled: bool) -> ScheduledPublishConfig: ...

    def get_state(self, schedule_id: str) -> ScheduledPublishState | None: ...

    def save_state(self, state: ScheduledPublishState) -> ScheduledPublishState: ...


class InMemoryScheduledPublishStore:
    """Thread-safe process-local scheduled publish store."""

    def __init__(
        self,
        configs: Iterable[ScheduledPublishConfig | Mapping[str, Any]] = (),
        states: Iterable[ScheduledPublishState | Mapping[str, Any]] = (),
    ) -> None:
        self._lock = RLock()
        self._configs: dict[str, ScheduledPublishConfig] = {}
        self._states: dict[str, ScheduledPublishState] = {}
        for config_like in configs:
            self.upsert_config(ScheduledPublishConfig.model_validate(config_like))
        for state_like in states:
            state = ScheduledPublishState.model_validate(state_like)
            self._states[state.schedule_id] = state

    def upsert_config(self, config: ScheduledPublishConfig) -> ScheduledPublishConfig:
        with self._lock:
            self._configs[config.schedule_id] = config
            self._states.setdefault(
                config.schedule_id,
                ScheduledPublishState(schedule_id=config.schedule_id),
            )
            return config

    def get_config(self, schedule_id: str) -> ScheduledPublishConfig | None:
        with self._lock:
            return self._configs.get(schedule_id)

    def list_configs(self) -> tuple[ScheduledPublishConfig, ...]:
        with self._lock:
            return tuple(
                self._configs[schedule_id] for schedule_id in sorted(self._configs)
            )

    def set_enabled(self, schedule_id: str, enabled: bool) -> ScheduledPublishConfig:
        with self._lock:
            config = self._configs.get(schedule_id)
            if config is None:
                raise LookupError(f"ScheduledPublishConfig {schedule_id!r} not found")
            updated = config.model_copy(update={"enabled": enabled})
            self._configs[schedule_id] = updated
            current = self._states.get(schedule_id) or ScheduledPublishState(
                schedule_id=schedule_id
            )
            self._states[schedule_id] = current.model_copy(
                update={"enabled": enabled, "updated_at": _utcnow()}
            )
            return updated

    def get_state(self, schedule_id: str) -> ScheduledPublishState | None:
        with self._lock:
            return self._states.get(schedule_id)

    def save_state(self, state: ScheduledPublishState) -> ScheduledPublishState:
        with self._lock:
            if state.schedule_id not in self._configs:
                raise LookupError(f"ScheduledPublishConfig {state.schedule_id!r} not found")
            updated = state.model_copy(update={"updated_at": _utcnow()})
            self._states[state.schedule_id] = updated
            return updated


class SchedulerPublisher:
    """Evaluates due schedules and publishes them through TaskPublishService."""

    def __init__(
        self,
        *,
        store: ScheduledPublishStore,
        publish_service: TaskPublishService,
    ) -> None:
        self._store = store
        self._publish_service = publish_service

    def tick(
        self,
        *,
        now: datetime | None = None,
        current_session_id: str | None = None,
    ) -> tuple[ScheduledPublishTickResult, ...]:
        tick_time = _aware(now or _utcnow())
        results: list[ScheduledPublishTickResult] = []
        for config in self._store.list_configs():
            results.append(
                self._tick_one(config, now=tick_time, current_session_id=current_session_id)
            )
        return tuple(results)

    def _tick_one(
        self,
        config: ScheduledPublishConfig,
        *,
        now: datetime,
        current_session_id: str | None,
    ) -> ScheduledPublishTickResult:
        state = self._store.get_state(config.schedule_id) or ScheduledPublishState(
            schedule_id=config.schedule_id
        )
        if not config.enabled or not state.enabled:
            return ScheduledPublishTickResult(
                schedule_id=config.schedule_id,
                due=False,
                next_run_at=state.next_run_at,
                reason="disabled",
            )
        try:
            session_id = _resolve_session(config.session_selector, current_session_id)
        except ValueError as exc:
            return ScheduledPublishTickResult(
                schedule_id=config.schedule_id,
                due=False,
                next_run_at=state.next_run_at,
                reason=str(exc),
            )

        next_run_at = state.next_run_at or _first_run_at(config, now)
        if next_run_at is None:
            return ScheduledPublishTickResult(
                schedule_id=config.schedule_id,
                due=False,
                next_run_at=None,
                reason="unsupported schedule type",
            )
        if next_run_at > now:
            return ScheduledPublishTickResult(
                schedule_id=config.schedule_id,
                due=False,
                next_run_at=next_run_at,
                reason="not due",
            )

        run_at = next_run_at
        request = _build_request(config, session_id=session_id, run_at=run_at)
        result = self._publish_service.publish(request)
        next_after = _next_after(config, run_at)
        self._store.save_state(
            ScheduledPublishState(
                schedule_id=config.schedule_id,
                enabled=state.enabled,
                last_run_at=run_at,
                next_run_at=next_after,
                last_result=result,
            )
        )
        return ScheduledPublishTickResult(
            schedule_id=config.schedule_id,
            due=True,
            published=result.accepted,
            result=result,
            next_run_at=next_after,
            reason=result.reason,
        )


def _resolve_session(selector: SessionSelector, current_session_id: str | None) -> str:
    if selector.mode == "fixed":
        if selector.session_id is None:
            raise ValueError("fixed session selector requires session_id")
        return selector.session_id
    if current_session_id is None:
        raise ValueError("current session selector requires current_session_id")
    return current_session_id


def _build_request(
    config: ScheduledPublishConfig,
    *,
    session_id: str,
    run_at: datetime,
) -> PublishRequest:
    publisher = PublisherRef(kind="scheduler", name=config.schedule_id)
    tree = normalize_task_tree_input(
        config.task_tree,
        publisher=publisher,
        source_ref=config.schedule_id,
        metadata={
            "schedule_id": config.schedule_id,
            "schedule_timezone": config.timezone,
            "schedule_run_at": run_at.isoformat(),
            **config.metadata,
        },
    )
    return PublishRequest(
        session_id=session_id,
        publisher=publisher,
        source=PublishSource(
            source_type="schedule",
            source_id=config.schedule_id,
            metadata={
                "schedule_id": config.schedule_id,
                "run_at": run_at.isoformat(),
            },
        ),
        task_tree=tree,
        options=config.options,
        idempotency_key=_idempotency_key(config, session_id=session_id, run_at=run_at),
    )


def _idempotency_key(
    config: ScheduledPublishConfig,
    *,
    session_id: str,
    run_at: datetime,
) -> str | None:
    policy = config.idempotency_policy
    if policy.mode == "none":
        return None
    values = {
        "schedule_id": config.schedule_id,
        "session_id": session_id,
        "run_at": run_at.isoformat(),
        "date": run_at.date().isoformat(),
    }
    if policy.key_template is not None:
        return policy.key_template.format(**values)
    if policy.mode == "constant":
        return "schedule:{schedule_id}:{session_id}".format(**values)
    return "schedule:{schedule_id}:{session_id}:{run_at}".format(**values)


def _first_run_at(config: ScheduledPublishConfig, now: datetime) -> datetime | None:
    schedule = config.schedule
    if schedule.type == "cron":
        return None
    if schedule.type == "interval":
        return now
    tz = ZoneInfo(config.timezone)
    daily_time = _parse_time(schedule.time_of_day)
    now_local = now.astimezone(tz)
    return datetime.combine(now_local.date(), daily_time, tzinfo=tz)


def _next_after(config: ScheduledPublishConfig, run_at: datetime) -> datetime | None:
    schedule = config.schedule
    if schedule.type == "cron":
        return None
    if schedule.type == "interval":
        if schedule.every_seconds is None:
            raise ValueError("interval schedule requires every_seconds")
        return run_at + timedelta(seconds=schedule.every_seconds)
    tz = ZoneInfo(config.timezone)
    daily_time = _parse_time(schedule.time_of_day)
    run_local = run_at.astimezone(tz)
    candidate = datetime.combine(run_local.date(), daily_time, tzinfo=tz)
    if candidate <= run_local:
        candidate += timedelta(days=1)
    return candidate


def _parse_time(value: str | None) -> time:
    if value is None:
        raise ValueError("daily schedule requires time_of_day")
    parts = value.split(":")
    if len(parts) not in {2, 3}:
        raise ValueError("time_of_day must be HH:MM or HH:MM:SS")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
        return time(hour=hour, minute=minute, second=second)
    except ValueError as exc:
        raise ValueError("time_of_day must be a valid HH:MM or HH:MM:SS value") from exc


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


__all__ = [
    "IdempotencyPolicy",
    "IdempotencyPolicyMode",
    "InMemoryScheduledPublishStore",
    "ScheduleExpression",
    "ScheduleExpressionKind",
    "ScheduledPublishConfig",
    "ScheduledPublishState",
    "ScheduledPublishStore",
    "ScheduledPublishTickResult",
    "SchedulerPublisher",
    "SessionSelector",
    "SessionSelectorMode",
]
