"""Runtime assembly helpers for optional computer-use backends."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from taskweavn.tools import (
    ComputerUseBackend,
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
    if normalized != "macos":
        raise ValueError(
            "unsupported computer-use backend "
            f"{backend_name!r}; valid values: disabled, macos"
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


__all__ = [
    "ComputerUseRuntimeSelection",
    "build_computer_use_runtime",
    "parse_computer_use_allowed_apps",
]
