"""Controlled git CLI backed workspace inspection provider."""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from taskweavn.core.workspace_layout import PROTECTED_WORKSPACE_METADATA_DIR_NAMES
from taskweavn.workspace_inspection.limits import WorkspaceInspectionLimits
from taskweavn.workspace_inspection.path_policy import WorkspacePathRef


class GitInspectionProviderError(RuntimeError):
    """Raised when the controlled git provider cannot complete a read."""


@dataclass(frozen=True)
class ControlledGitCliInspectionProvider:
    """Read-only inspection provider using fixed git CLI invocations."""

    workspace_root: Path
    workspace_id: str
    limits: WorkspaceInspectionLimits = WorkspaceInspectionLimits()
    timeout_seconds: float = 5.0

    def status(self, *, max_files: int | None = None) -> dict[str, Any]:
        generated_at = _utcnow()
        root_status = self._repository_status(generated_at)
        if root_status is not None:
            return root_status

        status_limit = self.limits.status_limit(max_files)
        output = self._git_text(
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            ".",
        )
        branch = self._branch_name()
        head_sha = self._head_sha()
        files = tuple(_parse_status_files(output, self.workspace_id))
        visible_files = files[:status_limit]
        has_more = len(files) > status_limit
        staged_count = sum(1 for item in files if item["staged"])
        unstaged_count = sum(1 for item in files if item["unstaged"])
        untracked_count = sum(1 for item in files if item["changeKind"] == "untracked")
        warnings = []
        if has_more:
            warnings.append(
                _warning(
                    "workspace.inspection_truncated",
                    "Workspace status was truncated.",
                )
            )
        repository_status = "clean"
        if files:
            repository_status = "untracked_only" if untracked_count == len(files) else "dirty"
        return {
            "schemaVersion": "plato.workspace_inspection.git_status.v1",
            "workspaceId": self.workspace_id,
            "generatedAt": generated_at,
            "repository": {
                "status": repository_status,
                "branch": branch,
                "headSha": head_sha,
                "isDetachedHead": branch is None,
                "rootLabel": f"workspace://{self.workspace_id}",
            },
            "summary": {
                "changedFileCount": len(files),
                "stagedFileCount": staged_count,
                "unstagedFileCount": unstaged_count,
                "untrackedFileCount": untracked_count,
                "hasMore": has_more,
            },
            "files": list(visible_files),
            "warnings": warnings,
        }

    def diff(
        self,
        path_ref: WorkspacePathRef,
        *,
        base: str = "head",
        context_lines: int | None = None,
        max_bytes: int | None = None,
    ) -> dict[str, Any]:
        generated_at = _utcnow()
        root_status = self._repository_status(generated_at)
        if root_status is not None:
            return _unavailable_diff(
                self.workspace_id,
                generated_at,
                path_ref,
                unavailable_reason=(
                    "not_git"
                    if root_status["repository"]["status"] == "not_git"
                    else "provider_error"
                ),
                warnings=root_status["warnings"],
            )
        if base not in {"head", "index"}:
            raise ValueError("base must be 'head' or 'index'")
        context = self.limits.context_line_limit(context_lines)
        limit = self.limits.diff_payload_limit(max_bytes)
        args = ["diff", "--no-color", "--no-ext-diff", f"--unified={context}"]
        if base == "index":
            args.append("--cached")
        args.extend(("--", path_ref.relative_path))
        raw = self._git_bytes(*args)
        truncated = len(raw) > limit
        raw = raw[:limit]
        text = raw.decode("utf-8", errors="replace")
        if _looks_binary_diff(text):
            return _unavailable_diff(
                self.workspace_id,
                generated_at,
                path_ref,
                unavailable_reason="binary",
                binary=True,
            )
        if not text.strip():
            return _unavailable_diff(
                self.workspace_id,
                generated_at,
                path_ref,
                unavailable_reason="file_not_changed",
            )
        hunks = _parse_unified_diff_hunks(text)
        additions = sum(1 for hunk in hunks for line in hunk["lines"] if line["kind"] == "add")
        deletions = sum(
            1 for hunk in hunks for line in hunk["lines"] if line["kind"] == "delete"
        )
        warnings = []
        if truncated:
            warnings.append(
                _warning(
                    "workspace.inspection_truncated",
                    "Diff output was truncated.",
                    path_label=path_ref.path_label,
                )
            )
        return {
            "schemaVersion": "plato.workspace_inspection.diff.v1",
            "workspaceId": self.workspace_id,
            "generatedAt": generated_at,
            "file": {
                **path_ref.to_contract(),
                "changeKind": _status_kind_for_path(self.status()["files"], path_ref.relative_path),
                "binary": False,
            },
            "base": base,
            "isAvailable": True,
            "hunks": hunks,
            "stats": {
                "additions": additions,
                "deletions": deletions,
                "hunkCount": len(hunks),
                "truncated": truncated,
            },
            "contentHash": _content_hash(raw),
            "warnings": warnings,
        }

    def file_content(
        self,
        path_ref: WorkspacePathRef,
        *,
        start_line: int = 1,
        line_count: int | None = None,
    ) -> dict[str, Any]:
        generated_at = _utcnow()
        target = path_ref.resolved_path
        range_start = max(1, start_line)
        range_count = self.limits.line_count_limit(line_count)
        if not target.exists():
            return _unavailable_file(
                self.workspace_id,
                generated_at,
                path_ref,
                file_kind="missing",
                unavailable_reason="file_missing",
                exists=False,
            )
        if target.is_dir():
            return _unavailable_file(
                self.workspace_id,
                generated_at,
                path_ref,
                file_kind="directory",
                unavailable_reason="directory",
                exists=True,
            )
        size = target.stat().st_size
        if size > self.limits.readable_text_file_bytes:
            return _unavailable_file(
                self.workspace_id,
                generated_at,
                path_ref,
                file_kind="text",
                unavailable_reason="too_large",
                exists=True,
                size_bytes=size,
                warnings=(
                    _warning(
                        "workspace.file_too_large",
                        "File is too large for Product 1.1 P0 inspection.",
                        path_label=path_ref.path_label,
                    ),
                ),
            )
        data = target.read_bytes()
        if _looks_binary_bytes(data):
            return _unavailable_file(
                self.workspace_id,
                generated_at,
                path_ref,
                file_kind="binary",
                unavailable_reason="binary",
                exists=True,
                size_bytes=size,
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return _unavailable_file(
                self.workspace_id,
                generated_at,
                path_ref,
                file_kind="unsupported",
                unavailable_reason="unsupported_encoding",
                exists=True,
                size_bytes=size,
            )
        all_lines = text.splitlines()
        selected = all_lines[range_start - 1 : range_start - 1 + range_count]
        rendered_lines: list[dict[str, Any]] = []
        payload_bytes = 0
        truncated = range_start - 1 + range_count < len(all_lines)
        for offset, line in enumerate(selected):
            safe_line, line_truncated = _truncate_text_bytes(
                line,
                self.limits.single_line_bytes,
            )
            encoded_length = len(safe_line.encode("utf-8"))
            if payload_bytes + encoded_length > self.limits.file_text_payload_bytes:
                truncated = True
                break
            payload_bytes += encoded_length
            truncated = truncated or line_truncated
            rendered_lines.append(
                {
                    "lineNumber": range_start + offset,
                    "text": safe_line,
                }
            )
        end_line = (
            rendered_lines[-1]["lineNumber"] if rendered_lines else max(0, range_start - 1)
        )
        warnings = []
        if truncated:
            warnings.append(
                _warning(
                    "workspace.inspection_truncated",
                    "File content was truncated.",
                    path_label=path_ref.path_label,
                )
            )
        return {
            "schemaVersion": "plato.workspace_inspection.file_content.v1",
            "workspaceId": self.workspace_id,
            "generatedAt": generated_at,
            "file": {
                **path_ref.to_contract(),
                "exists": True,
                "fileKind": "text",
                "sizeBytes": size,
                "encoding": "utf-8",
            },
            "range": {
                "startLine": range_start,
                "endLine": end_line,
                "totalLines": len(all_lines),
                "truncated": truncated,
            },
            "content": {"lines": rendered_lines},
            "contentHash": _content_hash(data),
            "source": "live",
            "warnings": warnings,
        }

    def _repository_status(self, generated_at: str) -> dict[str, Any] | None:
        try:
            top_level = self._git_text("rev-parse", "--show-toplevel").strip()
        except GitInspectionProviderError:
            return {
                "schemaVersion": "plato.workspace_inspection.git_status.v1",
                "workspaceId": self.workspace_id,
                "generatedAt": generated_at,
                "repository": {
                    "status": "not_git",
                    "branch": None,
                    "headSha": None,
                    "isDetachedHead": False,
                    "rootLabel": f"workspace://{self.workspace_id}",
                },
                "summary": {
                    "changedFileCount": 0,
                    "stagedFileCount": 0,
                    "unstagedFileCount": 0,
                    "untrackedFileCount": 0,
                    "hasMore": False,
                },
                "files": [],
                "warnings": [
                    _warning(
                        "workspace.not_git",
                        "The selected workspace is not a git repository.",
                    )
                ],
            }
        workspace_root = self.workspace_root.expanduser().resolve()
        if Path(top_level).expanduser().resolve() != workspace_root:
            return {
                "schemaVersion": "plato.workspace_inspection.git_status.v1",
                "workspaceId": self.workspace_id,
                "generatedAt": generated_at,
                "repository": {
                    "status": "unavailable",
                    "branch": None,
                    "headSha": None,
                    "isDetachedHead": False,
                    "rootLabel": f"workspace://{self.workspace_id}",
                },
                "summary": {
                    "changedFileCount": 0,
                    "stagedFileCount": 0,
                    "unstagedFileCount": 0,
                    "untrackedFileCount": 0,
                    "hasMore": False,
                },
                "files": [],
                "warnings": [
                    _warning(
                        "workspace.provider_partial",
                        "Git root differs from the selected workspace root.",
                    )
                ],
            }
        return None

    def _branch_name(self) -> str | None:
        try:
            branch = self._git_text("branch", "--show-current").strip()
        except GitInspectionProviderError:
            return None
        return branch or None

    def _head_sha(self) -> str | None:
        try:
            return self._git_text("rev-parse", "--verify", "HEAD").strip() or None
        except GitInspectionProviderError:
            return None

    def _git_text(self, *args: str) -> str:
        return self._git_bytes(*args).decode("utf-8", errors="replace")

    def _git_bytes(self, *args: str) -> bytes:
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=self.workspace_root,
                check=False,
                capture_output=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitInspectionProviderError(type(exc).__name__) from exc
        if completed.returncode != 0:
            raise GitInspectionProviderError("git command failed")
        return completed.stdout


def _parse_status_files(output: str, workspace_id: str) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        x_status = line[0]
        y_status = line[1]
        raw_path = line[3:]
        old_relative_path = None
        if " -> " in raw_path:
            old_relative_path, raw_path = raw_path.split(" -> ", 1)
        relative_path = _unquote_git_path(raw_path)
        if relative_path.split("/", 1)[0] in PROTECTED_WORKSPACE_METADATA_DIR_NAMES:
            continue
        path_label = f"workspace://{workspace_id}/{relative_path}"
        staged = x_status not in (" ", "?")
        unstaged = y_status not in (" ", "?") or x_status == "?"
        item: dict[str, Any] = {
            "relativePath": relative_path,
            "pathLabel": path_label,
            "changeKind": _change_kind(x_status, y_status),
            "staged": staged,
            "unstaged": unstaged,
            "binary": None,
            "relatedTaskRefs": [],
        }
        if old_relative_path:
            old_path = _unquote_git_path(old_relative_path)
            item["oldRelativePath"] = old_path
            item["oldPathLabel"] = f"workspace://{workspace_id}/{old_path}"
        files.append(item)
    return files


def _change_kind(x_status: str, y_status: str) -> str:
    if x_status == "?" and y_status == "?":
        return "untracked"
    status = x_status if x_status != " " else y_status
    return {
        "A": "added",
        "M": "modified",
        "D": "deleted",
        "R": "renamed",
        "C": "copied",
        "T": "type_changed",
    }.get(status, "unknown")


def _unquote_git_path(path: str) -> str:
    if len(path) >= 2 and path[0] == '"' and path[-1] == '"':
        try:
            return bytes(path[1:-1], "utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            return path[1:-1]
    return path


_HUNK_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_lines>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_lines>\d+))? @@(?P<header>.*)$"
)


def _parse_unified_diff_hunks(text: str) -> list[dict[str, Any]]:
    hunks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    old_line = 0
    new_line = 0
    for raw_line in text.splitlines():
        match = _HUNK_RE.match(raw_line)
        if match:
            old_line = int(match.group("old_start"))
            new_line = int(match.group("new_start"))
            current = {
                "hunkId": f"hunk-{len(hunks) + 1}",
                "oldStart": old_line,
                "oldLines": int(match.group("old_lines") or "1"),
                "newStart": new_line,
                "newLines": int(match.group("new_lines") or "1"),
                "header": match.group("header").strip(),
                "lines": [],
            }
            hunks.append(current)
            continue
        if current is None:
            continue
        if raw_line.startswith("\\"):
            continue
        marker = raw_line[:1]
        text_value = raw_line[1:] if marker in {" ", "+", "-"} else raw_line
        if marker == "+":
            current["lines"].append(
                {
                    "kind": "add",
                    "oldLine": None,
                    "newLine": new_line,
                    "text": text_value,
                }
            )
            new_line += 1
        elif marker == "-":
            current["lines"].append(
                {
                    "kind": "delete",
                    "oldLine": old_line,
                    "newLine": None,
                    "text": text_value,
                }
            )
            old_line += 1
        else:
            current["lines"].append(
                {
                    "kind": "context",
                    "oldLine": old_line,
                    "newLine": new_line,
                    "text": text_value,
                }
            )
            old_line += 1
            new_line += 1
    return hunks


def _status_kind_for_path(files: list[dict[str, Any]], relative_path: str) -> str:
    for item in files:
        if item["relativePath"] == relative_path:
            return str(item["changeKind"])
    return "unknown"


def _looks_binary_diff(text: str) -> bool:
    return text.startswith("Binary files ") or "\nBinary files " in text


def _looks_binary_bytes(data: bytes) -> bool:
    return b"\0" in data[:4096]


def _truncate_text_bytes(value: str, limit: int) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value, False
    return encoded[:limit].decode("utf-8", errors="ignore"), True


def _content_hash(data: bytes) -> dict[str, str]:
    return {
        "algorithm": "sha256",
        "value": hashlib.sha256(data).hexdigest(),
    }


def _warning(code: str, message: str, *, path_label: str | None = None) -> dict[str, str]:
    warning = {"code": code, "message": message}
    if path_label is not None:
        warning["pathLabel"] = path_label
    return warning


def _unavailable_diff(
    workspace_id: str,
    generated_at: str,
    path_ref: WorkspacePathRef,
    *,
    unavailable_reason: str,
    binary: bool = False,
    warnings: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": "plato.workspace_inspection.diff.v1",
        "workspaceId": workspace_id,
        "generatedAt": generated_at,
        "file": {
            **path_ref.to_contract(),
            "changeKind": "unknown",
            "binary": binary,
        },
        "base": "head",
        "isAvailable": False,
        "unavailableReason": unavailable_reason,
        "hunks": [],
        "stats": {
            "additions": 0,
            "deletions": 0,
            "hunkCount": 0,
            "truncated": False,
        },
        "warnings": warnings or [],
    }


def _unavailable_file(
    workspace_id: str,
    generated_at: str,
    path_ref: WorkspacePathRef,
    *,
    file_kind: str,
    unavailable_reason: str,
    exists: bool,
    size_bytes: int | None = None,
    warnings: tuple[dict[str, str], ...] = (),
) -> dict[str, Any]:
    file_payload: dict[str, Any] = {
        **path_ref.to_contract(),
        "exists": exists,
        "fileKind": file_kind,
    }
    if size_bytes is not None:
        file_payload["sizeBytes"] = size_bytes
    return {
        "schemaVersion": "plato.workspace_inspection.file_content.v1",
        "workspaceId": workspace_id,
        "generatedAt": generated_at,
        "file": file_payload,
        "range": {
            "startLine": 1,
            "endLine": 0,
            "totalLines": None,
            "truncated": False,
        },
        "content": {"lines": []},
        "source": "live",
        "unavailableReason": unavailable_reason,
        "warnings": list(warnings),
    }


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
