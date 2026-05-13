"""Observability: structured logging and legacy channel compatibility."""

from taskweavn.observability.context import (
    get_log_context,
    merge_log_context,
    use_log_context,
)
from taskweavn.observability.levels import LogLevel
from taskweavn.observability.logger import ObjectLogger, get_object_logger
from taskweavn.observability.manager import (
    LoggingManager,
    build_disabled_logging_config,
    build_legacy_logging_config,
    build_session_logging_config,
    get_logging_manager,
)
from taskweavn.observability.models import (
    EffectiveLogRule,
    LogArchiveManifest,
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
    configure_session_logging,
    get_channel_logger,
    load_logging_config,
)

__all__ = [
    "CHANNELS",
    "EffectiveLogRule",
    "LOGGER_PREFIX",
    "LogArchiveManifest",
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
    "build_session_logging_config",
    "configure_logging",
    "configure_session_logging",
    "get_channel_logger",
    "get_log_context",
    "get_logging_manager",
    "get_object_logger",
    "load_logging_config",
    "merge_log_context",
    "use_log_context",
]
