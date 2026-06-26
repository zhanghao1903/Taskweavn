"""Runtime assembly helpers for optional computer-use backends."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from taskweavn.core import WorkspaceLayout
from taskweavn.execution_plane import (
    WECHAT_SEND_CAPABILITY,
    InMemoryExecutionEnvRegistry,
    SqliteExecutionPlaneStore,
    SqliteWeChatSendBoundaryStore,
    WeChatSendRuntimeHandler,
    default_local_execution_env,
)
from taskweavn.integrations.wechat_desktop import (
    MacOSWeChatSearchDriver,
    WeChatDesktopAdapter,
)
from taskweavn.interaction import InProcessMessageBus, SqliteMessageStream
from taskweavn.server.runtime_config_consumers import RuntimeComputerUseSettings
from taskweavn.task import SqliteTaskBus
from taskweavn.tools import (
    ComputerUseBackend,
    ComputerUseHelperBackend,
    ComputerUseHelperBackendConfig,
    MacOSComputerUseBackend,
    MacOSComputerUseBackendConfig,
)


@dataclass(frozen=True)
class ComputerUseRuntimeSelection:
    """Resolved computer-use runtime wiring for a sidecar process."""

    enabled: bool
    backend: ComputerUseBackend | None
    backend_name: str
    allowed_apps: tuple[str, ...] = ()


def build_computer_use_runtime(
    *,
    backend_name: str | None,
    allowed_apps: str | Sequence[str] | None = None,
    allow_coordinate_click: bool = False,
    screen_recording_required: bool = False,
    helper_manifest_path: str | None = None,
    helper_endpoint: str | None = None,
    helper_token: str | None = None,
    helper_app_path: str | None = None,
    helper_auto_launch: bool = False,
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
        )
    if normalized == "helper":
        return ComputerUseRuntimeSelection(
            enabled=True,
            backend=ComputerUseHelperBackend(
                config=ComputerUseHelperBackendConfig.from_environment(
                    allowed_apps=parsed_allowed_apps,
                    allow_coordinate_click=allow_coordinate_click,
                    allow_screenshot=screen_recording_required,
                )
                if helper_manifest_path is None
                and helper_endpoint is None
                and helper_token is None
                and helper_app_path is None
                and not helper_auto_launch
                else ComputerUseHelperBackendConfig(
                    endpoint_manifest_path=(
                        None
                        if helper_manifest_path is None
                        else Path(helper_manifest_path).expanduser()
                    ),
                    endpoint=helper_endpoint,
                    token=helper_token,
                    helper_app_path=(
                        None
                        if helper_app_path is None
                        else Path(helper_app_path).expanduser()
                    ),
                    helper_auto_launch=helper_auto_launch,
                    allowed_apps=parsed_allowed_apps,
                    allow_coordinate_click=allow_coordinate_click,
                    allow_screenshot=screen_recording_required,
                )
            ),
            backend_name="helper",
            allowed_apps=parsed_allowed_apps,
        )
    if normalized != "macos":
        raise ValueError(
            "unsupported computer-use backend "
            f"{backend_name!r}; valid values: disabled, helper, macos"
        )

    return ComputerUseRuntimeSelection(
        enabled=True,
        backend=MacOSComputerUseBackend(
            config=MacOSComputerUseBackendConfig(
                allowed_apps=parsed_allowed_apps,
                allow_coordinate_click=allow_coordinate_click,
                screen_recording_required=screen_recording_required,
            )
        ),
        backend_name="macos",
        allowed_apps=parsed_allowed_apps,
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


def build_execution_env_registry(
    *,
    computer_use_settings: RuntimeComputerUseSettings,
) -> InMemoryExecutionEnvRegistry:
    """Build the execution environment registry for the local sidecar."""

    capabilities: tuple[str, ...] = ("execute", "testing")
    tool_pool: tuple[str, ...] = ()
    if computer_use_settings.enabled:
        capabilities = (*capabilities, "computer_use", WECHAT_SEND_CAPABILITY)
        tool_pool = (*tool_pool, "computer_use", "wechat_desktop")
    return InMemoryExecutionEnvRegistry(
        (
            default_local_execution_env(
                capabilities=capabilities,
                tool_pool=tool_pool,
            ),
        )
    )


def build_execution_plane_runtime_handlers(
    *,
    layout: WorkspaceLayout,
    task_bus: SqliteTaskBus,
    message_bus: InProcessMessageBus,
    message_stream: SqliteMessageStream,
    execution_plane_store: SqliteExecutionPlaneStore,
    computer_use_settings: RuntimeComputerUseSettings,
    computer_use_backend: ComputerUseBackend | None,
) -> tuple[WeChatSendRuntimeHandler, ...]:
    """Build optional execution-plane runtime handlers for computer-use tools."""

    if not computer_use_settings.enabled or computer_use_backend is None:
        return ()
    wechat_boundary_store = SqliteWeChatSendBoundaryStore(
        layout.meta_dir / "wechat_send_boundaries.sqlite"
    )
    return (
        WeChatSendRuntimeHandler(
            task_bus=task_bus,
            message_bus=message_bus,
            message_stream=message_stream,
            execution_store=execution_plane_store,
            boundary_store=wechat_boundary_store,
            adapter=WeChatDesktopAdapter(
                computer_use_backend,
                contact_search_driver=MacOSWeChatSearchDriver(),
            ),
        ),
    )


__all__ = [
    "ComputerUseRuntimeSelection",
    "build_execution_env_registry",
    "build_execution_plane_runtime_handlers",
    "build_computer_use_runtime",
    "parse_computer_use_allowed_apps",
]
