"""Read-only Settings and first-run readiness for the local Plato sidecar."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from taskweavn.llm.config import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS,
)
from taskweavn.observability import build_session_logging_config
from taskweavn.product_errors import ProductRecoveryAction
from taskweavn.server.ui_contract.base import UiContractModel

SETTINGS_READINESS_SCHEMA_VERSION: Literal["plato.settings_readiness.v1"] = (
    "plato.settings_readiness.v1"
)
DEFAULT_FIRST_RUN_LLM_PROVIDER = DEFAULT_LLM_PROVIDER
DEFAULT_FIRST_RUN_LLM_MODEL = "deepseek-v4-pro"

SettingsReadinessStatus = Literal["ready", "needs_configuration", "degraded"]
SettingsReadinessIssueSeverity = Literal["blocking", "warning"]

_SUPPORTED_PROVIDERS = ("litellm", "deepseek", "openrouter")
_OPENROUTER_BOOL_ENV_VARS = (
    "OPENROUTER_ALLOW_FALLBACKS",
    "OPENROUTER_REQUIRE_PARAMETERS",
    "OPENROUTER_ZDR",
)


class SettingsReadinessIssue(UiContractModel):
    code: str
    severity: SettingsReadinessIssueSeverity
    message: str
    recovery_actions: tuple[ProductRecoveryAction, ...]
    env_vars: tuple[str, ...] = ()


class SettingsReadinessFirstRun(UiContractModel):
    ready: bool
    blocking_issue_codes: tuple[str, ...]
    recommended_actions: tuple[ProductRecoveryAction, ...]


class SettingsReadinessThinking(UiContractModel):
    configured: bool
    enabled: bool | None = None
    effort: str | None = None


class SettingsReadinessOpenRouterRouting(UiContractModel):
    configured: bool
    invalid_env_vars: tuple[str, ...] = ()
    provider_order_count: int = 0
    provider_only_count: int = 0
    provider_ignore_count: int = 0
    allow_fallbacks: bool | None = None
    require_parameters: bool | None = None
    data_collection_configured: bool = False
    zdr: bool | None = None


class SettingsReadinessLlm(UiContractModel):
    provider: str
    provider_source: Literal["default", "env"]
    model: str
    model_source: Literal["default", "env"]
    configured: bool
    api_key_configured: bool
    missing_env_vars: tuple[str, ...]
    request_timeout_seconds: float | None
    request_timeout_configured: bool
    request_timeout_valid: bool
    thinking: SettingsReadinessThinking
    routing: SettingsReadinessOpenRouterRouting | None = None


class SettingsReadinessLoggingProfile(UiContractModel):
    id: str
    description: str


class SettingsReadinessLogging(UiContractModel):
    enabled: bool
    level: str
    selected_profile: str | None = None
    selected_profile_known: bool
    default_profile: str | None = None
    profiles: tuple[SettingsReadinessLoggingProfile, ...]


class SettingsReadinessDiagnostics(UiContractModel):
    bundle_export_available: bool
    http_export_route_available: bool
    cli_command_template: str


class SettingsReadinessReport(UiContractModel):
    schema_version: Literal["plato.settings_readiness.v1"] = (
        SETTINGS_READINESS_SCHEMA_VERSION
    )
    generated_at: datetime
    workspace_root_label: str = "workspace://current"
    status: SettingsReadinessStatus
    first_run: SettingsReadinessFirstRun
    llm: SettingsReadinessLlm
    logging: SettingsReadinessLogging
    diagnostics: SettingsReadinessDiagnostics
    blocking_issues: tuple[SettingsReadinessIssue, ...] = ()
    warnings: tuple[SettingsReadinessIssue, ...] = ()


@dataclass(frozen=True)
class DefaultSettingsReadinessGateway:
    """Build the read-only first-run readiness payload for the sidecar."""

    workspace_root: Path
    logging_enabled: bool = True
    logging_level: str = "INFO"
    selected_logging_profile: str | None = None
    default_model: str = DEFAULT_FIRST_RUN_LLM_MODEL
    env: Mapping[str, str] | None = None

    def get_readiness(self) -> dict[str, Any]:
        """Return a frontend-ready camelCase readiness report."""

        environment = os.environ if self.env is None else self.env
        report = build_settings_readiness_report(
            workspace_root=self.workspace_root,
            env=environment,
            logging_enabled=self.logging_enabled,
            logging_level=self.logging_level,
            selected_logging_profile=self.selected_logging_profile,
            default_model=self.default_model,
        )
        return report.to_contract_dict()


def build_settings_readiness_report(
    *,
    workspace_root: Path,
    env: Mapping[str, str],
    logging_enabled: bool = True,
    logging_level: str = "INFO",
    selected_logging_profile: str | None = None,
    default_model: str = DEFAULT_FIRST_RUN_LLM_MODEL,
    now: datetime | None = None,
) -> SettingsReadinessReport:
    """Build a deterministic local readiness report without provider calls."""

    issues: list[SettingsReadinessIssue] = []
    warnings: list[SettingsReadinessIssue] = []
    llm = _llm_readiness(env, default_model=default_model, issues=issues)
    logging = _logging_readiness(
        workspace_root=workspace_root,
        enabled=logging_enabled,
        level=logging_level,
        selected_profile=selected_logging_profile,
        issues=issues,
        warnings=warnings,
    )
    diagnostics = SettingsReadinessDiagnostics(
        bundle_export_available=True,
        http_export_route_available=True,
        cli_command_template=(
            "uv run taskweavn diagnostics export --workspace <workspace> "
            "--session-id <sessionId> --output <dir>"
        ),
    )
    blocking_issues = tuple(issue for issue in issues if issue.severity == "blocking")
    warning_issues = tuple(warnings) + tuple(
        issue for issue in issues if issue.severity == "warning"
    )
    status = _readiness_status(blocking_issues, warning_issues)
    first_run = SettingsReadinessFirstRun(
        ready=not blocking_issues,
        blocking_issue_codes=tuple(issue.code for issue in blocking_issues),
        recommended_actions=_recommended_actions(blocking_issues),
    )
    return SettingsReadinessReport(
        generated_at=now or datetime.now(UTC),
        status=status,
        first_run=first_run,
        llm=llm,
        logging=logging,
        diagnostics=diagnostics,
        blocking_issues=blocking_issues,
        warnings=warning_issues,
    )


def _llm_readiness(
    env: Mapping[str, str],
    *,
    default_model: str,
    issues: list[SettingsReadinessIssue],
) -> SettingsReadinessLlm:
    provider_source: Literal["default", "env"] = (
        "env" if "LLM_PROVIDER" in env else "default"
    )
    provider = env.get("LLM_PROVIDER", DEFAULT_FIRST_RUN_LLM_PROVIDER).strip().lower()
    provider_for_payload = provider or "unknown"
    model_source: Literal["default", "env"] = "env" if "LLM_MODEL" in env else "default"
    model = env.get("LLM_MODEL", default_model)
    missing_env_vars: tuple[str, ...] = ()
    api_key_configured = False

    if provider not in _SUPPORTED_PROVIDERS:
        issues.append(
            SettingsReadinessIssue(
                code="llm.invalid_provider",
                severity="blocking",
                message="LLM_PROVIDER must be one of: litellm, deepseek, openrouter.",
                recovery_actions=("open_settings",),
                env_vars=("LLM_PROVIDER",),
            )
        )
    else:
        required_api_vars = _required_api_key_env_vars(provider)
        api_key_configured = any(_has_env_value(env, key) for key in required_api_vars)
        if not api_key_configured:
            missing_env_vars = required_api_vars
            issues.append(
                SettingsReadinessIssue(
                    code="llm.missing_api_key",
                    severity="blocking",
                    message="LLM API key configuration is missing.",
                    recovery_actions=("open_settings",),
                    env_vars=required_api_vars,
                )
            )

    if not model.strip():
        issues.append(
            SettingsReadinessIssue(
                code="llm.invalid_model",
                severity="blocking",
                message="LLM_MODEL must not be empty.",
                recovery_actions=("open_settings",),
                env_vars=("LLM_MODEL",),
            )
        )

    request_timeout_seconds, request_timeout_valid = _request_timeout(env, issues)
    thinking = _thinking_readiness(env, issues)
    routing = _openrouter_routing_readiness(env, issues) if provider == "openrouter" else None

    return SettingsReadinessLlm(
        provider=provider_for_payload,
        provider_source=provider_source,
        model=model if model.strip() else default_model,
        model_source=model_source,
        configured=not any(issue.code.startswith("llm.") for issue in issues),
        api_key_configured=api_key_configured,
        missing_env_vars=missing_env_vars,
        request_timeout_seconds=request_timeout_seconds,
        request_timeout_configured="LLM_REQUEST_TIMEOUT_SECONDS" in env,
        request_timeout_valid=request_timeout_valid,
        thinking=thinking,
        routing=routing,
    )


def _logging_readiness(
    *,
    workspace_root: Path,
    enabled: bool,
    level: str,
    selected_profile: str | None,
    issues: list[SettingsReadinessIssue],
    warnings: list[SettingsReadinessIssue],
) -> SettingsReadinessLogging:
    try:
        config = build_session_logging_config(workspace_root, level=level)
    except Exception:
        issues.append(
            SettingsReadinessIssue(
                code="logging.invalid_level",
                severity="blocking",
                message="Logging level is invalid.",
                recovery_actions=("open_settings",),
                env_vars=(),
            )
        )
        return SettingsReadinessLogging(
            enabled=enabled,
            level=str(level),
            selected_profile=selected_profile,
            selected_profile_known=False,
            default_profile=None,
            profiles=(),
        )

    profiles = tuple(
        SettingsReadinessLoggingProfile(id=name, description=profile.description)
        for name, profile in sorted(config.profiles.items())
    )
    selected_profile_known = (
        selected_profile is None or selected_profile in config.profiles
    )
    if not selected_profile_known:
        issues.append(
            SettingsReadinessIssue(
                code="logging.unknown_profile",
                severity="blocking",
                message="Selected logging profile is not available.",
                recovery_actions=("open_settings",),
                env_vars=(),
            )
        )
    if not enabled:
        warnings.append(
            SettingsReadinessIssue(
                code="logging.disabled",
                severity="warning",
                message="Session logging is disabled; diagnostics may be incomplete.",
                recovery_actions=("open_settings",),
                env_vars=(),
            )
        )

    return SettingsReadinessLogging(
        enabled=enabled,
        level=config.default_level,
        selected_profile=selected_profile,
        selected_profile_known=selected_profile_known,
        default_profile="normal" if "normal" in config.profiles else None,
        profiles=profiles,
    )


def _request_timeout(
    env: Mapping[str, str],
    issues: list[SettingsReadinessIssue],
) -> tuple[float | None, bool]:
    raw = env.get("LLM_REQUEST_TIMEOUT_SECONDS")
    if raw is None:
        return DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS, True
    normalized = raw.strip().lower()
    if normalized in {"none", "off", "disabled"}:
        return None, True
    try:
        timeout = float(normalized)
    except ValueError:
        _append_invalid_timeout_issue(issues)
        return None, False
    if timeout <= 0:
        _append_invalid_timeout_issue(issues)
        return None, False
    return timeout, True


def _thinking_readiness(
    env: Mapping[str, str],
    issues: list[SettingsReadinessIssue],
) -> SettingsReadinessThinking:
    raw = env.get("LLM_THINKING_ENABLED")
    if raw is None:
        return SettingsReadinessThinking(configured=False)
    parsed = _parse_bool(raw)
    if parsed is None:
        issues.append(
            SettingsReadinessIssue(
                code="llm.invalid_thinking_enabled",
                severity="blocking",
                message="LLM_THINKING_ENABLED must be a boolean value.",
                recovery_actions=("open_settings",),
                env_vars=("LLM_THINKING_ENABLED",),
            )
        )
    return SettingsReadinessThinking(
        configured=True,
        enabled=parsed,
        effort=env.get("LLM_THINKING_EFFORT", "high"),
    )


def _openrouter_routing_readiness(
    env: Mapping[str, str],
    issues: list[SettingsReadinessIssue],
) -> SettingsReadinessOpenRouterRouting:
    invalid_env_vars: list[str] = []
    bool_values: dict[str, bool | None] = {}
    for key in _OPENROUTER_BOOL_ENV_VARS:
        if key not in env:
            bool_values[key] = None
            continue
        parsed = _parse_bool(env[key])
        bool_values[key] = parsed
        if parsed is None:
            invalid_env_vars.append(key)
    if invalid_env_vars:
        issues.append(
            SettingsReadinessIssue(
                code="llm.invalid_openrouter_routing",
                severity="blocking",
                message="OpenRouter routing boolean settings are invalid.",
                recovery_actions=("open_settings",),
                env_vars=tuple(invalid_env_vars),
            )
        )
    configured = any(
        key in env
        for key in (
            "OPENROUTER_PROVIDER_ORDER",
            "OPENROUTER_PROVIDER_ONLY",
            "OPENROUTER_PROVIDER_IGNORE",
            "OPENROUTER_DATA_COLLECTION",
            *_OPENROUTER_BOOL_ENV_VARS,
        )
    )
    return SettingsReadinessOpenRouterRouting(
        configured=configured,
        invalid_env_vars=tuple(invalid_env_vars),
        provider_order_count=len(_split_csv(env.get("OPENROUTER_PROVIDER_ORDER"))),
        provider_only_count=len(_split_csv(env.get("OPENROUTER_PROVIDER_ONLY"))),
        provider_ignore_count=len(_split_csv(env.get("OPENROUTER_PROVIDER_IGNORE"))),
        allow_fallbacks=bool_values["OPENROUTER_ALLOW_FALLBACKS"],
        require_parameters=bool_values["OPENROUTER_REQUIRE_PARAMETERS"],
        data_collection_configured="OPENROUTER_DATA_COLLECTION" in env,
        zdr=bool_values["OPENROUTER_ZDR"],
    )


def _required_api_key_env_vars(provider: str) -> tuple[str, ...]:
    if provider == "deepseek":
        return ("DEEPSEEK_API_KEY", "LLM_API_KEY")
    if provider == "openrouter":
        return ("OPENROUTER_API_KEY", "LLM_API_KEY")
    return ("LLM_API_KEY",)


def _has_env_value(env: Mapping[str, str], key: str) -> bool:
    return bool(env.get(key, "").strip())


def _append_invalid_timeout_issue(issues: list[SettingsReadinessIssue]) -> None:
    issues.append(
        SettingsReadinessIssue(
            code="llm.invalid_timeout",
            severity="blocking",
            message="LLM_REQUEST_TIMEOUT_SECONDS must be positive or 'none'.",
            recovery_actions=("open_settings",),
            env_vars=("LLM_REQUEST_TIMEOUT_SECONDS",),
        )
    )


def _parse_bool(raw: str) -> bool | None:
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _split_csv(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _readiness_status(
    blocking_issues: tuple[SettingsReadinessIssue, ...],
    warnings: tuple[SettingsReadinessIssue, ...],
) -> SettingsReadinessStatus:
    if blocking_issues:
        return "needs_configuration"
    if warnings:
        return "degraded"
    return "ready"


def _recommended_actions(
    blocking_issues: tuple[SettingsReadinessIssue, ...],
) -> tuple[ProductRecoveryAction, ...]:
    if not blocking_issues:
        return ("none",)
    actions: list[ProductRecoveryAction] = []
    for issue in blocking_issues:
        for action in issue.recovery_actions:
            if action not in actions:
                actions.append(action)
    return tuple(actions)


__all__ = [
    "DEFAULT_FIRST_RUN_LLM_PROVIDER",
    "DEFAULT_FIRST_RUN_LLM_MODEL",
    "DefaultSettingsReadinessGateway",
    "SETTINGS_READINESS_SCHEMA_VERSION",
    "SettingsReadinessDiagnostics",
    "SettingsReadinessFirstRun",
    "SettingsReadinessIssue",
    "SettingsReadinessLlm",
    "SettingsReadinessLogging",
    "SettingsReadinessLoggingProfile",
    "SettingsReadinessOpenRouterRouting",
    "SettingsReadinessReport",
    "SettingsReadinessStatus",
    "SettingsReadinessThinking",
    "build_settings_readiness_report",
]
