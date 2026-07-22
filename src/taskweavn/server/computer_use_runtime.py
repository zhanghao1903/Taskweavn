"""Runtime assembly helpers for optional computer-use backends."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from taskweavn.execution_plane import (
    InMemoryExecutionEnvRegistry,
    default_local_execution_env,
    local_macos_app_control_execution_env,
)
from taskweavn.integrations.app_control import (
    AppControlClientFactoryConfig,
)
from taskweavn.server.runtime_config_consumers import RuntimeComputerUseSettings
from taskweavn.tools import (
    ComputerUseBackend,
    MacOSComputerUseBackend,
    MacOSComputerUseBackendConfig,
)
from taskweavn.wechat_task_types import WECHAT_SEND_CAPABILITY


@dataclass(frozen=True)
class ComputerUseRuntimeSelection:
    """Resolved computer-use runtime wiring for a sidecar process."""

    enabled: bool
    backend: ComputerUseBackend | None
    backend_name: str
    allowed_apps: tuple[str, ...] = ()
    app_control_config: AppControlClientFactoryConfig | None = None


def build_computer_use_runtime(
    *,
    backend_name: str | None,
    allowed_apps: str | Sequence[str] | None = None,
    allow_coordinate_click: bool = True,
    screen_recording_required: bool = False,
    helper_manifest_path: str | None = None,
    helper_startup_failure: Mapping[str, str] | None = None,
) -> ComputerUseRuntimeSelection:
    """Build the optional computer-use backend selected by runtime config."""

    normalized = (backend_name or "disabled").strip().lower()
    parsed_allowed_apps = parse_computer_use_allowed_apps(allowed_apps)
    if normalized in {"", "disabled", "none", "off"}:
        return ComputerUseRuntimeSelection(
            enabled=False,
            backend=None,
            backend_name="disabled",
            allowed_apps=parsed_allowed_apps,
            app_control_config=None,
        )
    if normalized not in {"helper", "macos"}:
        raise ValueError(
            "unsupported computer-use backend "
            f"{backend_name!r}; valid values: disabled, helper, macos"
        )

    app_control_backend = "helper" if normalized == "helper" else "direct"
    app_control_config = AppControlClientFactoryConfig(
        backend=app_control_backend,
        allowed_apps=parsed_allowed_apps,
        allow_coordinate_click=allow_coordinate_click,
        screen_recording_required=screen_recording_required,
        helper_manifest_path=(
            None if helper_manifest_path is None else Path(helper_manifest_path).expanduser()
        ),
        helper_startup_failure=helper_startup_failure,
    )
    return ComputerUseRuntimeSelection(
        enabled=True,
        backend=MacOSComputerUseBackend(
            config=MacOSComputerUseBackendConfig(
                backend=app_control_backend,
                allowed_apps=parsed_allowed_apps,
                allow_coordinate_click=allow_coordinate_click,
                screen_recording_required=screen_recording_required,
                helper_manifest_path=app_control_config.helper_manifest_path,
            )
        ),
        backend_name=normalized,
        allowed_apps=parsed_allowed_apps,
        app_control_config=app_control_config,
    )


def parse_computer_use_allowed_apps(
    raw: str | Sequence[str] | None,
) -> tuple[str, ...]:
    """Parse a comma-separated or sequence app allowlist."""

    if raw is None:
        return ()
    if isinstance(raw, str):
        return tuple(app.strip() for app in raw.split(",") if app.strip())
    return tuple(app.strip() for app in raw if app.strip())


def resolve_computer_use_runtime(
    *,
    computer_use_settings: RuntimeComputerUseSettings,
    computer_use_backend: ComputerUseBackend | None,
    app_control_config: AppControlClientFactoryConfig | None = None,
) -> ComputerUseRuntimeSelection:
    """Resolve the runtime config snapshot into one concrete backend selection."""

    if not computer_use_settings.enabled:
        return ComputerUseRuntimeSelection(
            enabled=False,
            backend=None,
            backend_name="disabled",
            allowed_apps=computer_use_settings.allowed_apps,
            app_control_config=None,
        )
    normalized_backend = computer_use_settings.backend.strip().lower()
    resolved_app_control_config = app_control_config or AppControlClientFactoryConfig(
        backend="helper" if normalized_backend == "helper" else "direct",
        allowed_apps=computer_use_settings.allowed_apps,
        allow_coordinate_click=computer_use_settings.allow_coordinate_click,
    )
    if computer_use_backend is not None:
        return ComputerUseRuntimeSelection(
            enabled=True,
            backend=computer_use_backend,
            backend_name=computer_use_settings.backend,
            allowed_apps=computer_use_settings.allowed_apps,
            app_control_config=resolved_app_control_config,
        )
    return build_computer_use_runtime(
        backend_name=computer_use_settings.backend,
        allowed_apps=computer_use_settings.allowed_apps,
        allow_coordinate_click=computer_use_settings.allow_coordinate_click,
    )


def build_execution_env_registry(
    *,
    computer_use_settings: RuntimeComputerUseSettings,
    computer_use_available: bool | None = None,
) -> InMemoryExecutionEnvRegistry:
    """Build the execution environment registry for the local sidecar."""

    resolved_computer_use_enabled = (
        computer_use_settings.enabled
        if computer_use_available is None
        else computer_use_settings.enabled and computer_use_available
    )
    capabilities: tuple[str, ...] = ("execute", "testing")
    tool_pool: tuple[str, ...] = ()
    if resolved_computer_use_enabled:
        capabilities = (*capabilities, "computer_use", WECHAT_SEND_CAPABILITY)
        tool_pool = (*tool_pool, "computer_use", "wechat_desktop")
    env = (
        local_macos_app_control_execution_env(
            capabilities=capabilities,
            tool_pool=tool_pool,
        )
        if resolved_computer_use_enabled
        else default_local_execution_env(capabilities=capabilities, tool_pool=tool_pool)
    )
    return InMemoryExecutionEnvRegistry((env,))


__all__ = [
    "ComputerUseRuntimeSelection",
    "build_execution_env_registry",
    "build_computer_use_runtime",
    "parse_computer_use_allowed_apps",
    "resolve_computer_use_runtime",
]
