"""Settings readiness projection for optional computer-use backends."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from taskweavn.tools import ComputerUseBackend
from taskweavn.types import ComputerUseAction, ComputerUseObservation

_WARNING_CODE = "computer_use.not_ready"
_RECOVERY_ACTIONS = ("open_settings", "export_diagnostics")
_SAFE_METADATA_KEYS = (
    "diagnostics",
    "failure_kind",
    "helper_status",
    "phase",
    "provider",
    "setup_hint",
)
_SENSITIVE_KEY_PARTS = ("api_key", "authorization", "password", "secret", "token")


class SettingsReadinessSource(Protocol):
    """Readiness source shape used by the local Settings HTTP route."""

    def get_readiness(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ComputerUseSettingsReadinessGateway:
    """Decorate Settings readiness with computer-use capability status."""

    inner: SettingsReadinessSource
    enabled: bool
    backend_name: str
    allowed_apps: tuple[str, ...] = ()
    backend: ComputerUseBackend | None = None

    def get_readiness(self) -> dict[str, Any]:
        return self._decorate(self.inner.get_readiness())

    def recheck_readiness(self) -> dict[str, Any]:
        recheck = getattr(self.inner, "recheck_readiness", None)
        base = recheck() if callable(recheck) else self.inner.get_readiness()
        return self._decorate(base)

    def _decorate(self, base: dict[str, Any]) -> dict[str, Any]:
        report = dict(base)
        computer_use = build_computer_use_settings_readiness(
            enabled=self.enabled,
            backend_name=self.backend_name,
            allowed_apps=self.allowed_apps,
            backend=self.backend,
        )
        report["computerUse"] = computer_use
        if self.enabled and not computer_use["ready"]:
            warnings = [*list(report.get("warnings") or ())]
            if not any(warning.get("code") == _WARNING_CODE for warning in warnings):
                warnings.append(_computer_use_warning(computer_use))
            report["warnings"] = warnings
            if report.get("status") == "ready":
                report["status"] = "degraded"
        return report


def build_computer_use_settings_readiness(
    *,
    enabled: bool,
    backend_name: str,
    allowed_apps: tuple[str, ...] = (),
    backend: ComputerUseBackend | None = None,
) -> dict[str, Any]:
    """Return a frontend-safe computer-use readiness section."""

    normalized_backend = backend_name.strip().lower() or "disabled"
    base: dict[str, Any] = {
        "enabled": enabled,
        "backend": normalized_backend,
        "allowedApps": list(allowed_apps),
        "ready": False,
        "configured": enabled and normalized_backend != "disabled" and backend is not None,
        "status": "disabled" if not enabled else "not_available",
        "summary": (
            "Computer-use is disabled."
            if not enabled
            else "Computer-use backend is not available."
        ),
        "recoveryActions": [] if not enabled else list(_RECOVERY_ACTIONS),
    }
    if not enabled:
        return base
    if backend is None:
        base["summary"] = (
            "Computer-use is enabled, but no backend is wired for this runtime."
        )
        return base

    try:
        observation = backend.execute(
            ComputerUseAction(
                operation="readiness",
                instruction="Check local computer-use readiness.",
                timeout_seconds=5.0,
            )
        )
    except Exception as exc:  # noqa: BLE001 - readiness must not break Settings.
        base["status"] = "failed"
        base["summary"] = f"Computer-use readiness check failed: {type(exc).__name__}"
        base["failureKind"] = "readiness_exception"
        return base

    return _readiness_from_observation(base, observation)


def _readiness_from_observation(
    base: dict[str, Any],
    observation: ComputerUseObservation,
) -> dict[str, Any]:
    metadata = observation.metadata
    helper_status = _string(metadata.get("helper_status"))
    failure_kind = _string(metadata.get("failure_kind"))
    setup_hint = _string(metadata.get("setup_hint"))
    helper_identity = _safe_helper_identity(metadata.get("helper"))

    base["operationStatus"] = observation.status
    base["ready"] = observation.success and observation.status == "ok"
    base["status"] = "ready" if base["ready"] else helper_status or observation.status
    base["summary"] = observation.summary
    if helper_status:
        base["helperStatus"] = helper_status
    if failure_kind:
        base["failureKind"] = failure_kind
    if setup_hint:
        base["setupHint"] = setup_hint
    if helper_identity:
        base["helper"] = helper_identity
    diagnostics = _safe_metadata(metadata)
    if diagnostics:
        base["diagnostics"] = diagnostics
    if base["ready"]:
        base["recoveryActions"] = []
    return base


def _computer_use_warning(computer_use: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "code": _WARNING_CODE,
        "severity": "warning",
        "message": str(computer_use.get("summary") or "Computer-use is not ready."),
        "recoveryActions": list(_RECOVERY_ACTIONS),
        "envVars": (),
    }


def _safe_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key in _SAFE_METADATA_KEYS:
        if key in metadata:
            safe[key] = _safe_value(metadata[key])
    return safe


def _safe_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, Mapping):
        return {
            str(key)[:80]: _safe_value(nested)
            for key, nested in list(value.items())[:20]
            if not _is_sensitive_key(str(key))
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in list(value)[:20]]
    return str(value)[:500]


def _safe_helper_identity(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    safe: dict[str, str] = {}
    for key in ("bundleId", "version", "apiVersion", "path", "signingMode"):
        raw = value.get(key)
        if isinstance(raw, str) and raw:
            safe[key] = raw[:500]
    return safe


def _string(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


__all__ = [
    "ComputerUseSettingsReadinessGateway",
    "build_computer_use_settings_readiness",
]
