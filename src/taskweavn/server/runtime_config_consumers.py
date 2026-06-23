"""Runtime configuration adapters for behavior-consuming constructors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from taskweavn.context import ContextBudget
from taskweavn.runtime_config import EffectiveRuntimeConfig


class RuntimeConfigConsumerError(ValueError):
    """Raised when an effective config cannot be adapted for a runtime consumer."""


@dataclass(frozen=True)
class RuntimeExecutionSettings:
    """Execution settings consumed by Main Page runtime assembly."""

    default_agent_max_steps: int
    execution_dispatcher_enabled: bool
    execution_dispatcher_max_ticks_per_trigger: int
    config_hash: str


@dataclass(frozen=True)
class RuntimeContextSettings:
    """Context Manager settings consumed by AgentLoop context assembly."""

    checkpoint_interval_steps: int
    max_prior_messages: int
    budget: ContextBudget
    config_hash: str


def runtime_execution_settings_from_config(
    config: EffectiveRuntimeConfig,
) -> RuntimeExecutionSettings:
    """Extract execution constructor values from an effective config snapshot."""

    return RuntimeExecutionSettings(
        default_agent_max_steps=_int_value(config, "agent_loop.default_max_steps"),
        execution_dispatcher_enabled=_bool_value(
            config,
            "execution_dispatcher.enabled",
        ),
        execution_dispatcher_max_ticks_per_trigger=_int_value(
            config,
            "execution_dispatcher.max_ticks_per_trigger",
        ),
        config_hash=config.config_hash,
    )


def runtime_context_settings_from_config(
    config: EffectiveRuntimeConfig,
) -> RuntimeContextSettings:
    """Extract Context Manager constructor values from an effective config snapshot."""

    return RuntimeContextSettings(
        checkpoint_interval_steps=_int_value(
            config,
            "context_manager.checkpoint_interval_steps",
        ),
        max_prior_messages=_int_value(config, "context_manager.max_prior_messages"),
        budget=ContextBudget(
            max_events=_int_value(config, "context_manager.budget.max_events"),
            max_tool_results=_int_value(
                config,
                "context_manager.budget.max_tool_results",
            ),
            max_file_snippets=_int_value(
                config,
                "context_manager.budget.max_file_snippets",
            ),
            max_file_snippet_chars=_int_value(
                config,
                "context_manager.budget.max_file_snippet_chars",
            ),
            max_rendered_chars=_int_value(
                config,
                "context_manager.budget.max_rendered_chars",
            ),
        ),
        config_hash=config.config_hash,
    )


def _value(config: EffectiveRuntimeConfig, key: str) -> Any:
    try:
        return config.values[key].value
    except KeyError as exc:
        raise RuntimeConfigConsumerError(
            f"effective runtime config is missing key: {key}",
        ) from exc


def _int_value(config: EffectiveRuntimeConfig, key: str) -> int:
    value = _value(config, key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeConfigConsumerError(f"{key} must be an int")
    return cast(int, value)


def _bool_value(config: EffectiveRuntimeConfig, key: str) -> bool:
    value = _value(config, key)
    if not isinstance(value, bool):
        raise RuntimeConfigConsumerError(f"{key} must be a bool")
    return value


__all__ = [
    "RuntimeConfigConsumerError",
    "RuntimeContextSettings",
    "RuntimeExecutionSettings",
    "runtime_context_settings_from_config",
    "runtime_execution_settings_from_config",
]
