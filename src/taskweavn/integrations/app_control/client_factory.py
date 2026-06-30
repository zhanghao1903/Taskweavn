"""Factories for published app-control package clients."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app_control_protocol import AppControlConfig, ComputerUseConfig, HelperConfig
from computer_use_macos import ComputerUseClient


@dataclass(frozen=True)
class AppControlClientFactoryConfig:
    """Plato-owned config normalized for the package client."""

    backend: str = "direct"
    allowed_apps: tuple[str, ...] = ()
    allowed_app_bundle_ids: Mapping[str, str] | None = None
    allow_coordinate_click: bool = False
    screen_recording_required: bool = False
    timeout_ms: int = 10_000
    helper_manifest_path: Path | None = None
    helper_app_path: Path | None = None
    helper_bundle_id: str | None = None
    helper_endpoint: str | None = None
    helper_token: str | None = None
    helper_auto_launch: bool = False


def build_app_control_config(config: AppControlClientFactoryConfig) -> AppControlConfig:
    """Build the shared package config from Plato runtime settings."""

    return AppControlConfig(
        computer_use=ComputerUseConfig(
            backend=config.backend,
            allowed_apps=config.allowed_apps,
            allowed_app_bundle_ids=dict(config.allowed_app_bundle_ids or {}),
            allow_coordinate_click=config.allow_coordinate_click,
            screen_recording_required=config.screen_recording_required,
            timeout_ms=config.timeout_ms,
        ),
        helper=HelperConfig(
            helper_app_path=str(config.helper_app_path) if config.helper_app_path else None,
            bundle_id=config.helper_bundle_id,
            manifest_path=str(config.helper_manifest_path)
            if config.helper_manifest_path
            else None,
            endpoint=config.helper_endpoint,
            token=config.helper_token,
            allowed_apps=config.allowed_apps,
            auto_launch=config.helper_auto_launch,
        ),
    )


class AppControlClientFactory:
    """Create protocol-compatible app-control clients.

    This keeps concrete package imports out of Router, TaskBus, and Agent code.
    """

    def __init__(self, config: AppControlClientFactoryConfig) -> None:
        self._config = config

    @property
    def config(self) -> AppControlClientFactoryConfig:
        return self._config

    def build_config(self) -> AppControlConfig:
        return build_app_control_config(self._config)

    def create_client(self) -> Any:
        return ComputerUseClient.from_config(self.build_config())
