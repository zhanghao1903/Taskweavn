"""Protocol adapter for the package Unix-socket app-control service."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app_control_protocol import ToolCommand, ToolEvent, ToolObservation
from computer_use_macos import LocalServiceError, UnixSocketServiceClient

from taskweavn.integrations.app_control.service_manifest import (
    AppControlServiceManifest,
)


@dataclass(frozen=True)
class UnixSocketAppControlClient:
    """Expose a remote local service as the standard AppControlClient API."""

    manifest: AppControlServiceManifest
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("app-control service timeout must be positive")

    @classmethod
    def from_manifest_path(
        cls,
        manifest_path: str | Path,
        *,
        timeout_seconds: float = 30.0,
    ) -> UnixSocketAppControlClient:
        return cls(
            manifest=AppControlServiceManifest.load(Path(manifest_path)),
            timeout_seconds=timeout_seconds,
        )

    def run_command(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: object | None = None,
    ) -> ToolObservation:
        tool_command = _coerce_command(command)
        envelopes = self._request(tool_command)
        observation: ToolObservation | None = None
        for envelope in envelopes:
            event = _event_from_envelope(envelope)
            if event is not None:
                _notify_observer(observer, event)
            parsed = _observation_from_envelope(envelope)
            if parsed is not None:
                observation = parsed
        if observation is None:
            raise LocalServiceError("app-control service returned no final observation")
        return observation

    def run_stream(
        self,
        command: ToolCommand | Mapping[str, Any],
        *,
        observer: object | None = None,
    ) -> Iterator[ToolEvent]:
        tool_command = _coerce_command(command)
        envelopes = self._request(tool_command)
        for envelope in envelopes:
            event = _event_from_envelope(envelope)
            if event is None:
                continue
            _notify_observer(observer, event)
            yield event

    def _request(self, command: ToolCommand) -> list[dict[str, Any]]:
        timeout = self.timeout_seconds
        if command.timeout_ms is not None:
            timeout = max(timeout, command.timeout_ms / 1000.0 + 5.0)
        client = UnixSocketServiceClient(
            self.manifest.endpoint,
            token=self.manifest.read_token(),
            timeout=timeout,
        )
        return client.run_command(
            command.to_dict(),
            action="stream",
            request_id=f"plato_{uuid4().hex}",
        )


def _coerce_command(command: ToolCommand | Mapping[str, Any]) -> ToolCommand:
    if isinstance(command, ToolCommand):
        return command
    return ToolCommand.from_dict(dict(command))


def _event_from_envelope(envelope: Mapping[str, Any]) -> ToolEvent | None:
    if envelope.get("status") != "event":
        return None
    payload = envelope.get("event")
    if not isinstance(payload, dict):
        raise LocalServiceError("app-control service event envelope is invalid")
    return ToolEvent.from_dict(payload)


def _observation_from_envelope(
    envelope: Mapping[str, Any],
) -> ToolObservation | None:
    if envelope.get("status") == "event":
        return None
    if envelope.get("success") is not True:
        error = envelope.get("error")
        raise LocalServiceError(f"app-control service request failed: {error or envelope}")
    payload = envelope.get("observation")
    if not isinstance(payload, dict):
        raise LocalServiceError("app-control service response has no observation")
    return ToolObservation.from_dict(payload)


def _notify_observer(observer: object | None, event: ToolEvent) -> None:
    if observer is None:
        return
    callback = getattr(observer, "on_event", None)
    if not callable(callback):
        raise TypeError("app-control observer must expose on_event(event)")
    callback(event)


__all__ = ["UnixSocketAppControlClient"]
