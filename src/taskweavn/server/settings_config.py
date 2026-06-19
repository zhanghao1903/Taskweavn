"""Local Settings config read/write gateway for Product 1.0 first-run setup."""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError

from taskweavn.core import WorkspaceLayout
from taskweavn.observability import build_session_logging_config
from taskweavn.product_errors import product_error_details
from taskweavn.server.settings_readiness import (
    DEFAULT_FIRST_RUN_LLM_MODEL,
    DEFAULT_FIRST_RUN_LLM_PROVIDER,
    SettingsReadinessReport,
    build_settings_readiness_report,
)
from taskweavn.server.ui_contract import ApiError
from taskweavn.server.ui_contract.base import UiContractModel

SETTINGS_CONFIG_SCHEMA_VERSION = "plato.settings_config.v1"
SETTINGS_CONFIG_UPDATE_SCHEMA_VERSION = "plato.settings_config_update.v1"

SettingsProvider = Literal["litellm", "deepseek", "openrouter"]
SettingsConfigSource = Literal["default", "env", "stored"]
SettingsApiKeySource = Literal["none", "env", "stored"]
SettingsWebSearchProvider = Literal["tavily"]
SettingsWebSearchStatus = Literal["disabled", "missing_key", "ready"]
SettingsWebFetchStatus = Literal["disabled", "missing_key", "ready"]

SUPPORTED_SETTINGS_PROVIDERS: tuple[SettingsProvider, ...] = (
    "litellm",
    "deepseek",
    "openrouter",
)
_PROVIDER_LABELS: dict[str, str] = {
    "litellm": "LiteLLM",
    "deepseek": "DeepSeek",
    "openrouter": "OpenRouter",
}
SUPPORTED_WEB_SEARCH_PROVIDERS: tuple[SettingsWebSearchProvider, ...] = ("tavily",)
_WEB_SEARCH_PROVIDER_LABELS: dict[str, str] = {
    "tavily": "Tavily",
}
_STORAGE_SCHEMA_VERSION = "plato.local_settings_storage.v1"


class SettingsConfigProviderOption(UiContractModel):
    id: SettingsProvider
    label: str
    required_api_key_env_vars: tuple[str, ...]
    preferred_api_key_env_var: str


class SettingsConfigWebSearchProviderOption(UiContractModel):
    id: SettingsWebSearchProvider
    label: str
    required_api_key_env_vars: tuple[str, ...]
    preferred_api_key_env_var: str


class SettingsConfigLlm(UiContractModel):
    provider: str
    provider_source: SettingsConfigSource
    provider_options: tuple[SettingsConfigProviderOption, ...]
    model: str
    model_source: SettingsConfigSource
    api_key_configured: bool
    api_key_source: SettingsApiKeySource
    api_key_env_var: str


class SettingsConfigLogging(UiContractModel):
    enabled: bool
    level: str
    selected_profile: str | None = None
    selected_profile_source: SettingsConfigSource
    selected_profile_known: bool
    default_profile: str | None = None
    profiles: tuple[dict[str, str], ...]


class SettingsConfigDiagnostics(UiContractModel):
    bundle_export_available: bool
    http_export_route_available: bool


class SettingsConfigWebSearch(UiContractModel):
    enabled: bool
    provider: str
    provider_source: SettingsConfigSource
    provider_options: tuple[SettingsConfigWebSearchProviderOption, ...]
    mode: str
    max_results: int
    fetch_enabled: bool
    fetch_max_urls: int
    fetch_max_chars_per_url: int
    fetch_max_total_chars: int
    fetch_status: SettingsWebFetchStatus
    api_key_configured: bool
    api_key_source: SettingsApiKeySource
    api_key_env_var: str
    status: SettingsWebSearchStatus


class SettingsConfigSummary(UiContractModel):
    schema_version: Literal["plato.settings_config.v1"] = "plato.settings_config.v1"
    generated_at: datetime
    workspace_root_label: str = "workspace://current"
    llm: SettingsConfigLlm
    web_search: SettingsConfigWebSearch
    logging: SettingsConfigLogging
    diagnostics: SettingsConfigDiagnostics


class SettingsConfigUpdateResult(UiContractModel):
    schema_version: Literal["plato.settings_config_update.v1"] = (
        "plato.settings_config_update.v1"
    )
    updated_at: datetime
    config: SettingsConfigSummary
    readiness: dict[str, Any]


class UpdateSettingsConfigLlmPayload(UiContractModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    api_key: str | None = None


class UpdateSettingsConfigLoggingPayload(UiContractModel):
    selected_profile: str | None = None


class UpdateSettingsConfigWebSearchPayload(UiContractModel):
    enabled: bool
    provider: str = Field(default="tavily", min_length=1)
    mode: Literal["basic"] = "basic"
    max_results: int = Field(default=5, ge=1, le=10)
    fetch_enabled: bool = False
    fetch_max_urls: int = Field(default=3, ge=1, le=5)
    fetch_max_chars_per_url: int = Field(default=12000, ge=1000, le=20000)
    fetch_max_total_chars: int = Field(default=24000, ge=1000, le=40000)
    api_key: str | None = None


class UpdateSettingsConfigPayload(UiContractModel):
    llm: UpdateSettingsConfigLlmPayload | None = None
    logging: UpdateSettingsConfigLoggingPayload | None = None
    web_search: UpdateSettingsConfigWebSearchPayload | None = None


@dataclass(frozen=True)
class EffectiveWebSearchSettings:
    enabled: bool
    provider: str
    provider_source: SettingsConfigSource
    mode: str
    max_results: int
    fetch_enabled: bool
    fetch_max_urls: int
    fetch_max_chars_per_url: int
    fetch_max_total_chars: int
    fetch_status: SettingsWebFetchStatus
    api_key: str | None
    api_key_source: SettingsApiKeySource
    api_key_env_var: str
    status: SettingsWebSearchStatus


@dataclass(frozen=True)
class SettingsConfigFieldError:
    path: str
    message: str
    allowed_values: tuple[str, ...] = ()
    env_vars: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "path": self.path,
            "message": self.message,
        }
        if self.allowed_values:
            result["allowedValues"] = list(self.allowed_values)
        if self.env_vars:
            result["envVars"] = list(self.env_vars)
        return result


class SettingsConfigValidationError(ValueError):
    """Raised for safe user-correctable settings payload failures."""

    def __init__(self, field_errors: tuple[SettingsConfigFieldError, ...]) -> None:
        super().__init__("settings config update is invalid")
        self.field_errors = field_errors

    def to_api_error(self) -> ApiError:
        has_llm_key_error = any(error.path == "llm.apiKey" for error in self.field_errors)
        details = (
            product_error_details(
                "llm_auth_or_config",
                ("open_settings", "export_diagnostics"),
                severity="action_required",
                user_message_key="settings.config.invalid",
                extra={
                    "fieldErrors": [
                        field_error.to_dict() for field_error in self.field_errors
                    ]
                },
            )
            if has_llm_key_error
            else product_error_details(
                "input_validation",
                ("edit_input", "open_settings"),
                severity="action_required",
                user_message_key="settings.config.invalid",
                extra={
                    "fieldErrors": [
                        field_error.to_dict() for field_error in self.field_errors
                    ]
                },
            )
        )
        return ApiError(
            code="bad_request",
            message="settings config update is invalid",
            details=details,
        )


class SettingsConfigStorageError(RuntimeError):
    """Raised when local settings files cannot be read or written safely."""


@dataclass(frozen=True)
class FileSettingsConfigStore:
    """Small Product 1.0 local settings store.

    Secret values are intentionally isolated from the safe config summary file.
    """

    workspace_root: Path
    settings_dir_override: Path | None = None

    @property
    def settings_dir(self) -> Path:
        if self.settings_dir_override is not None:
            return self.settings_dir_override
        return WorkspaceLayout(self.workspace_root).meta_dir / "settings"

    @property
    def config_path(self) -> Path:
        return self.settings_dir / "config.json"

    @property
    def secrets_path(self) -> Path:
        return self.settings_dir / "secrets.json"

    def read_config(self) -> dict[str, Any]:
        return _read_json_object(self.config_path)

    def read_secret(self) -> tuple[str, str] | None:
        data = _read_json_object(self.secrets_path)
        llm = data.get("llm")
        if not isinstance(llm, Mapping):
            return None
        provider = llm.get("provider")
        api_key = llm.get("apiKey")
        if not isinstance(provider, str) or not isinstance(api_key, str):
            return None
        if not provider.strip() or not api_key.strip():
            return None
        return provider.strip().lower(), api_key

    def read_llm_provider_secret(self, provider: str) -> str | None:
        """Read a provider-specific LLM API key from backend-only secrets."""

        data = _read_json_object(self.secrets_path)
        providers = data.get("llmProviders")
        normalized_provider = provider.strip().lower()
        if isinstance(providers, Mapping):
            provider_secret = providers.get(normalized_provider)
            if isinstance(provider_secret, Mapping):
                api_key = provider_secret.get("apiKey")
                if isinstance(api_key, str) and api_key.strip():
                    return api_key
        legacy_secret = self.read_secret()
        if legacy_secret is not None and legacy_secret[0] == normalized_provider:
            return legacy_secret[1]
        return None

    def read_web_search_secret(self) -> tuple[str, str] | None:
        data = _read_json_object(self.secrets_path)
        web_search = data.get("webSearch")
        if not isinstance(web_search, Mapping):
            return None
        provider = web_search.get("provider")
        api_key = web_search.get("apiKey")
        if not isinstance(provider, str) or not isinstance(api_key, str):
            return None
        if not provider.strip() or not api_key.strip():
            return None
        return provider.strip().lower(), api_key

    def write_config(self, data: Mapping[str, Any]) -> None:
        payload = {
            "schemaVersion": _STORAGE_SCHEMA_VERSION,
            **dict(data),
        }
        _write_private_json(self.config_path, payload)

    def write_secret(self, *, provider: str, api_key: str, updated_at: datetime) -> None:
        existing = {
            key: value
            for key, value in self._safe_secrets().items()
            if key not in {"schemaVersion", "updatedAt", "llm"}
        }
        payload = {
            "schemaVersion": _STORAGE_SCHEMA_VERSION,
            "updatedAt": _timestamp(updated_at),
            **existing,
            "llm": {
                "provider": provider,
                "apiKey": api_key,
            },
        }
        _write_private_json(self.secrets_path, payload)

    def write_web_search_secret(
        self,
        *,
        provider: str,
        api_key: str,
        updated_at: datetime,
    ) -> None:
        existing = {
            key: value
            for key, value in self._safe_secrets().items()
            if key not in {"schemaVersion", "updatedAt", "webSearch"}
        }
        payload = {
            "schemaVersion": _STORAGE_SCHEMA_VERSION,
            "updatedAt": _timestamp(updated_at),
            **existing,
            "webSearch": {
                "provider": provider,
                "apiKey": api_key,
            },
        }
        _write_private_json(self.secrets_path, payload)

    def effective_env(self, base_env: Mapping[str, str]) -> dict[str, str]:
        env = dict(base_env)
        config = self.read_config()
        llm = config.get("llm")
        if isinstance(llm, Mapping):
            provider = llm.get("provider")
            model = llm.get("model")
            if isinstance(provider, str) and provider.strip():
                env["LLM_PROVIDER"] = provider.strip().lower()
            if isinstance(model, str) and model.strip():
                env["LLM_MODEL"] = model.strip()
        secret = self.read_secret()
        provider = env.get("LLM_PROVIDER", DEFAULT_FIRST_RUN_LLM_PROVIDER).strip().lower()
        if secret is not None and secret[0] == provider:
            env[_preferred_api_key_env_var(provider)] = secret[1]
        web_search = effective_web_search_settings(
            config=config,
            base_env=base_env,
            store=self,
        )
        if web_search.enabled:
            env["PLATO_WEB_SEARCH_ENABLED"] = "1"
        if web_search.fetch_enabled:
            env["PLATO_WEB_FETCH_ENABLED"] = "1"
            env["PLATO_WEB_FETCH_MAX_URLS"] = str(web_search.fetch_max_urls)
            env["PLATO_WEB_FETCH_MAX_CHARS_PER_URL"] = str(
                web_search.fetch_max_chars_per_url
            )
            env["PLATO_WEB_FETCH_MAX_TOTAL_CHARS"] = str(
                web_search.fetch_max_total_chars
            )
        if web_search.provider:
            env["PLATO_WEB_SEARCH_PROVIDER"] = web_search.provider
        if web_search.api_key is not None:
            env[web_search.api_key_env_var] = web_search.api_key
        return env

    def _safe_secrets(self) -> dict[str, Any]:
        try:
            return _read_json_object(self.secrets_path)
        except SettingsConfigStorageError:
            raise


def file_settings_config_store_for(
    *,
    workspace_root: Path,
    global_settings_root: Path | None = None,
) -> FileSettingsConfigStore:
    """Resolve the active settings store for a workspace runtime.

    Electron passes its userData directory as the global root so the Settings UI
    edits one Plato-level configuration across all workspaces. CLI callers that
    omit the global root keep the historical workspace-local store.
    """

    if global_settings_root is None:
        return FileSettingsConfigStore(workspace_root=workspace_root)
    return FileSettingsConfigStore(
        workspace_root=workspace_root,
        settings_dir_override=global_settings_root / "settings",
    )


@dataclass(frozen=True)
class DefaultSettingsConfigGateway:
    """Read, save, and recheck Product 1.0 first-run Settings config."""

    workspace_root: Path
    logging_enabled: bool = True
    logging_level: str = "INFO"
    selected_logging_profile: str | None = None
    default_model: str = DEFAULT_FIRST_RUN_LLM_MODEL
    env: Mapping[str, str] | None = None
    store: FileSettingsConfigStore | None = None

    def get_config(self) -> dict[str, Any]:
        return self._config_summary().to_contract_dict()

    def update_config(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        parsed = _parse_update_payload(payload)
        store = self._store()
        now = datetime.now(UTC)
        stored = store.read_config()
        updated = _updated_config_data(stored, parsed, now=now)
        errors = _validate_update(
            parsed,
            updated,
            base_env=self._base_env(),
            store=store,
            workspace_root=self.workspace_root,
        )
        if errors:
            raise SettingsConfigValidationError(tuple(errors))

        store.write_config(updated)
        llm = updated.get("llm")
        api_key = _api_key_replacement(parsed)
        if api_key is not None and isinstance(llm, Mapping):
            provider = str(llm["provider"])
            store.write_secret(provider=provider, api_key=api_key, updated_at=now)
        web_search = updated.get("webSearch")
        web_search_api_key = _web_search_api_key_replacement(parsed)
        if web_search_api_key is not None and isinstance(web_search, Mapping):
            provider = str(web_search["provider"])
            store.write_web_search_secret(
                provider=provider,
                api_key=web_search_api_key,
                updated_at=now,
            )

        readiness = self._readiness()
        result = SettingsConfigUpdateResult(
            updated_at=now,
            config=self._config_summary(now=now),
            readiness=readiness.to_contract_dict(),
        )
        return result.to_contract_dict()

    def get_readiness(self) -> dict[str, Any]:
        return self._readiness().to_contract_dict()

    def recheck_readiness(self) -> dict[str, Any]:
        return self.get_readiness()

    def _config_summary(self, *, now: datetime | None = None) -> SettingsConfigSummary:
        store = self._store()
        return build_settings_config_summary(
            workspace_root=self.workspace_root,
            store=store,
            env=self._base_env(),
            logging_enabled=self.logging_enabled,
            logging_level=self.logging_level,
            selected_logging_profile=self.selected_logging_profile,
            default_model=self.default_model,
            now=now,
        )

    def _readiness(self) -> SettingsReadinessReport:
        store = self._store()
        return build_settings_readiness_report(
            workspace_root=self.workspace_root,
            env=store.effective_env(self._base_env()),
            logging_enabled=self.logging_enabled,
            logging_level=self.logging_level,
            selected_logging_profile=_effective_logging_profile(
                store.read_config(),
                self.selected_logging_profile,
            ),
            default_model=self.default_model,
        )

    def _base_env(self) -> Mapping[str, str]:
        return os.environ if self.env is None else self.env

    def _store(self) -> FileSettingsConfigStore:
        return self.store or FileSettingsConfigStore(self.workspace_root)


def build_settings_config_summary(
    *,
    workspace_root: Path,
    store: FileSettingsConfigStore,
    env: Mapping[str, str],
    logging_enabled: bool = True,
    logging_level: str = "INFO",
    selected_logging_profile: str | None = None,
    default_model: str = DEFAULT_FIRST_RUN_LLM_MODEL,
    now: datetime | None = None,
) -> SettingsConfigSummary:
    config = store.read_config()
    effective_env = store.effective_env(env)
    llm = _llm_summary(
        config,
        effective_env,
        base_env=env,
        store=store,
        default_model=default_model,
    )
    logging = _logging_summary(
        workspace_root=workspace_root,
        config=config,
        enabled=logging_enabled,
        level=logging_level,
        selected_profile=selected_logging_profile,
    )
    web_search_settings = effective_web_search_settings(
        config=config,
        base_env=env,
        store=store,
    )
    return SettingsConfigSummary(
        generated_at=now or datetime.now(UTC),
        llm=llm,
        web_search=SettingsConfigWebSearch(
            enabled=web_search_settings.enabled,
            provider=web_search_settings.provider,
            provider_source=web_search_settings.provider_source,
            provider_options=_web_search_provider_options(),
            mode=web_search_settings.mode,
            max_results=web_search_settings.max_results,
            fetch_enabled=web_search_settings.fetch_enabled,
            fetch_max_urls=web_search_settings.fetch_max_urls,
            fetch_max_chars_per_url=web_search_settings.fetch_max_chars_per_url,
            fetch_max_total_chars=web_search_settings.fetch_max_total_chars,
            fetch_status=web_search_settings.fetch_status,
            api_key_configured=web_search_settings.api_key_source != "none",
            api_key_source=web_search_settings.api_key_source,
            api_key_env_var=web_search_settings.api_key_env_var,
            status=web_search_settings.status,
        ),
        logging=logging,
        diagnostics=SettingsConfigDiagnostics(
            bundle_export_available=True,
            http_export_route_available=True,
        ),
    )


def _llm_summary(
    config: Mapping[str, Any],
    effective_env: Mapping[str, str],
    *,
    base_env: Mapping[str, str],
    store: FileSettingsConfigStore,
    default_model: str,
) -> SettingsConfigLlm:
    stored_llm = config.get("llm")
    provider_source: SettingsConfigSource = "default"
    model_source: SettingsConfigSource = "default"
    if isinstance(stored_llm, Mapping) and isinstance(stored_llm.get("provider"), str):
        provider_source = "stored"
    elif "LLM_PROVIDER" in base_env:
        provider_source = "env"
    if isinstance(stored_llm, Mapping) and isinstance(stored_llm.get("model"), str):
        model_source = "stored"
    elif "LLM_MODEL" in base_env:
        model_source = "env"

    provider = (
        effective_env.get("LLM_PROVIDER", DEFAULT_FIRST_RUN_LLM_PROVIDER).strip().lower()
        or "unknown"
    )
    model = effective_env.get("LLM_MODEL", default_model).strip() or default_model
    api_key_source, api_key_env_var = _api_key_source(provider, base_env=base_env, store=store)

    return SettingsConfigLlm(
        provider=provider,
        provider_source=provider_source,
        provider_options=_provider_options(),
        model=model,
        model_source=model_source,
        api_key_configured=api_key_source != "none",
        api_key_source=api_key_source,
        api_key_env_var=api_key_env_var,
    )


def effective_web_search_settings(
    *,
    config: Mapping[str, Any],
    base_env: Mapping[str, str],
    store: FileSettingsConfigStore,
    api_key_replacement: str | None = None,
) -> EffectiveWebSearchSettings:
    stored_web_search = config.get("webSearch")
    stored_mapping = stored_web_search if isinstance(stored_web_search, Mapping) else {}
    env_enabled = _env_flag(base_env.get("PLATO_WEB_SEARCH_ENABLED"))
    stored_enabled = stored_mapping.get("enabled")
    enabled = (
        env_enabled
        if env_enabled is not None
        else bool(stored_enabled)
        if isinstance(stored_enabled, bool)
        else False
    )
    raw_env_provider = base_env.get("PLATO_WEB_SEARCH_PROVIDER")
    stored_provider = stored_mapping.get("provider")
    provider_source: SettingsConfigSource = "default"
    if isinstance(raw_env_provider, str) and raw_env_provider.strip():
        provider = raw_env_provider.strip().lower()
        provider_source = "env"
    elif isinstance(stored_provider, str) and stored_provider.strip():
        provider = stored_provider.strip().lower()
        provider_source = "stored"
    else:
        provider = "tavily"

    raw_mode = stored_mapping.get("mode")
    mode = raw_mode if isinstance(raw_mode, str) and raw_mode.strip() else "basic"
    if mode != "basic":
        mode = "basic"
    raw_max_results = stored_mapping.get("maxResults")
    max_results = _bounded_int(raw_max_results, default=5, minimum=1, maximum=10)
    env_fetch_enabled = _env_flag(base_env.get("PLATO_WEB_FETCH_ENABLED"))
    stored_fetch_enabled = stored_mapping.get("fetchEnabled")
    fetch_enabled = (
        env_fetch_enabled
        if env_fetch_enabled is not None
        else bool(stored_fetch_enabled)
        if isinstance(stored_fetch_enabled, bool)
        else False
    )
    fetch_enabled = bool(enabled and fetch_enabled)
    fetch_max_urls = _bounded_int(
        base_env.get("PLATO_WEB_FETCH_MAX_URLS", stored_mapping.get("fetchMaxUrls")),
        default=3,
        minimum=1,
        maximum=5,
    )
    fetch_max_chars_per_url = _bounded_int(
        base_env.get(
            "PLATO_WEB_FETCH_MAX_CHARS_PER_URL",
            stored_mapping.get("fetchMaxCharsPerUrl"),
        ),
        default=12000,
        minimum=1000,
        maximum=20000,
    )
    fetch_max_total_chars = _bounded_int(
        base_env.get(
            "PLATO_WEB_FETCH_MAX_TOTAL_CHARS",
            stored_mapping.get("fetchMaxTotalChars"),
        ),
        default=24000,
        minimum=1000,
        maximum=40000,
    )
    api_key_source, api_key_env_var, api_key = _web_search_api_key_source(
        provider,
        base_env=base_env,
        store=store,
        api_key_replacement=api_key_replacement,
    )
    status: SettingsWebSearchStatus
    if not enabled:
        status = "disabled"
    elif api_key_source == "none":
        status = "missing_key"
    else:
        status = "ready"
    fetch_status: SettingsWebFetchStatus
    if not fetch_enabled:
        fetch_status = "disabled"
    elif api_key_source == "none":
        fetch_status = "missing_key"
    else:
        fetch_status = "ready"
    return EffectiveWebSearchSettings(
        enabled=enabled,
        provider=provider,
        provider_source=provider_source,
        mode=mode,
        max_results=max_results,
        fetch_enabled=fetch_enabled,
        fetch_max_urls=fetch_max_urls,
        fetch_max_chars_per_url=fetch_max_chars_per_url,
        fetch_max_total_chars=fetch_max_total_chars,
        fetch_status=fetch_status,
        api_key=api_key,
        api_key_source=api_key_source,
        api_key_env_var=api_key_env_var,
        status=status,
    )


def _logging_summary(
    *,
    workspace_root: Path,
    config: Mapping[str, Any],
    enabled: bool,
    level: str,
    selected_profile: str | None,
) -> SettingsConfigLogging:
    stored_logging = config.get("logging")
    stored_selected = None
    has_stored_selected = False
    if isinstance(stored_logging, Mapping) and "selectedProfile" in stored_logging:
        has_stored_selected = True
        raw = stored_logging.get("selectedProfile")
        stored_selected = raw if isinstance(raw, str) and raw.strip() else None
    effective_selected = stored_selected if has_stored_selected else selected_profile
    source: SettingsConfigSource = (
        "stored" if has_stored_selected else "env" if selected_profile is not None else "default"
    )
    try:
        logging_config = build_session_logging_config(workspace_root, level=level)
    except Exception:
        return SettingsConfigLogging(
            enabled=enabled,
            level=str(level),
            selected_profile=effective_selected,
            selected_profile_source=source,
            selected_profile_known=False,
            default_profile=None,
            profiles=(),
        )
    profiles = tuple(
        {"id": name, "description": profile.description}
        for name, profile in sorted(logging_config.profiles.items())
    )
    selected_known = (
        effective_selected is None or effective_selected in logging_config.profiles
    )
    return SettingsConfigLogging(
        enabled=enabled,
        level=logging_config.default_level,
        selected_profile=effective_selected,
        selected_profile_source=source,
        selected_profile_known=selected_known,
        default_profile="normal" if "normal" in logging_config.profiles else None,
        profiles=profiles,
    )


def _parse_update_payload(payload: Mapping[str, Any]) -> UpdateSettingsConfigPayload:
    try:
        return UpdateSettingsConfigPayload.model_validate(payload)
    except ValidationError as exc:
        errors = tuple(
            SettingsConfigFieldError(
                path=_field_path(error.get("loc", ())),
                message=str(error.get("msg", "invalid value")),
            )
            for error in exc.errors(include_input=False)
        )
        raise SettingsConfigValidationError(errors) from None


def _updated_config_data(
    stored: Mapping[str, Any],
    parsed: UpdateSettingsConfigPayload,
    *,
    now: datetime,
) -> dict[str, Any]:
    updated = {
        key: value
        for key, value in dict(stored).items()
        if key not in {"schemaVersion", "updatedAt"}
    }
    if parsed.llm is not None:
        updated["llm"] = {
            "provider": parsed.llm.provider.strip().lower(),
            "model": parsed.llm.model.strip(),
        }
    if parsed.logging is not None and "selected_profile" in parsed.logging.model_fields_set:
        raw_profile = parsed.logging.selected_profile
        selected_profile = raw_profile.strip() if isinstance(raw_profile, str) else None
        updated["logging"] = {"selectedProfile": selected_profile or None}
    if parsed.web_search is not None:
        updated["webSearch"] = {
            "enabled": parsed.web_search.enabled,
            "provider": parsed.web_search.provider.strip().lower(),
            "mode": parsed.web_search.mode,
            "maxResults": parsed.web_search.max_results,
            "fetchEnabled": bool(
                parsed.web_search.enabled and parsed.web_search.fetch_enabled
            ),
            "fetchMaxUrls": parsed.web_search.fetch_max_urls,
            "fetchMaxCharsPerUrl": parsed.web_search.fetch_max_chars_per_url,
            "fetchMaxTotalChars": parsed.web_search.fetch_max_total_chars,
        }
    updated["updatedAt"] = _timestamp(now)
    return updated


def _validate_update(
    parsed: UpdateSettingsConfigPayload,
    updated: Mapping[str, Any],
    *,
    base_env: Mapping[str, str],
    store: FileSettingsConfigStore,
    workspace_root: Path,
) -> list[SettingsConfigFieldError]:
    errors: list[SettingsConfigFieldError] = []
    llm = updated.get("llm")
    if parsed.llm is not None:
        if not isinstance(llm, Mapping):
            errors.append(SettingsConfigFieldError("llm", "llm settings are required"))
        else:
            provider = str(llm.get("provider", "")).strip().lower()
            model = str(llm.get("model", "")).strip()
            if provider not in SUPPORTED_SETTINGS_PROVIDERS:
                errors.append(
                    SettingsConfigFieldError(
                        path="llm.provider",
                        message="unsupported provider",
                        allowed_values=SUPPORTED_SETTINGS_PROVIDERS,
                    )
                )
            if not model:
                errors.append(
                    SettingsConfigFieldError(
                        path="llm.model",
                        message="model must not be empty",
                    )
                )
            if provider in SUPPORTED_SETTINGS_PROVIDERS and not _has_effective_api_key(
                provider,
                parsed,
                base_env=base_env,
                store=store,
            ):
                errors.append(
                    SettingsConfigFieldError(
                        path="llm.apiKey",
                        message="an API key is required for the selected provider",
                        env_vars=_required_api_key_env_vars(provider),
                    )
                )

    logging = updated.get("logging")
    if parsed.logging is not None and isinstance(logging, Mapping):
        selected_profile = logging.get("selectedProfile")
        if isinstance(selected_profile, str) and selected_profile:
            try:
                logging_config = build_session_logging_config(workspace_root)
            except Exception:
                logging_config = None
            if logging_config is None or selected_profile not in logging_config.profiles:
                allowed = (
                    tuple(sorted(logging_config.profiles))
                    if logging_config is not None
                    else ()
                )
                errors.append(
                    SettingsConfigFieldError(
                        path="logging.selectedProfile",
                        message="unknown logging profile",
                        allowed_values=allowed,
                    )
                )
    web_search = updated.get("webSearch")
    if parsed.web_search is not None:
        if not isinstance(web_search, Mapping):
            errors.append(
                SettingsConfigFieldError(
                    "webSearch",
                    "web search settings are required",
                )
            )
        else:
            provider = str(web_search.get("provider", "")).strip().lower()
            if provider not in SUPPORTED_WEB_SEARCH_PROVIDERS:
                errors.append(
                    SettingsConfigFieldError(
                        path="webSearch.provider",
                        message="unsupported web search provider",
                        allowed_values=SUPPORTED_WEB_SEARCH_PROVIDERS,
                    )
                )
            enabled = bool(web_search.get("enabled"))
            if enabled and provider in SUPPORTED_WEB_SEARCH_PROVIDERS:
                effective = effective_web_search_settings(
                    config=updated,
                    base_env=base_env,
                    store=store,
                    api_key_replacement=_web_search_api_key_replacement(parsed),
                )
                if effective.status == "missing_key":
                    errors.append(
                        SettingsConfigFieldError(
                            path="webSearch.apiKey",
                            message=(
                                "an API key is required when web search is enabled"
                            ),
                            env_vars=_web_search_required_api_key_env_vars(provider),
                        )
                    )
    return errors


def _has_effective_api_key(
    provider: str,
    parsed: UpdateSettingsConfigPayload,
    *,
    base_env: Mapping[str, str],
    store: FileSettingsConfigStore,
) -> bool:
    api_key = _api_key_replacement(parsed)
    if api_key is not None:
        return True
    secret = store.read_secret()
    if secret is not None and secret[0] == provider and secret[1].strip():
        return True
    return any(bool(base_env.get(key, "").strip()) for key in _required_api_key_env_vars(provider))


def _api_key_replacement(parsed: UpdateSettingsConfigPayload) -> str | None:
    if parsed.llm is None or "api_key" not in parsed.llm.model_fields_set:
        return None
    raw = parsed.llm.api_key
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def _web_search_api_key_replacement(parsed: UpdateSettingsConfigPayload) -> str | None:
    if (
        parsed.web_search is None
        or "api_key" not in parsed.web_search.model_fields_set
    ):
        return None
    raw = parsed.web_search.api_key
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def _api_key_source(
    provider: str,
    *,
    base_env: Mapping[str, str],
    store: FileSettingsConfigStore,
) -> tuple[SettingsApiKeySource, str]:
    preferred_env_var = _preferred_api_key_env_var(provider)
    secret = store.read_secret()
    if secret is not None and secret[0] == provider:
        return "stored", preferred_env_var
    for key in _required_api_key_env_vars(provider):
        if base_env.get(key, "").strip():
            return "env", key
    return "none", preferred_env_var


def _web_search_api_key_source(
    provider: str,
    *,
    base_env: Mapping[str, str],
    store: FileSettingsConfigStore,
    api_key_replacement: str | None,
) -> tuple[SettingsApiKeySource, str, str | None]:
    preferred_env_var = _web_search_preferred_api_key_env_var(provider)
    if api_key_replacement is not None:
        return "stored", preferred_env_var, api_key_replacement
    secret = store.read_web_search_secret()
    if secret is not None and secret[0] == provider:
        return "stored", preferred_env_var, secret[1]
    for key in _web_search_required_api_key_env_vars(provider):
        value = base_env.get(key, "").strip()
        if value:
            return "env", key, value
    return "none", preferred_env_var, None


def _effective_logging_profile(
    config: Mapping[str, Any],
    fallback: str | None,
) -> str | None:
    logging = config.get("logging")
    if not isinstance(logging, Mapping) or "selectedProfile" not in logging:
        return fallback
    raw = logging.get("selectedProfile")
    return raw if isinstance(raw, str) and raw.strip() else None


def _provider_options() -> tuple[SettingsConfigProviderOption, ...]:
    return tuple(
        SettingsConfigProviderOption(
            id=provider,
            label=_PROVIDER_LABELS[provider],
            required_api_key_env_vars=_required_api_key_env_vars(provider),
            preferred_api_key_env_var=_preferred_api_key_env_var(provider),
        )
        for provider in SUPPORTED_SETTINGS_PROVIDERS
    )


def _web_search_provider_options() -> tuple[SettingsConfigWebSearchProviderOption, ...]:
    return tuple(
        SettingsConfigWebSearchProviderOption(
            id=provider,
            label=_WEB_SEARCH_PROVIDER_LABELS[provider],
            required_api_key_env_vars=_web_search_required_api_key_env_vars(provider),
            preferred_api_key_env_var=_web_search_preferred_api_key_env_var(provider),
        )
        for provider in SUPPORTED_WEB_SEARCH_PROVIDERS
    )


def _required_api_key_env_vars(provider: str) -> tuple[str, ...]:
    if provider == "deepseek":
        return ("DEEPSEEK_API_KEY", "LLM_API_KEY")
    if provider == "openrouter":
        return ("OPENROUTER_API_KEY", "LLM_API_KEY")
    return ("LLM_API_KEY",)


def _preferred_api_key_env_var(provider: str) -> str:
    return _required_api_key_env_vars(provider)[0]


def _web_search_required_api_key_env_vars(provider: str) -> tuple[str, ...]:
    if provider == "tavily":
        return ("TAVILY_API_KEY",)
    return ("TAVILY_API_KEY",)


def _web_search_preferred_api_key_env_var(provider: str) -> str:
    return _web_search_required_api_key_env_vars(provider)[0]


def _env_flag(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _bounded_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return min(maximum, max(minimum, value))
    if isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError:
            return default
        return min(maximum, max(minimum, parsed))
    return default


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SettingsConfigStorageError("local settings storage could not be read") from exc
    if not isinstance(parsed, dict):
        raise SettingsConfigStorageError("local settings storage is invalid")
    return parsed


def _write_private_json(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.tmp")
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        temp_path.write_text(f"{text}\n", encoding="utf-8")
        with contextlib.suppress(OSError):
            temp_path.chmod(0o600)
        temp_path.replace(path)
        with contextlib.suppress(OSError):
            path.chmod(0o600)
    except OSError as exc:
        raise SettingsConfigStorageError("local settings storage could not be written") from exc


def _field_path(loc: Any) -> str:
    parts = [str(part) for part in loc] if isinstance(loc, tuple) else [str(loc)]
    return ".".join(_camelize_part(part) for part in parts if part)


def _camelize_part(value: str) -> str:
    if "_" not in value:
        return value
    head, *tail = value.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "DefaultSettingsConfigGateway",
    "EffectiveWebSearchSettings",
    "FileSettingsConfigStore",
    "SETTINGS_CONFIG_SCHEMA_VERSION",
    "SETTINGS_CONFIG_UPDATE_SCHEMA_VERSION",
    "SUPPORTED_SETTINGS_PROVIDERS",
    "SUPPORTED_WEB_SEARCH_PROVIDERS",
    "SettingsConfigDiagnostics",
    "SettingsConfigFieldError",
    "SettingsConfigLlm",
    "SettingsConfigLogging",
    "SettingsConfigProviderOption",
    "SettingsConfigStorageError",
    "SettingsConfigSummary",
    "SettingsConfigUpdateResult",
    "SettingsConfigValidationError",
    "SettingsConfigWebSearch",
    "SettingsConfigWebSearchProviderOption",
    "SettingsWebFetchStatus",
    "UpdateSettingsConfigPayload",
    "effective_web_search_settings",
    "build_settings_config_summary",
]
