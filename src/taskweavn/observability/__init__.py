"""Observability: structured logging and legacy channel compatibility."""

from taskweavn.observability.levels import LogLevel
from taskweavn.observability.logger import ObjectLogger, get_object_logger
from taskweavn.observability.manager import (
    LoggingManager,
    build_disabled_logging_config,
    build_legacy_logging_config,
    get_logging_manager,
)
from taskweavn.observability.models import (
    EffectiveLogRule,
    LogCategory,
    LogContext,
    LogEvent,
    LoggingConfig,
    LoggingConfigPatch,
    LoggingProfile,
    LogOverride,
    LogRule,
    LogScope,
    LogSinkConfig,
    RotationConfig,
)
from taskweavn.observability.setup import (
    CHANNELS,
    LOGGER_PREFIX,
    configure_logging,
    get_channel_logger,
)

__all__ = [
    "CHANNELS",
    "EffectiveLogRule",
    "LOGGER_PREFIX",
    "LogCategory",
    "LogContext",
    "LogEvent",
    "LogLevel",
    "LogOverride",
    "LogRule",
    "LogScope",
    "LogSinkConfig",
    "LoggingConfig",
    "LoggingConfigPatch",
    "LoggingManager",
    "LoggingProfile",
    "ObjectLogger",
    "RotationConfig",
    "build_disabled_logging_config",
    "build_legacy_logging_config",
    "configure_logging",
    "get_channel_logger",
    "get_logging_manager",
    "get_object_logger",
]
