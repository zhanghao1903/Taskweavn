"""Adapter from Plato's computer-use contract to macos-computer-use.

The external package is optional. Import failures are represented as sanitized
``not_available`` observations so the default runtime remains safe on non-macOS
hosts and in CI.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from typing import Any, Protocol, cast

from taskweavn.tools.computer_use import ComputerUseBackend
from taskweavn.types.computer_use import (
    ComputerUseAction,
    ComputerUseObservation,
    ComputerUseStatus,
)


class MacOSComputerUseClientProtocol(Protocol):
    """Subset of the external package client used by Plato."""

    def readiness(self) -> Any: ...

    def open_app(self, app: str, *, timeout: float = 10.0) -> Any: ...

    def observe(
        self,
        *,
        target_app: str | None = None,
        timeout: float = 5.0,
    ) -> Any: ...

    def type_text(
        self,
        text: str,
        *,
        target_app: str | None = None,
        timeout: float = 5.0,
    ) -> Any: ...

    def click(
        self,
        target: str,
        *,
        target_app: str | None = None,
        snapshot_id: str | None = None,
        timeout: float = 5.0,
        confirmed: bool = False,
        role_hints: tuple[str, ...] = ("AXButton",),
        aliases: tuple[str, ...] = (),
        max_nodes: int = 200,
        max_depth: int = 6,
        lookup_timeout: float | None = None,
        click_timeout: float | None = None,
        post_click_observe: bool = True,
    ) -> Any: ...

    def press_key(
        self,
        keys: tuple[str, ...],
        *,
        target_app: str | None = None,
        timeout: float = 5.0,
    ) -> Any: ...

    def wait(self, *, seconds: float = 1.0) -> Any: ...


@dataclass(frozen=True)
class MacOSComputerUseBackendConfig:
    """Runtime options passed to ``macos-computer-use`` when available."""

    allowed_apps: tuple[str, ...] = ()
    enabled: bool = True
    allow_coordinate_click: bool = False
    screen_recording_required: bool = False
    max_text_chars: int = 4_000


class MacOSComputerUseBackend(ComputerUseBackend):
    """Plato backend adapter over the optional macOS package."""

    def __init__(
        self,
        *,
        client: MacOSComputerUseClientProtocol | None = None,
        config: MacOSComputerUseBackendConfig | None = None,
    ) -> None:
        self._config = config or MacOSComputerUseBackendConfig()
        self._import_error: str | None = None
        self._client: MacOSComputerUseClientProtocol | None
        if client is not None:
            self._client = client
            return
        self._client = self._load_client()

    def _load_client(self) -> MacOSComputerUseClientProtocol | None:
        try:
            module = importlib.import_module("macos_computer_use")
            client_cls = module.MacOSComputerUseClient
            return cast(
                MacOSComputerUseClientProtocol,
                client_cls(
                    allowed_apps=self._config.allowed_apps,
                    enabled=self._config.enabled,
                    allow_coordinate_click=self._config.allow_coordinate_click,
                    screen_recording_required=self._config.screen_recording_required,
                    max_text_chars=self._config.max_text_chars,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - optional dependency boundary.
            self._import_error = f"{type(exc).__name__}: {exc}"
            return None

    def readiness(self, *, action_id: str | None = None) -> ComputerUseObservation:
        if self._client is None:
            return ComputerUseObservation(
                action_id=action_id,
                success=False,
                operation="readiness",
                status="not_available",
                summary="macOS computer-use package is not available.",
                metadata={"error": self._import_error or "package import failed"},
            )
        try:
            readiness = self._client.readiness()
        except Exception as exc:  # noqa: BLE001 - sanitize package boundary.
            return ComputerUseObservation(
                action_id=action_id,
                success=False,
                operation="readiness",
                status="failed",
                summary=f"macOS computer-use readiness failed: {type(exc).__name__}",
                metadata={"error": str(exc)},
            )
        readiness_status = _enum_value(getattr(readiness, "status", "error"))
        status = _map_readiness_status(readiness_status)
        setup_hint = getattr(readiness, "setup_hint", None)
        summary = f"macOS computer-use readiness: {readiness_status}."
        if setup_hint:
            summary = f"{summary} {setup_hint}"
        readiness_payload = _to_dict(readiness)
        return ComputerUseObservation(
            action_id=action_id,
            success=status == "ok",
            operation="readiness",
            status=status,
            summary=summary,
            metadata={
                "readiness": readiness_payload,
                "diagnostics": _readiness_diagnostics(readiness_payload, self._client),
            },
        )

    def execute(self, action: ComputerUseAction) -> ComputerUseObservation:
        if action.operation == "readiness":
            return self.readiness(action_id=action.event_id)
        if self._client is None:
            return ComputerUseObservation(
                action_id=action.event_id,
                success=False,
                operation=action.operation,
                status="not_available",
                summary="macOS computer-use package is not available.",
                metadata={"error": self._import_error or "package import failed"},
            )
        try:
            result = self._execute_with_client(action)
        except Exception as exc:  # noqa: BLE001 - sanitize package boundary.
            return ComputerUseObservation(
                action_id=action.event_id,
                success=False,
                operation=action.operation,
                status="failed",
                summary=f"macOS computer-use operation failed: {type(exc).__name__}",
                metadata={"error": str(exc)},
            )
        return _result_to_observation(action, result)

    def _execute_with_client(self, action: ComputerUseAction) -> Any:
        assert self._client is not None
        if action.operation == "open_app":
            assert action.target is not None
            return self._client.open_app(action.target, timeout=action.timeout_seconds)
        if action.operation == "observe":
            return self._client.observe(
                target_app=_target_app(action),
                timeout=action.timeout_seconds,
            )
        if action.operation == "type_text":
            assert action.text is not None
            return self._client.type_text(
                action.text,
                target_app=_target_app(action),
                timeout=action.timeout_seconds,
            )
        if action.operation == "click":
            assert action.target is not None
            return self._client.click(
                action.target,
                target_app=_target_app(action),
                snapshot_id=_string_metadata(action, "snapshot_id"),
                timeout=action.timeout_seconds,
                confirmed=_bool_metadata(action, "confirmed_by_user"),
                role_hints=_tuple_metadata(
                    action,
                    "role_hints",
                    default=("AXButton",),
                ),
                aliases=_tuple_metadata(action, "aliases"),
                max_nodes=_int_metadata(action, "max_nodes", default=200),
                max_depth=_int_metadata(action, "max_depth", default=6),
                lookup_timeout=_float_metadata(action, "lookup_timeout"),
                click_timeout=_float_metadata(action, "click_timeout"),
                post_click_observe=_bool_metadata(
                    action,
                    "post_click_observe",
                    default=True,
                ),
            )
        if action.operation == "press_key":
            return self._client.press_key(
                action.keys,
                target_app=_target_app(action),
                timeout=action.timeout_seconds,
            )
        if action.operation == "wait":
            return self._client.wait(seconds=action.timeout_seconds)
        return _UnsupportedResult(
            status="not_available",
            operation=action.operation,
            summary=f"macOS computer-use package does not support {action.operation}.",
        )


def _target_app(action: ComputerUseAction) -> str | None:
    return _string_metadata(action, "target_app") or (
        action.target if action.operation in {"observe", "type_text"} else None
    )


def _string_metadata(action: ComputerUseAction, key: str) -> str | None:
    value = action.metadata.get(key)
    return value if isinstance(value, str) and value else None


def _bool_metadata(
    action: ComputerUseAction,
    key: str,
    *,
    default: bool = False,
) -> bool:
    value = action.metadata.get(key)
    return value if isinstance(value, bool) else default


def _tuple_metadata(
    action: ComputerUseAction,
    key: str,
    *,
    default: tuple[str, ...] = (),
) -> tuple[str, ...]:
    value = action.metadata.get(key)
    if not isinstance(value, list | tuple):
        return default
    values = tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    return values or default


def _int_metadata(
    action: ComputerUseAction,
    key: str,
    *,
    default: int,
) -> int:
    value = action.metadata.get(key)
    if isinstance(value, int):
        return value
    return default


def _float_metadata(action: ComputerUseAction, key: str) -> float | None:
    value = action.metadata.get(key)
    if isinstance(value, int | float):
        return float(value)
    return None


def _enum_value(value: Any) -> str:
    enum_value = getattr(value, "value", value)
    return enum_value if isinstance(enum_value, str) else str(enum_value)


def _to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "to_dict"):
        raw = value.to_dict()
        if isinstance(raw, dict):
            return raw
    if isinstance(value, dict):
        return value
    return {"value": str(value)}


def _readiness_diagnostics(
    readiness: dict[str, Any],
    client: MacOSComputerUseClientProtocol | None,
) -> dict[str, str]:
    diagnostics: dict[str, str] = {}
    raw_diagnostics = readiness.get("diagnostics")
    if isinstance(raw_diagnostics, dict):
        for key, value in raw_diagnostics.items():
            if isinstance(key, str) and isinstance(value, str) and value:
                diagnostics[key] = value[:500]
    diagnostics.setdefault("checkedByProcessPath", sys.executable)
    diagnostics["adapterProcessExecutable"] = sys.executable
    if sys.argv:
        diagnostics["adapterArgv0"] = sys.argv[0][:500]
    if client is not None:
        diagnostics["packageClientClass"] = (
            f"{client.__class__.__module__}.{client.__class__.__qualname__}"
        )[:500]
    return diagnostics


def _map_readiness_status(readiness_status: str) -> ComputerUseStatus:
    if readiness_status == "ready":
        return "ok"
    if readiness_status == "needs_manual_setup":
        return "needs_user"
    if readiness_status == "error":
        return "failed"
    return "not_available"


def _map_result_status(status: str) -> ComputerUseStatus:
    if status == "ok":
        return "ok"
    if status == "blocked":
        return "blocked"
    if status == "needs_user":
        return "needs_user"
    if status == "not_available":
        return "not_available"
    if status == "failed":
        return "failed"
    return "failed"


def _result_to_observation(
    action: ComputerUseAction,
    result: Any,
) -> ComputerUseObservation:
    status = _map_result_status(_enum_value(getattr(result, "status", "failed")))
    metadata = _to_dict(getattr(result, "metadata", {}))
    metadata["package_status"] = _enum_value(getattr(result, "status", "failed"))
    metadata["package_operation"] = _enum_value(
        getattr(result, "operation", action.operation)
    )
    snapshot_id = getattr(result, "snapshot_id", None)
    if isinstance(snapshot_id, str) and snapshot_id:
        metadata["snapshot_id"] = snapshot_id
    risk = getattr(result, "risk", None)
    if risk is not None:
        metadata["risk"] = _to_dict(risk)
    return ComputerUseObservation(
        action_id=action.event_id,
        success=status == "ok",
        operation=action.operation,
        status=status,
        summary=str(getattr(result, "summary", "macOS computer-use operation result.")),
        text_extract=getattr(result, "text_extract", None),
        metadata=metadata,
    )


@dataclass(frozen=True)
class _UnsupportedResult:
    status: ComputerUseStatus
    operation: str
    summary: str
    metadata: dict[str, Any] | None = None


__all__ = [
    "MacOSComputerUseBackend",
    "MacOSComputerUseBackendConfig",
    "MacOSComputerUseClientProtocol",
]
