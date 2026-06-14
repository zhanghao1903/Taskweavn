"""Read-only diagnostic support descriptors for inquiry answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import quote

DiagnosticDisclosure = Literal["public", "partial", "hidden"]


@dataclass(frozen=True)
class DiagnosticSupportDescriptor:
    """Renderer-safe diagnostic support summary.

    This descriptor advertises accepted diagnostic support surfaces. It does not
    export a bundle or read bundle files.
    """

    ref_id: str
    label: str
    summary: str
    disclosure: DiagnosticDisclosure = "partial"
    truncated: bool = False


class DiagnosticSupportContextProvider(Protocol):
    def describe(
        self,
        *,
        session_id: str,
        workspace_id: str | None,
        diagnostic_id: str | None,
    ) -> DiagnosticSupportDescriptor | None: ...


@dataclass(frozen=True)
class DefaultDiagnosticSupportContextProvider:
    """Describe Product 1.1 diagnostic bundle support without side effects."""

    def describe(
        self,
        *,
        session_id: str,
        workspace_id: str | None,
        diagnostic_id: str | None,
    ) -> DiagnosticSupportDescriptor | None:
        normalized = _normalize_diagnostic_id(diagnostic_id)
        if normalized not in {None, "bundle_export", "diagnostic_bundle", "support"}:
            return None
        export_path = (
            f"/api/v1/sessions/{quote(session_id, safe='')}/diagnostics/export"
        )
        workspace_label = (
            f"workspace {workspace_id}" if workspace_id is not None else "current workspace"
        )
        return DiagnosticSupportDescriptor(
            ref_id="diagnostic:bundle_export",
            label="Diagnostic bundle export",
            summary=(
                "Redacted diagnostic bundle export is available for this session "
                f"in {workspace_label}. Use the Export diagnostics action "
                f"({export_path}) to create a support bundle. The support "
                "descriptor uses safe workspace labels and does not include raw "
                "provider payloads, prompts, SQLite rows, secrets, or absolute "
                "workspace paths."
            ),
        )


def _normalize_diagnostic_id(diagnostic_id: str | None) -> str | None:
    if diagnostic_id is None:
        return None
    normalized = diagnostic_id.removeprefix("diagnostic:")
    return normalized or None


__all__ = [
    "DefaultDiagnosticSupportContextProvider",
    "DiagnosticSupportContextProvider",
    "DiagnosticSupportDescriptor",
]
