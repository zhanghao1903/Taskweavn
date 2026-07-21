"""Endpoint manifest shared by the app-control Helper and sidecar."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

APP_CONTROL_SERVICE_MANIFEST_SCHEMA = "plato.app_control.service_manifest.v1"


@dataclass(frozen=True)
class AppControlServiceManifest:
    """Stable discovery metadata for one local Helper service process."""

    endpoint: Path
    token_path: Path
    pid: int
    bundle_id: str
    service_version: str
    app_path: Path | None = None
    schema: str = APP_CONTROL_SERVICE_MANIFEST_SCHEMA
    transport: str = "unix_socket"

    def __post_init__(self) -> None:
        if self.schema != APP_CONTROL_SERVICE_MANIFEST_SCHEMA:
            raise ValueError(f"unsupported app-control service manifest: {self.schema}")
        if self.transport != "unix_socket":
            raise ValueError(f"unsupported app-control service transport: {self.transport}")
        if self.pid <= 0:
            raise ValueError("app-control service pid must be positive")
        if not self.bundle_id.strip():
            raise ValueError("app-control service bundle id is required")
        if not self.service_version.strip():
            raise ValueError("app-control service version is required")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema": self.schema,
            "transport": self.transport,
            "endpoint": str(self.endpoint.expanduser()),
            "tokenPath": str(self.token_path.expanduser()),
            "pid": self.pid,
            "bundleId": self.bundle_id,
            "serviceVersion": self.service_version,
        }
        if self.app_path is not None:
            payload["appPath"] = str(self.app_path.expanduser())
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AppControlServiceManifest:
        return cls(
            schema=_required_string(payload, "schema"),
            transport=_required_string(payload, "transport"),
            endpoint=Path(_required_string(payload, "endpoint")).expanduser(),
            token_path=Path(_required_string(payload, "tokenPath")).expanduser(),
            pid=_required_int(payload, "pid"),
            bundle_id=_required_string(payload, "bundleId"),
            service_version=_required_string(payload, "serviceVersion"),
            app_path=_optional_path(payload, "appPath"),
        )

    @classmethod
    def load(cls, path: Path) -> AppControlServiceManifest:
        try:
            payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"could not read app-control service manifest: {path}") from exc
        if not isinstance(payload, dict):
            raise ValueError("app-control service manifest must be a JSON object")
        return cls.from_dict(payload)

    def write(self, path: Path) -> None:
        destination = path.expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(destination)

    def read_token(self) -> str:
        try:
            token = self.token_path.expanduser().read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(
                f"could not read app-control service token: {self.token_path}"
            ) from exc
        if not token:
            raise ValueError("app-control service token is empty")
        return token


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"app-control service manifest requires string field: {key}")
    return value.strip()


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"app-control service manifest requires integer field: {key}")
    return value


def _optional_path(payload: dict[str, Any], key: str) -> Path | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"app-control service manifest requires string field: {key}")
    return Path(value).expanduser()


__all__ = [
    "APP_CONTROL_SERVICE_MANIFEST_SCHEMA",
    "AppControlServiceManifest",
]
