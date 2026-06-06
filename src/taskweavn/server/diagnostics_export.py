"""Sidecar diagnostic bundle export gateway."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from taskweavn.core import WorkspaceLayout
from taskweavn.diagnostics import (
    DiagnosticBundleError,
    DiagnosticBundleExporter,
    DiagnosticExportOptions,
    DiagnosticExportResult,
    normalize_workspace_path,
)

DIAGNOSTIC_EXPORT_SCHEMA_VERSION = "plato.diagnostics_export.v1"


class DiagnosticExportSessionNotFound(LookupError):
    """Raised when a requested session cannot be exported."""


class DiagnosticExportFailure(RuntimeError):
    """Raised when diagnostic export fails after session lookup."""


@dataclass(frozen=True)
class DefaultDiagnosticExportGateway:
    """Export one redacted diagnostic bundle through the local sidecar."""

    workspace_root: Path
    output_dir: Path | None = None
    create_zip: bool = True

    def export_session(self, session_id: str) -> dict[str, Any]:
        workspace_root = self.workspace_root.expanduser().resolve()
        output_dir = self.output_dir
        if output_dir is None:
            output_dir = WorkspaceLayout(workspace_root).meta_dir / "diagnostics"

        try:
            result = DiagnosticBundleExporter(
                DiagnosticExportOptions(
                    workspace_root=workspace_root,
                    session_id=session_id,
                    output_dir=output_dir,
                    create_zip=self.create_zip,
                )
            ).export()
        except DiagnosticBundleError as exc:
            if str(exc).startswith("session not found:"):
                raise DiagnosticExportSessionNotFound(str(exc)) from None
            raise DiagnosticExportFailure("diagnostic bundle export failed") from exc

        return _export_descriptor(result, workspace_root=workspace_root)


def _export_descriptor(
    result: DiagnosticExportResult,
    *,
    workspace_root: Path,
) -> dict[str, Any]:
    manifest = result.manifest.model_dump(mode="json", by_alias=True)
    bundle_dir = result.bundle_dir
    zip_path = result.zip_path
    manifest_path = bundle_dir / "manifest.json"
    sections = [
        {
            "name": section["name"],
            "status": section["status"],
            "warnings": section["warnings"],
        }
        for section in manifest["sections"]
    ]
    return {
        "schemaVersion": DIAGNOSTIC_EXPORT_SCHEMA_VERSION,
        "bundleId": result.bundle_id,
        "bundleDir": str(bundle_dir),
        "bundleDirLabel": normalize_workspace_path(
            bundle_dir,
            workspace_root=workspace_root,
        ),
        "zipPath": None if zip_path is None else str(zip_path),
        "zipPathLabel": (
            None
            if zip_path is None
            else normalize_workspace_path(zip_path, workspace_root=workspace_root)
        ),
        "manifestPath": str(manifest_path),
        "manifestPathLabel": normalize_workspace_path(
            manifest_path,
            workspace_root=workspace_root,
        ),
        "createdAt": manifest["createdAt"],
        "redactionProfile": manifest["redactionProfile"],
        "includedSections": manifest["includedSections"],
        "sections": sections,
        "warnings": manifest["warnings"],
        "fileCount": len(manifest["files"]),
    }


__all__ = [
    "DIAGNOSTIC_EXPORT_SCHEMA_VERSION",
    "DefaultDiagnosticExportGateway",
    "DiagnosticExportFailure",
    "DiagnosticExportSessionNotFound",
]
