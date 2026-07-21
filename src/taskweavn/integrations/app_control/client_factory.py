"""Factories for published app-control package clients."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app_control_protocol import AppControlConfig, ComputerUseConfig, HelperConfig
from computer_use_macos import ComputerUseClient

from taskweavn.integrations.app_control.service_client import (
    UnixSocketAppControlClient,
)


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
    helper_startup_failure: Mapping[str, str] | None = None


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
            manifest_path=str(config.helper_manifest_path)
            if config.helper_manifest_path
            else None,
            allowed_apps=config.allowed_apps,
            auto_launch=False,
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
        normalized_backend = self._config.backend.strip().lower()
        if normalized_backend in {"helper", "service"}:
            manifest_path = self._config.helper_manifest_path
            if manifest_path is None:
                raise ValueError(
                    "Helper-hosted app-control service requires an endpoint manifest"
                )
            if not manifest_path.is_file() and self._config.helper_startup_failure:
                failure_kind = self._config.helper_startup_failure.get(
                    "failureKind", "helper_start_failed"
                )
                message = self._config.helper_startup_failure.get(
                    "message", "Computer Use Helper did not start."
                )
                raise ValueError(f"{failure_kind}: {message}")
            return UnixSocketAppControlClient.from_manifest_path(
                manifest_path,
                timeout_seconds=self._config.timeout_ms / 1000.0,
            )
        return ComputerUseClient.from_config(self.build_config())
