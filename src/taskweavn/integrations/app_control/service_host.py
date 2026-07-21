"""Product-owned host for the package app-control Unix-socket service."""

from __future__ import annotations

import os
import secrets
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app_control_protocol import AppControlConfig, build_logging_observer
from computer_use_macos import (
    ComputerUseClient,
    LocalCommandService,
    UnixSocketCommandService,
)
from computer_use_macos import (
    __version__ as computer_use_macos_version,
)

from taskweavn.integrations.app_control.client_factory import (
    AppControlClientFactoryConfig,
    build_app_control_config,
)
from taskweavn.integrations.app_control.service_manifest import (
    AppControlServiceManifest,
)

AppControlClientBuilder = Callable[[AppControlConfig], Any]
ObserverBuilder = Callable[[AppControlConfig], object | None]


@dataclass(frozen=True)
class AppControlServiceHostConfig:
    """Fixed startup inputs owned by Electron and the Helper bundle."""

    socket_path: Path
    token_path: Path
    manifest_path: Path
    bundle_id: str
    app_path: Path | None = None
    allowed_apps: tuple[str, ...] = ()
    allowed_app_bundle_ids: Mapping[str, str] | None = None
    allow_coordinate_click: bool = False
    screen_recording_required: bool = False
    timeout_ms: int = 10_000


class AppControlServiceHost:
    """Own a direct macOS client and publish it through the package service."""

    def __init__(
        self,
        config: AppControlServiceHostConfig,
        *,
        client_builder: AppControlClientBuilder = ComputerUseClient.from_config,
        observer_builder: ObserverBuilder = build_logging_observer,
    ) -> None:
        self._config = config
        self._client_builder = client_builder
        self._observer_builder = observer_builder
        self._server: UnixSocketCommandService | None = None
        self._server_thread: threading.Thread | None = None
        self._manifest: AppControlServiceManifest | None = None

    @property
    def manifest(self) -> AppControlServiceManifest | None:
        return self._manifest

    def start(self) -> AppControlServiceManifest:
        if self._server is not None:
            raise RuntimeError("app-control Helper service is already started")

        self._prepare_private_parent(self._config.socket_path)
        self._prepare_private_parent(self._config.token_path)
        self._prepare_private_parent(self._config.manifest_path)
        token = secrets.token_urlsafe(32)
        self._write_token(token)

        app_config = build_app_control_config(
            AppControlClientFactoryConfig(
                backend="direct",
                allowed_apps=self._config.allowed_apps,
                allowed_app_bundle_ids=self._config.allowed_app_bundle_ids,
                allow_coordinate_click=self._config.allow_coordinate_click,
                screen_recording_required=self._config.screen_recording_required,
                timeout_ms=self._config.timeout_ms,
            )
        )
        app_control = self._client_builder(app_config)
        service = LocalCommandService(
            app_control,
            token=token,
            observer=self._observer_builder(app_config),
        )
        server = UnixSocketCommandService(self._config.socket_path, service)
        try:
            thread = server.serve_in_thread()
            manifest = AppControlServiceManifest(
                endpoint=server.socket_path,
                token_path=self._config.token_path,
                pid=os.getpid(),
                bundle_id=self._config.bundle_id,
                service_version=computer_use_macos_version,
                app_path=self._config.app_path,
            )
            manifest.write(self._config.manifest_path)
        except Exception:
            server.shutdown()
            self._remove_runtime_files()
            raise

        self._server = server
        self._server_thread = thread
        self._manifest = manifest
        return manifest

    def serve_until(self, stop_event: threading.Event) -> None:
        self.start()
        try:
            stop_event.wait()
        finally:
            self.stop()

    def stop(self) -> None:
        server = self._server
        thread = self._server_thread
        self._server = None
        self._server_thread = None
        self._manifest = None
        if server is not None:
            server.shutdown()
        if thread is not None:
            thread.join(timeout=2.0)
        self._remove_runtime_files()

    def _write_token(self, token: str) -> None:
        destination = self._config.token_path.expanduser()
        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.write_text(token + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(destination)

    def _remove_runtime_files(self) -> None:
        for path in (self._config.manifest_path, self._config.token_path):
            try:
                path.expanduser().unlink(missing_ok=True)
            except OSError:
                continue

    @staticmethod
    def _prepare_private_parent(path: Path) -> None:
        parent = path.expanduser().parent
        if parent.exists():
            if not parent.is_dir():
                raise ValueError(f"app-control runtime parent is not a directory: {parent}")
            return
        parent.mkdir(parents=True, mode=0o700)


__all__ = [
    "AppControlServiceHost",
    "AppControlServiceHostConfig",
]
