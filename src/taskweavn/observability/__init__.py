"""Observability: structured logging and legacy channel compatibility."""

from taskweavn.observability.context import (
    get_log_context,
    merge_log_context,
    use_log_context,
)
from taskweavn.observability.control import (
    LoggingControlOperation,
    LoggingControlResult,
    LoggingControlService,
    LoggingProfileInfo,
)
from taskweavn.observability.events import (
    LOG_EVENTS_BY_CATEGORY,
    is_known_log_event,
    known_log_events,
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
from taskweavn.observability.runtime_config_consumer import (
    LoggingLevelApplier,
    RuntimeConfigLoggingConsumer,
    subscribe_runtime_config_logging_consumer,
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
    "LOG_EVENTS_BY_CATEGORY",
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
    "LoggingControlOperation",
    "LoggingControlResult",
    "LoggingControlService",
    "LoggingLevelApplier",
    "LoggingManager",
    "LoggingProfile",
    "LoggingProfileInfo",
    "ObjectLogger",
    "RuntimeConfigLoggingConsumer",
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
    "is_known_log_event",
    "known_log_events",
    "load_logging_config",
    "merge_log_context",
    "subscribe_runtime_config_logging_consumer",
    "use_log_context",
]
