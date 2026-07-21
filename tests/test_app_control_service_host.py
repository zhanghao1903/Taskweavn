from __future__ import annotations

import shutil
import stat
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from app_control_protocol import (
    ToolCommand,
    ToolEvent,
    ToolEventType,
    ToolObservation,
)

from taskweavn.integrations.app_control import (
    APP_CONTROL_SERVICE_MANIFEST_SCHEMA,
    AppControlClientFactory,
    AppControlClientFactoryConfig,
    AppControlServiceHost,
    AppControlServiceHostConfig,
    AppControlServiceManifest,
    UnixSocketAppControlClient,
)


class _FakeAppControl:
    def run_command(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        del observer
        tool_command = _coerce_command(command)
        return _observation(tool_command)

    def run_stream(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: object | None = None,
    ) -> Iterator[ToolEvent]:
        del observer
        tool_command = _coerce_command(command)
        observation = _observation(tool_command)
        yield ToolEvent(
            command_id=tool_command.command_id,
            seq=0,
            event_type=ToolEventType.STARTED,
            phase=tool_command.operation,
            summary="Fake app-control command started.",
        )
        yield ToolEvent(
            command_id=tool_command.command_id,
            seq=1,
            event_type=ToolEventType.OBSERVATION,
            phase=tool_command.operation,
            status=observation.status,
            summary=observation.summary,
            data={"observation": observation.to_dict()},
        )


class _RecordingObserver:
    def __init__(self) -> None:
        self.events: list[ToolEvent] = []

    def on_event(self, event: ToolEvent) -> None:
        self.events.append(event)


def test_service_manifest_round_trip_and_token(tmp_path: Path) -> None:
    token_path = tmp_path / "runtime" / "service.token"
    token_path.parent.mkdir()
    token_path.write_text("secret\n", encoding="utf-8")
    manifest_path = token_path.parent / "service.json"
    manifest = AppControlServiceManifest(
        endpoint=token_path.parent / "service.sock",
        token_path=token_path,
        pid=123,
        bundle_id="com.taskweavn.plato.computer-use-helper.dev",
        service_version="0.3.0",
        app_path=Path("/Applications/Plato Computer Use Helper Dev.app"),
    )

    manifest.write(manifest_path)

    loaded = AppControlServiceManifest.load(manifest_path)
    assert loaded == manifest
    assert loaded.schema == APP_CONTROL_SERVICE_MANIFEST_SCHEMA
    assert loaded.read_token() == "secret"
    assert loaded.app_path == Path("/Applications/Plato Computer Use Helper Dev.app")
    assert stat.S_IMODE(manifest_path.stat().st_mode) == 0o600


def test_helper_host_does_not_change_existing_parent_permissions(tmp_path: Path) -> None:
    tmp_path.chmod(0o755)

    AppControlServiceHost._prepare_private_parent(tmp_path / "service.sock")

    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o755


def test_helper_service_host_round_trip_over_unix_socket(tmp_path: Path) -> None:
    del tmp_path
    runtime_root = Path(tempfile.mkdtemp(prefix="plato-app-control-", dir="/tmp"))
    manifest_path = runtime_root / "service.json"
    host = AppControlServiceHost(
        AppControlServiceHostConfig(
            socket_path=runtime_root / "service.sock",
            token_path=runtime_root / "service.token",
            manifest_path=manifest_path,
            bundle_id="com.taskweavn.plato.computer-use-helper.dev",
            allowed_apps=("WeChat",),
            allowed_app_bundle_ids={"WeChat": "com.tencent.xinWeChat"},
        ),
        client_builder=lambda _config: _FakeAppControl(),
        observer_builder=lambda _config: None,
    )

    manifest = host.start()
    observer = _RecordingObserver()
    client = UnixSocketAppControlClient.from_manifest_path(manifest_path)
    command = ToolCommand(
        command_id="cmd_readiness",
        tool="macos.computer_use",
        operation="readiness",
    )

    try:
        observation = client.run_command(command, observer=observer)

        assert observation.success is True
        assert observation.command_id == "cmd_readiness"
        assert observation.observation == {"status": "ready"}
        assert [event.event_type for event in observer.events] == [
            ToolEventType.STARTED,
            ToolEventType.OBSERVATION,
        ]
        assert manifest.endpoint.is_socket()
        assert stat.S_IMODE(manifest.endpoint.stat().st_mode) == 0o600
        assert stat.S_IMODE(manifest.token_path.stat().st_mode) == 0o600
    finally:
        host.stop()
        shutil.rmtree(runtime_root, ignore_errors=True)

    assert not manifest.endpoint.exists()
    assert not manifest.token_path.exists()
    assert not manifest_path.exists()


def test_client_factory_uses_service_manifest_for_helper_backend(tmp_path: Path) -> None:
    token_path = tmp_path / "service.token"
    token_path.write_text("secret\n", encoding="utf-8")
    manifest_path = tmp_path / "service.json"
    AppControlServiceManifest(
        endpoint=tmp_path / "service.sock",
        token_path=token_path,
        pid=123,
        bundle_id="com.taskweavn.plato.computer-use-helper.dev",
        service_version="0.3.0",
    ).write(manifest_path)

    client = AppControlClientFactory(
        AppControlClientFactoryConfig(
            backend="helper",
            helper_manifest_path=manifest_path,
            timeout_ms=12_000,
        )
    ).create_client()

    assert isinstance(client, UnixSocketAppControlClient)
    assert client.manifest.endpoint == tmp_path / "service.sock"
    assert client.timeout_seconds == 12.0


def test_client_factory_preserves_electron_helper_startup_failure(
    tmp_path: Path,
) -> None:
    factory = AppControlClientFactory(
        AppControlClientFactoryConfig(
            backend="helper",
            helper_manifest_path=tmp_path / "missing.json",
            helper_startup_failure={
                "failureKind": "helper_app_missing",
                "message": "Dev Helper app is not installed.",
            },
        )
    )

    with pytest.raises(
        ValueError,
        match="helper_app_missing: Dev Helper app is not installed",
    ):
        factory.create_client()


def _coerce_command(command: ToolCommand | Mapping[str, Any]) -> ToolCommand:
    if isinstance(command, ToolCommand):
        return command
    return ToolCommand.from_dict(dict(command))


def _observation(command: ToolCommand) -> ToolObservation:
    return ToolObservation.ok(
        command_id=command.command_id,
        tool=command.tool,
        operation=command.operation,
        summary="Fake app-control command completed.",
        observation={"status": "ready"},
    )
