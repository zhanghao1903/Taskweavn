"""Precision file read/search/write services for Product 1.1."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from taskweavn.core.workspace_layout import PROTECTED_WORKSPACE_METADATA_DIR_NAMES
from taskweavn.workspace_inspection.limits import WorkspaceInspectionLimits
from taskweavn.workspace_inspection.path_policy import (
    WorkspaceInspectionPathPolicy,
    WorkspacePathRef,
)
from taskweavn.workspace_inspection.precision_store import SqlitePrecisionFileOperationStore
from taskweavn.workspace_inspection.store import SqliteInspectionEvidenceStore


class PrecisionFileInputError(ValueError):
    """Raised when a precision file request is invalid."""


class PrecisionFileDriftError(PrecisionFileInputError):
    """Raised when expected content hash differs from current content."""


class WorkspaceContentHash(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    algorithm: Literal["sha256"] = "sha256"
    value: str

    @classmethod
    def from_bytes(cls, content: bytes) -> WorkspaceContentHash:
        return cls(value=hashlib.sha256(content).hexdigest())

    def to_contract(self) -> dict[str, str]:
        return {"algorithm": self.algorithm, "value": self.value}


class WorkspaceLineRange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.end_line < self.start_line:
            raise ValueError("end_line must be greater than or equal to start_line")

    def to_contract(self) -> dict[str, int]:
        return {"startLine": self.start_line, "endLine": self.end_line}


@dataclass(frozen=True)
class PrecisionFileService:
    """Bounded file operations with path policy, drift checks, and evidence."""

    workspace_root: Path
    workspace_id: str
    evidence_store: SqliteInspectionEvidenceStore
    operation_store: SqlitePrecisionFileOperationStore
    limits: WorkspaceInspectionLimits = WorkspaceInspectionLimits()

    @classmethod
    def build(
        cls,
        *,
        workspace_root: Path,
        workspace_id: str,
        inspection_db_path: Path,
        limits: WorkspaceInspectionLimits | None = None,
    ) -> PrecisionFileService:
        configured_limits = limits or WorkspaceInspectionLimits()
        return cls(
            workspace_root=workspace_root,
            workspace_id=workspace_id,
            evidence_store=SqliteInspectionEvidenceStore(
                inspection_db_path,
                limits=configured_limits,
            ),
            operation_store=SqlitePrecisionFileOperationStore(inspection_db_path),
            limits=configured_limits,
        )

    def read_range(
        self,
        *,
        path: str,
        start_line: int = 1,
        line_count: int | None = None,
    ) -> dict[str, Any]:
        path_ref = self._path_policy().resolve_required(path)
        text = self._read_text_file(path_ref)
        lines = _split_lines(text)
        bounded_line_count = self.limits.line_count_limit(line_count)
        if start_line < 1:
            raise PrecisionFileInputError("startLine must be greater than or equal to 1")
        end_line = start_line + bounded_line_count - 1
        selected = [
            _line_contract(
                line_number=index + 1,
                text=line,
                single_line_bytes=self.limits.single_line_bytes,
            )
            for index, line in enumerate(lines)
            if start_line <= index + 1 <= end_line
        ]
        full_bytes = text.encode("utf-8")
        range_bytes = "\n".join(line["text"] for line in selected).encode("utf-8")
        return {
            "schemaVersion": "plato.precision_file.read_range.v1",
            "workspaceId": self.workspace_id,
            "file": path_ref.to_contract(),
            "range": {
                "startLine": start_line,
                "endLine": min(end_line, max(len(lines), start_line)),
                "requestedLineCount": line_count,
                "returnedLineCount": len(selected),
                "truncated": (start_line + bounded_line_count - 1) < len(lines),
            },
            "lines": selected,
            "contentHash": WorkspaceContentHash.from_bytes(full_bytes).to_contract(),
            "rangeHash": WorkspaceContentHash.from_bytes(range_bytes).to_contract(),
            "warnings": [],
        }

    def search(
        self,
        *,
        query: str,
        mode: Literal["literal", "filename"] = "literal",
        case_sensitive: bool = False,
        include_globs: tuple[str, ...] = (),
        exclude_globs: tuple[str, ...] = (),
        max_files: int | None = None,
        max_matches: int | None = None,
    ) -> dict[str, Any]:
        if not query:
            raise PrecisionFileInputError("query is required")
        if mode not in {"literal", "filename"}:
            raise PrecisionFileInputError("unsupported search mode")
        file_limit = self.limits.search_file_limit(max_files)
        match_limit = self.limits.search_match_limit(max_matches)
        matches: list[dict[str, Any]] = []
        visited_files = 0
        truncated = False
        needle = query if case_sensitive else query.lower()
        for file_path in self._iter_search_files(
            include_globs=include_globs,
            exclude_globs=exclude_globs,
        ):
            if visited_files >= file_limit:
                truncated = True
                break
            visited_files += 1
            relative_path = _relative_path(self.workspace_root, file_path)
            path_ref = self._path_policy().resolve(relative_path)
            file_matches = (
                _filename_matches(path_ref, query=needle, case_sensitive=case_sensitive)
                if mode == "filename"
                else self._literal_matches(
                    path_ref,
                    query=needle,
                    case_sensitive=case_sensitive,
                    remaining=max(0, match_limit - len(matches)),
                )
            )
            matches.extend(file_matches)
            if len(matches) >= match_limit:
                matches = matches[:match_limit]
                truncated = True
                break
        return {
            "schemaVersion": "plato.precision_file.search.v1",
            "workspaceId": self.workspace_id,
            "query": query,
            "mode": mode,
            "caseSensitive": case_sensitive,
            "matches": matches,
            "summary": {
                "filesVisited": visited_files,
                "matchCount": len(matches),
                "truncated": truncated,
            },
            "warnings": (
                [_warning("workspace.search_truncated", "Workspace search was truncated.")]
                if truncated
                else []
            ),
        }

    def replace_range(
        self,
        *,
        operation_id: str,
        path: str,
        start_line: int,
        end_line: int,
        replacement_text: str,
        expected_content_hash: WorkspaceContentHash,
        reason: Literal["task_execution", "user_command", "recovery"] = "task_execution",
    ) -> dict[str, Any]:
        path_ref = self._path_policy().resolve_required(path)
        line_range = WorkspaceLineRange(start_line=start_line, end_line=end_line)
        request_hash = _request_hash(
            {
                "kind": "replace_range",
                "path": path_ref.relative_path,
                "range": line_range.to_contract(),
                "replacementText": replacement_text,
                "expectedContentHash": expected_content_hash.to_contract(),
                "reason": reason,
            }
        )
        replay = self.operation_store.reserve(
            operation_id=operation_id,
            request_hash=request_hash,
            kind="replace_range",
            workspace_id=self.workspace_id,
            path_label=path_ref.path_label,
        )
        if replay is not None:
            response = dict(replay.response)
            response["replayed"] = True
            return response
        try:
            response = self._replace_range_once(
                operation_id=operation_id,
                path_ref=path_ref,
                line_range=line_range,
                replacement_text=replacement_text,
                expected_content_hash=expected_content_hash,
                reason=reason,
            )
        except Exception as exc:
            self.operation_store.fail(operation_id=operation_id, message=str(exc))
            raise
        self.operation_store.complete(
            operation_id=operation_id,
            before_hash=response["beforeHash"]["value"],
            after_hash=response["afterHash"]["value"],
            evidence_id=response["evidenceRef"]["evidenceId"],
            response=response,
        )
        return response

    def append(
        self,
        *,
        operation_id: str,
        path: str,
        content: str,
        expected_content_hash: WorkspaceContentHash,
        ensure_trailing_newline: bool = True,
        reason: Literal["task_execution", "user_command", "recovery"] = "task_execution",
    ) -> dict[str, Any]:
        path_ref = self._path_policy().resolve_required(path)
        request_hash = _request_hash(
            {
                "kind": "append",
                "path": path_ref.relative_path,
                "content": content,
                "expectedContentHash": expected_content_hash.to_contract(),
                "ensureTrailingNewline": ensure_trailing_newline,
                "reason": reason,
            }
        )
        replay = self.operation_store.reserve(
            operation_id=operation_id,
            request_hash=request_hash,
            kind="append",
            workspace_id=self.workspace_id,
            path_label=path_ref.path_label,
        )
        if replay is not None:
            response = dict(replay.response)
            response["replayed"] = True
            return response
        try:
            response = self._append_once(
                operation_id=operation_id,
                path_ref=path_ref,
                content=content,
                expected_content_hash=expected_content_hash,
                ensure_trailing_newline=ensure_trailing_newline,
                reason=reason,
            )
        except Exception as exc:
            self.operation_store.fail(operation_id=operation_id, message=str(exc))
            raise
        self.operation_store.complete(
            operation_id=operation_id,
            before_hash=response["beforeHash"]["value"],
            after_hash=response["afterHash"]["value"],
            evidence_id=response["evidenceRef"]["evidenceId"],
            response=response,
        )
        return response

    def _replace_range_once(
        self,
        *,
        operation_id: str,
        path_ref: WorkspacePathRef,
        line_range: WorkspaceLineRange,
        replacement_text: str,
        expected_content_hash: WorkspaceContentHash,
        reason: str,
    ) -> dict[str, Any]:
        if (
            len(replacement_text.encode("utf-8"))
            > self.limits.precision_write_max_replacement_bytes
        ):
            raise PrecisionFileInputError("replacement text is too large")
        original_bytes = self._read_text_bytes(path_ref)
        before_hash = WorkspaceContentHash.from_bytes(original_bytes)
        _verify_expected_hash(before_hash, expected_content_hash)
        text = original_bytes.decode("utf-8")
        newline = _dominant_newline(text)
        lines = _split_lines(text)
        if line_range.end_line > len(lines):
            raise PrecisionFileInputError("line range exceeds file length")
        replacement_lines = _split_lines(_normalize_newlines(replacement_text, "\n"))
        new_lines = (
            lines[: line_range.start_line - 1]
            + replacement_lines
            + lines[line_range.end_line :]
        )
        new_text = _join_lines(new_lines, newline, ends_with_newline=text.endswith(("\n", "\r")))
        after_bytes = new_text.encode("utf-8")
        self._atomic_write(path_ref.resolved_path, after_bytes)
        after_hash = WorkspaceContentHash.from_bytes(after_bytes)
        changed_range = WorkspaceLineRange(
            start_line=line_range.start_line,
            end_line=max(line_range.start_line, line_range.start_line + len(replacement_lines) - 1),
        )
        return self._mutation_response(
            schema_version="plato.precision_file.replace_range.v1",
            operation_id=operation_id,
            path_ref=path_ref,
            changed_ranges=[changed_range],
            before_hash=before_hash,
            after_hash=after_hash,
            bytes_written=len(after_bytes),
            evidence_kind="line_replace_snapshot",
            reason=reason,
        )

    def _append_once(
        self,
        *,
        operation_id: str,
        path_ref: WorkspacePathRef,
        content: str,
        expected_content_hash: WorkspaceContentHash,
        ensure_trailing_newline: bool,
        reason: str,
    ) -> dict[str, Any]:
        if content == "":
            raise PrecisionFileInputError("append content is required")
        if len(content.encode("utf-8")) > self.limits.precision_write_max_append_bytes:
            raise PrecisionFileInputError("append content is too large")
        original_bytes = self._read_text_bytes(path_ref)
        before_hash = WorkspaceContentHash.from_bytes(original_bytes)
        _verify_expected_hash(before_hash, expected_content_hash)
        text = original_bytes.decode("utf-8")
        newline = _dominant_newline(text)
        needs_separator = (
            ensure_trailing_newline and text and not text.endswith(("\n", "\r"))
        )
        prefix = newline if needs_separator else ""
        normalized_content = _normalize_newlines(content, newline)
        appended = prefix + normalized_content
        new_text = text + appended
        after_bytes = new_text.encode("utf-8")
        self._atomic_write(path_ref.resolved_path, after_bytes)
        after_hash = WorkspaceContentHash.from_bytes(after_bytes)
        old_line_count = len(_split_lines(text))
        appended_line_count = max(1, len(_split_lines(normalized_content)))
        changed_range = WorkspaceLineRange(
            start_line=old_line_count + 1,
            end_line=old_line_count + appended_line_count,
        )
        return self._mutation_response(
            schema_version="plato.precision_file.append.v1",
            operation_id=operation_id,
            path_ref=path_ref,
            changed_ranges=[changed_range],
            before_hash=before_hash,
            after_hash=after_hash,
            bytes_written=len(after_bytes),
            evidence_kind="append_snapshot",
            reason=reason,
        )

    def _mutation_response(
        self,
        *,
        schema_version: str,
        operation_id: str,
        path_ref: WorkspacePathRef,
        changed_ranges: list[WorkspaceLineRange],
        before_hash: WorkspaceContentHash,
        after_hash: WorkspaceContentHash,
        bytes_written: int,
        evidence_kind: str,
        reason: str,
    ) -> dict[str, Any]:
        descriptor = {
            "kind": evidence_kind,
            "operationId": operation_id,
            "pathLabel": path_ref.path_label,
            "beforeHash": before_hash.to_contract(),
            "afterHash": after_hash.to_contract(),
            "changedLineRanges": [item.to_contract() for item in changed_ranges],
            "truncated": False,
        }
        payload = {
            "schemaVersion": schema_version,
            "workspaceId": self.workspace_id,
            "operationId": operation_id,
            "file": path_ref.to_contract(),
            "changedLineRanges": descriptor["changedLineRanges"],
            "beforeHash": before_hash.to_contract(),
            "afterHash": after_hash.to_contract(),
            "bytesWritten": bytes_written,
            "reason": reason,
        }
        evidence_ref = self.evidence_store.capture(
            workspace_id=self.workspace_id,
            kind=evidence_kind,
            source="precision_file_operation",
            payload=payload,
            descriptor=descriptor,
            path_label=path_ref.path_label,
        )
        return {
            **payload,
            "evidenceRef": evidence_ref,
            "replayed": False,
        }

    def _iter_search_files(
        self,
        *,
        include_globs: tuple[str, ...],
        exclude_globs: tuple[str, ...],
    ) -> list[Path]:
        root = self.workspace_root.expanduser().resolve()
        files: list[Path] = []
        for current_root, dirnames, filenames in os.walk(root):
            current = Path(current_root)
            dirnames[:] = [
                name
                for name in sorted(dirnames)
                if (
                    name not in PROTECTED_WORKSPACE_METADATA_DIR_NAMES
                    and _safe_resolve(
                        self._path_policy(),
                        _relative_path(root, current / name),
                    )
                    is not None
                )
            ]
            for filename in sorted(filenames):
                candidate = current / filename
                try:
                    relative_path = _relative_path(root, candidate)
                    self._path_policy().resolve(relative_path)
                except ValueError:
                    continue
                if include_globs and not any(
                    fnmatch.fnmatch(relative_path, pattern) for pattern in include_globs
                ):
                    continue
                if exclude_globs and any(
                    fnmatch.fnmatch(relative_path, pattern) for pattern in exclude_globs
                ):
                    continue
                if _is_probably_binary_or_large(
                    candidate,
                    max_bytes=self.limits.readable_text_file_bytes,
                ):
                    continue
                files.append(candidate)
        return files

    def _literal_matches(
        self,
        path_ref: WorkspacePathRef,
        *,
        query: str,
        case_sensitive: bool,
        remaining: int,
    ) -> list[dict[str, Any]]:
        if remaining == 0:
            return []
        try:
            text = self._read_text_file(path_ref)
        except PrecisionFileInputError:
            return []
        matches: list[dict[str, Any]] = []
        for line_number, line in enumerate(_split_lines(text), start=1):
            haystack = line if case_sensitive else line.lower()
            match_start = haystack.find(query)
            if match_start < 0:
                continue
            matches.append(
                {
                    "file": path_ref.to_contract(),
                    "lineNumber": line_number,
                    "preview": _bounded_preview(line),
                    "matchStart": match_start,
                    "matchEnd": match_start + len(query),
                }
            )
            if len(matches) >= remaining:
                break
        return matches

    def _read_text_file(self, path_ref: WorkspacePathRef) -> str:
        return self._read_text_bytes(path_ref).decode("utf-8")

    def _read_text_bytes(self, path_ref: WorkspacePathRef) -> bytes:
        target = path_ref.resolved_path
        if not target.exists():
            raise PrecisionFileInputError("file does not exist")
        if not target.is_file():
            raise PrecisionFileInputError("path is not a file")
        size = target.stat().st_size
        if size > self.limits.readable_text_file_bytes:
            raise PrecisionFileInputError("file is too large")
        raw = target.read_bytes()
        if _looks_binary(raw):
            raise PrecisionFileInputError("binary files are unsupported")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PrecisionFileInputError("file is not valid UTF-8") from exc
        return raw

    def _atomic_write(self, target: Path, content: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(content)
        tmp_path.replace(target)

    def _path_policy(self) -> WorkspaceInspectionPathPolicy:
        return WorkspaceInspectionPathPolicy(
            workspace_root=self.workspace_root,
            workspace_id=self.workspace_id,
        )


def _verify_expected_hash(
    actual: WorkspaceContentHash,
    expected: WorkspaceContentHash,
) -> None:
    if expected.algorithm != "sha256" or actual.value != expected.value:
        raise PrecisionFileDriftError("workspace.file_drift")


def _filename_matches(
    path_ref: WorkspacePathRef,
    *,
    query: str,
    case_sensitive: bool,
) -> list[dict[str, Any]]:
    haystack = path_ref.relative_path if case_sensitive else path_ref.relative_path.lower()
    if query not in haystack:
        return []
    start = haystack.find(query)
    return [
        {
            "file": path_ref.to_contract(),
            "lineNumber": None,
            "preview": path_ref.relative_path,
            "matchStart": start,
            "matchEnd": start + len(query),
        }
    ]


def _line_contract(
    *,
    line_number: int,
    text: str,
    single_line_bytes: int,
) -> dict[str, Any]:
    encoded = text.encode("utf-8")
    if len(encoded) <= single_line_bytes:
        return {"lineNumber": line_number, "text": text, "truncated": False}
    truncated = encoded[:single_line_bytes].decode(
        "utf-8",
        errors="ignore",
    )
    return {"lineNumber": line_number, "text": truncated, "truncated": True}


def _split_lines(text: str) -> list[str]:
    if text == "":
        return []
    return text.splitlines()


def _join_lines(lines: list[str], newline: str, *, ends_with_newline: bool) -> str:
    text = newline.join(lines)
    if ends_with_newline and text:
        text += newline
    return text


def _dominant_newline(text: str) -> str:
    crlf = text.count("\r\n")
    bare_lf = text.replace("\r\n", "").count("\n")
    bare_cr = text.replace("\r\n", "").count("\r")
    if crlf >= bare_lf and crlf >= bare_cr and crlf > 0:
        return "\r\n"
    if bare_cr > bare_lf:
        return "\r"
    return "\n"


def _normalize_newlines(text: str, newline: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)


def _request_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _relative_path(root: Path, target: Path) -> str:
    return target.resolve(strict=False).relative_to(root.resolve()).as_posix()


def _looks_binary(raw: bytes) -> bool:
    return b"\x00" in raw[:4096]


def _is_probably_binary_or_large(path: Path, *, max_bytes: int) -> bool:
    try:
        if path.stat().st_size > max_bytes:
            return True
        with path.open("rb") as handle:
            return _looks_binary(handle.read(4096))
    except OSError:
        return True


def _bounded_preview(line: str, *, limit: int = 240) -> str:
    return line if len(line) <= limit else line[:limit] + "..."


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _safe_resolve(
    policy: WorkspaceInspectionPathPolicy,
    relative_path: str,
) -> WorkspacePathRef | None:
    try:
        return policy.resolve(relative_path)
    except ValueError:
        return None
