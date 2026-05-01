"""Tests for LocalRuntime and the Runtime Protocol (1.3)."""

from __future__ import annotations

from code_agent.runtime import LocalRuntime, Runtime
from code_agent.types import BaseAction, BaseObservation, ErrorObservation


class _AddAction(BaseAction):
    a: int
    b: int


class _UnregisteredAction(BaseAction):
    payload: str


class _SumObservation(BaseObservation):
    total: int


def _add_executor(action: BaseAction) -> BaseObservation:
    assert isinstance(action, _AddAction)
    return _SumObservation(total=action.a + action.b, action_id=action.event_id)


def _broken_executor(action: BaseAction) -> BaseObservation:  # noqa: ARG001
    raise RuntimeError("boom")


def test_local_runtime_implements_protocol() -> None:
    assert isinstance(LocalRuntime(), Runtime)


def test_executor_dispatch() -> None:
    rt = LocalRuntime()
    rt.register(_AddAction, _add_executor)

    obs = rt.execute(_AddAction(a=2, b=3))
    assert isinstance(obs, _SumObservation)
    assert obs.total == 5
    assert obs.success is True


def test_observation_links_back_to_action() -> None:
    rt = LocalRuntime()
    rt.register(_AddAction, _add_executor)

    action = _AddAction(a=1, b=1)
    obs = rt.execute(action)
    assert obs.action_id == action.event_id


def test_missing_executor_returns_error_observation() -> None:
    rt = LocalRuntime()
    action = _UnregisteredAction(payload="x")
    obs = rt.execute(action)
    assert isinstance(obs, ErrorObservation)
    assert obs.success is False
    assert obs.error_type == "no_executor"
    assert "_UnregisteredAction" in obs.message
    assert obs.action_id == action.event_id


def test_executor_exception_caught_as_error_observation() -> None:
    rt = LocalRuntime()
    rt.register(_AddAction, _broken_executor)
    obs = rt.execute(_AddAction(a=0, b=0))
    assert isinstance(obs, ErrorObservation)
    assert obs.error_type == "execution_error"
    assert "boom" in obs.message
    assert obs.success is False


def test_register_replaces_existing_executor() -> None:
    rt = LocalRuntime()
    rt.register(_AddAction, _broken_executor)
    rt.register(_AddAction, _add_executor)  # second wins
    obs = rt.execute(_AddAction(a=4, b=5))
    assert isinstance(obs, _SumObservation)
    assert obs.total == 9
