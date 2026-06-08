"""Read-only workspace context source for Collaborator authoring."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from taskweavn.core.workspace_layout import PROTECTED_WORKSPACE_METADATA_DIR_NAMES
from taskweavn.task.authoring_evidence import (
    AuthoringEvidenceOperation,
    AuthoringEvidencePolicyDecision,
    AuthoringEvidenceRecord,
    AuthoringEvidenceStore,
    AuthoringEvidenceToolName,
)
from taskweavn.task.collaborator_loop import (
    AUTHORING_READ_WORKSPACE_TOOL_NAME,
    AUTHORING_SEARCH_WORKSPACE_TOOL_NAME,
)
from taskweavn.tools.workspace import (
    PathOutsideWorkspaceError,
    PathProtectedWorkspaceError,
    Workspace,
)

DEFAULT_AUTHORING_GUIDANCE_GLOBS: tuple[str, ...] = (
    "README*",
    "AGENTS.md",
    "docs/plans/**",
    "docs/architecture/**",
    "docs/decisions/**",
    "docs/engineering/**",
)

_WORKSPACE_LABEL_PREFIX = "workspace://current"
_SEARCH_READ_BYTES_LIMIT = 128_000


class _FrozenWorkspaceContextModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class AuthoringReadWorkspaceRequest(_FrozenWorkspaceContextModel):
    paths: tuple[str, ...] = Field(min_length=1)
    purpose: str = Field(min_length=1)
    max_snippet_chars: int = Field(default=4000, ge=1, le=20_000)


class AuthoringReadWorkspaceFile(_FrozenWorkspaceContextModel):
    evidence_ref: str
    path_label: str
    content_snippet: str | None = Field(default=None, min_length=1)
    content_hash: str | None = Field(default=None, min_length=1)
    omitted_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_payload(self) -> AuthoringReadWorkspaceFile:
        if self.content_snippet is None and self.omitted_reason is None:
            raise ValueError("read file result requires content_snippet or omitted_reason")
        return self


class AuthoringReadWorkspaceObservation(_FrozenWorkspaceContextModel):
    evidence_refs: tuple[str, ...]
    files: tuple[AuthoringReadWorkspaceFile, ...]


class AuthoringSearchWorkspaceScope(_FrozenWorkspaceContextModel):
    path_globs: tuple[str, ...] = DEFAULT_AUTHORING_GUIDANCE_GLOBS
    selected_folders: tuple[str, ...] = ()


class AuthoringSearchWorkspaceRequest(_FrozenWorkspaceContextModel):
    query: str = Field(min_length=1)
    scope: AuthoringSearchWorkspaceScope = Field(
        default_factory=AuthoringSearchWorkspaceScope
    )
    max_results: int = Field(default=10, ge=1, le=50)
    max_snippet_chars: int = Field(default=500, ge=1, le=4000)
    purpose: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_query(self) -> AuthoringSearchWorkspaceRequest:
        if not self.query.strip():
            raise ValueError("query must not be blank")
        return self


class AuthoringSearchWorkspaceResult(_FrozenWorkspaceContextModel):
    evidence_ref: str
    path_label: str
    score: float | None = None
    match_snippet: str | None = Field(default=None, min_length=1)
    content_hash: str | None = Field(default=None, min_length=1)


class AuthoringSearchWorkspaceObservation(_FrozenWorkspaceContextModel):
    evidence_refs: tuple[str, ...]
    results: tuple[AuthoringSearchWorkspaceResult, ...]


@runtime_checkable
class CollaboratorWorkspaceContextSource(Protocol):
    """Authoring-scoped read/search source for workspace facts."""

    def read_workspace(
        self,
        *,
        session_id: str,
        loop_id: str,
        request: AuthoringReadWorkspaceRequest,
    ) -> AuthoringReadWorkspaceObservation: ...

    def search_workspace(
        self,
        *,
        session_id: str,
        loop_id: str,
        request: AuthoringSearchWorkspaceRequest,
    ) -> AuthoringSearchWorkspaceObservation: ...


class LocalCollaboratorWorkspaceContextSource:
    """Deterministic local filesystem implementation for authoring reads/search."""

    def __init__(
        self,
        *,
        workspace_root: str | Path,
        evidence_store: AuthoringEvidenceStore,
    ) -> None:
        self._workspace = Workspace(workspace_root)
        self._evidence_store = evidence_store

    def read_workspace(
        self,
        *,
        session_id: str,
        loop_id: str,
        request: AuthoringReadWorkspaceRequest,
    ) -> AuthoringReadWorkspaceObservation:
        files: list[AuthoringReadWorkspaceFile] = []
        for raw_path in request.paths:
            file_result = self._read_one(
                session_id=session_id,
                loop_id=loop_id,
                raw_path=raw_path,
                purpose=request.purpose,
                max_snippet_chars=request.max_snippet_chars,
            )
            files.append(file_result)
        return AuthoringReadWorkspaceObservation(
            evidence_refs=tuple(file.evidence_ref for file in files),
            files=tuple(files),
        )

    def search_workspace(
        self,
        *,
        session_id: str,
        loop_id: str,
        request: AuthoringSearchWorkspaceRequest,
    ) -> AuthoringSearchWorkspaceObservation:
        results: list[AuthoringSearchWorkspaceResult] = []
        for path in self._candidate_search_files(request.scope):
            if len(results) >= request.max_results:
                break
            match = self._search_one(
                path=path,
                query=request.query,
                max_snippet_chars=request.max_snippet_chars,
            )
            if match is None:
                continue
            path_label, score, snippet, content_hash = match
            record = self._put_evidence(
                session_id=session_id,
                loop_id=loop_id,
                operation="search_workspace",
                tool_name=AUTHORING_SEARCH_WORKSPACE_TOOL_NAME,
                purpose=request.purpose,
                path_label=path_label,
                content_hash=content_hash,
                snippet=snippet,
                policy_decision="allowed",
            )
            results.append(
                AuthoringSearchWorkspaceResult(
                    evidence_ref=record.evidence_id,
                    path_label=path_label,
                    score=score,
                    match_snippet=snippet,
                    content_hash=content_hash,
                )
            )
        return AuthoringSearchWorkspaceObservation(
            evidence_refs=tuple(result.evidence_ref for result in results),
            results=tuple(results),
        )

    def _read_one(
        self,
        *,
        session_id: str,
        loop_id: str,
        raw_path: str,
        purpose: str,
        max_snippet_chars: int,
    ) -> AuthoringReadWorkspaceFile:
        path_label = _requested_path_label(raw_path)
        try:
            target = _resolve_authoring_path(self._workspace, raw_path)
            path_label = _workspace_label(self._workspace, target)
            if not target.is_file():
                return self._omitted_read_result(
                    session_id=session_id,
                    loop_id=loop_id,
                    purpose=purpose,
                    path_label=path_label,
                    omitted_reason="path is not a file",
                    policy_decision="omitted",
                )
            raw_content = target.read_bytes()
            content = raw_content.decode("utf-8")
        except UnicodeDecodeError:
            return self._omitted_read_result(
                session_id=session_id,
                loop_id=loop_id,
                purpose=purpose,
                path_label=path_label,
                omitted_reason="file is not valid UTF-8 text",
                policy_decision="omitted",
            )
        except (PathOutsideWorkspaceError, PathProtectedWorkspaceError, ValueError) as exc:
            return self._omitted_read_result(
                session_id=session_id,
                loop_id=loop_id,
                purpose=purpose,
                path_label=path_label,
                omitted_reason=str(exc),
                policy_decision="denied",
            )

        snippet = content[:max_snippet_chars]
        content_hash = _sha256(raw_content)
        record = self._put_evidence(
            session_id=session_id,
            loop_id=loop_id,
            operation="read_workspace",
            tool_name=AUTHORING_READ_WORKSPACE_TOOL_NAME,
            purpose=purpose,
            path_label=path_label,
            content_hash=content_hash,
            snippet=snippet,
            policy_decision="allowed",
        )
        return AuthoringReadWorkspaceFile(
            evidence_ref=record.evidence_id,
            path_label=path_label,
            content_snippet=snippet,
            content_hash=content_hash,
        )

    def _omitted_read_result(
        self,
        *,
        session_id: str,
        loop_id: str,
        purpose: str,
        path_label: str,
        omitted_reason: str,
        policy_decision: AuthoringEvidencePolicyDecision,
    ) -> AuthoringReadWorkspaceFile:
        record = self._put_evidence(
            session_id=session_id,
            loop_id=loop_id,
            operation="read_workspace",
            tool_name=AUTHORING_READ_WORKSPACE_TOOL_NAME,
            purpose=purpose,
            path_label=path_label,
            omitted_reason=omitted_reason,
            policy_decision=policy_decision,
        )
        return AuthoringReadWorkspaceFile(
            evidence_ref=record.evidence_id,
            path_label=path_label,
            omitted_reason=omitted_reason,
        )

    def _candidate_search_files(
        self,
        scope: AuthoringSearchWorkspaceScope,
    ) -> tuple[Path, ...]:
        candidates: dict[str, Path] = {}
        globs = scope.path_globs or DEFAULT_AUTHORING_GUIDANCE_GLOBS
        for pattern in globs:
            if _is_full_workspace_glob(pattern):
                continue
            if _is_protected_glob(pattern):
                continue
            for expanded_pattern in _expanded_glob_patterns(pattern):
                for base in self._selected_search_bases(scope.selected_folders):
                    for path in base.glob(expanded_pattern):
                        if not path.is_file():
                            continue
                        if self._workspace.is_protected_path(path):
                            continue
                        candidates[str(path)] = path
        return tuple(
            sorted(
                candidates.values(),
                key=lambda path: path.relative_to(self._workspace.root).as_posix(),
            )
        )

    def _selected_search_bases(self, selected_folders: tuple[str, ...]) -> tuple[Path, ...]:
        if not selected_folders:
            return (self._workspace.root,)
        bases: list[Path] = []
        for folder in selected_folders:
            try:
                target = _resolve_authoring_path(self._workspace, folder)
            except (PathOutsideWorkspaceError, PathProtectedWorkspaceError, ValueError):
                continue
            if target.is_dir():
                bases.append(target)
        return tuple(bases) or (self._workspace.root,)

    def _search_one(
        self,
        *,
        path: Path,
        query: str,
        max_snippet_chars: int,
    ) -> tuple[str, float, str, str] | None:
        try:
            raw_content = path.read_bytes()
        except OSError:
            return None
        if len(raw_content) > _SEARCH_READ_BYTES_LIMIT:
            return None
        try:
            content = raw_content.decode("utf-8")
        except UnicodeDecodeError:
            return None

        query_text = query.strip().lower()
        path_label = _workspace_label(self._workspace, path)
        path_score = 0.0
        filename = path.name.lower()
        if query_text in filename:
            path_score += 50.0
        content_lower = content.lower()
        content_index = content_lower.find(query_text)
        if content_index >= 0:
            path_score += 100.0
            snippet = _snippet_around(
                content,
                content_index,
                max_snippet_chars,
                match_length=len(query_text),
            )
        else:
            token_score = 0.0
            first_index: int | None = None
            for token in _query_tokens(query_text):
                token_index = content_lower.find(token)
                if token_index >= 0:
                    token_score += 10.0
                    first_index = (
                        token_index
                        if first_index is None
                        else min(first_index, token_index)
                    )
            if token_score <= 0.0 and path_score <= 0.0:
                return None
            path_score += token_score
            snippet = _snippet_around(content, first_index or 0, max_snippet_chars)
        return (path_label, path_score, snippet, _sha256(raw_content))

    def _put_evidence(
        self,
        *,
        session_id: str,
        loop_id: str,
        operation: AuthoringEvidenceOperation,
        tool_name: AuthoringEvidenceToolName,
        purpose: str,
        path_label: str,
        policy_decision: AuthoringEvidencePolicyDecision,
        content_hash: str | None = None,
        snippet: str | None = None,
        omitted_reason: str | None = None,
    ) -> AuthoringEvidenceRecord:
        record = AuthoringEvidenceRecord(
            session_id=session_id,
            loop_id=loop_id,
            operation=operation,
            tool_name=tool_name,
            purpose=purpose,
            path_label=path_label,
            content_hash=content_hash,
            snippet=snippet,
            omitted_reason=omitted_reason,
            policy_decision=policy_decision,
        )
        return self._evidence_store.put(record)


def _resolve_authoring_path(workspace: Workspace, value: str) -> Path:
    path = _path_from_request_value(value)
    return workspace.resolve(path)


def _path_from_request_value(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("path must not be blank")
    if stripped.startswith(_WORKSPACE_LABEL_PREFIX):
        suffix = stripped[len(_WORKSPACE_LABEL_PREFIX) :]
        return suffix.lstrip("/") or "."
    if Path(stripped).is_absolute():
        raise ValueError("raw absolute paths are not accepted")
    return stripped


def _requested_path_label(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith(_WORKSPACE_LABEL_PREFIX):
        return stripped
    if not stripped:
        return f"{_WORKSPACE_LABEL_PREFIX}/<blank>"
    if Path(stripped).is_absolute():
        return f"{_WORKSPACE_LABEL_PREFIX}/<absolute-path-redacted>"
    if stripped.startswith("./"):
        stripped = stripped[2:]
    return f"{_WORKSPACE_LABEL_PREFIX}/{stripped}"


def _workspace_label(workspace: Workspace, path: Path) -> str:
    relative = path.resolve().relative_to(workspace.root).as_posix()
    return f"{_WORKSPACE_LABEL_PREFIX}/{relative}" if relative else _WORKSPACE_LABEL_PREFIX


def _sha256(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _query_tokens(query: str) -> tuple[str, ...]:
    return tuple(token for token in query.split() if token)


def _snippet_around(
    content: str,
    index: int,
    max_chars: int,
    *,
    match_length: int = 0,
) -> str:
    if len(content) <= max_chars:
        return content
    match_end = min(index + match_length, len(content))
    start = max(min(index - max_chars // 3, match_end - max_chars), 0)
    end = min(start + max_chars, len(content))
    if end < match_end:
        end = match_end
        start = max(end - max_chars, 0)
    return content[start:end]


def _is_full_workspace_glob(pattern: str) -> bool:
    normalized = pattern.strip().replace("\\", "/")
    return normalized in {"*", "**", "**/*", "./*", "./**", "./**/*"}


def _expanded_glob_patterns(pattern: str) -> tuple[str, ...]:
    normalized = pattern.strip()
    if normalized.endswith("/**"):
        return (normalized, f"{normalized}/*")
    return (normalized,)


def _is_protected_glob(pattern: str) -> bool:
    normalized = pattern.strip().replace("\\", "/")
    return any(
        normalized == name or normalized.startswith(f"{name}/")
        for name in PROTECTED_WORKSPACE_METADATA_DIR_NAMES
    )


__all__ = [
    "DEFAULT_AUTHORING_GUIDANCE_GLOBS",
    "AuthoringReadWorkspaceFile",
    "AuthoringReadWorkspaceObservation",
    "AuthoringReadWorkspaceRequest",
    "AuthoringSearchWorkspaceObservation",
    "AuthoringSearchWorkspaceRequest",
    "AuthoringSearchWorkspaceResult",
    "AuthoringSearchWorkspaceScope",
    "CollaboratorWorkspaceContextSource",
    "LocalCollaboratorWorkspaceContextSource",
]
