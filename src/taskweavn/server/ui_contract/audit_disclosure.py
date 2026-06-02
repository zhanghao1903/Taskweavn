"""Runtime-only Audit Page payload disclosure and sanitization policy."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from taskweavn.core.session import Session
from taskweavn.observability.models import LogArchiveManifest
from taskweavn.server.ui_contract.gateway_protocols import (
    AuditEventProvider,
    PayloadDisclosureResult,
)
from taskweavn.server.ui_contract.view_models import (
    AuditDisclosure,
    AuditRecord,
    EvidenceRef,
    SanitizedRawPayload,
)
from taskweavn.types.base import BaseAction, BaseEvent, BaseObservation

_AUDIT_PROJECTION_PARTIAL_REASON = (
    "Audit records are projected from Task state. Dedicated audit-agent, log, "
    "and raw event evidence aggregation is not connected yet."
)
_AUDIT_PAYLOAD_TEXT_LIMIT = 4096
_AUDIT_PAYLOAD_STRING_FIELD_LIMIT = 2048
_AUDIT_LOG_EXCERPT_LINE_LIMIT = 20
_SECRET_KEY_PATTERNS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "token",
        "authorization",
        "cookie",
        "set_cookie",
        "password",
        "passwd",
        "secret",
        "private_key",
        "ssh_key",
        "credential",
        "openai_api_key",
        "anthropic_api_key",
        "deepseek_api_key",
    }
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b("
    r"api[_-]?key|access[_-]?token|refresh[_-]?token|token|authorization|"
    r"cookie|password|passwd|secret|private[_-]?key|credential"
    r")\s*[:=]\s*([^\s,;]+)"
)
_SECRET_JSON_FIELD_RE = re.compile(
    r'(?i)("(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|'
    r'authorization|cookie|password|passwd|secret|private[_-]?key|credential)"'
    r'\s*:\s*)"[^"]*"'
)


class DefaultAuditPayloadDisclosureService:
    """Build sanitized Audit Page payloads on demand.

    The service is deliberately runtime-only: it reads source material, applies
    a conservative sanitizer, and returns the sanitized payload to the caller
    without writing it back to the event stream, logs, or any database.
    """

    def __init__(
        self,
        *,
        audit_event_provider: AuditEventProvider | None = None,
    ) -> None:
        self._audit_event_provider = audit_event_provider

    def build_record_payload(
        self,
        record: AuditRecord,
        *,
        session: Session,
        include_sanitized_payload: bool,
    ) -> PayloadDisclosureResult:
        evidence_ref = record.evidence_refs[0] if record.evidence_refs else None
        return self._build_payload(
            record,
            evidence_ref,
            session=session,
            include_sanitized_payload=include_sanitized_payload,
        )

    def build_evidence_payload(
        self,
        record: AuditRecord,
        evidence_ref: EvidenceRef,
        *,
        session: Session,
        include_sanitized_payload: bool,
    ) -> PayloadDisclosureResult:
        return self._build_payload(
            record,
            evidence_ref,
            session=session,
            include_sanitized_payload=include_sanitized_payload,
        )

    def _build_payload(
        self,
        record: AuditRecord,
        evidence_ref: EvidenceRef | None,
        *,
        session: Session,
        include_sanitized_payload: bool,
    ) -> PayloadDisclosureResult:
        if _is_provider_payload_record(record, evidence_ref):
            return _hidden_payload(
                "LLM/provider payload is hidden by the audit disclosure policy."
            )
        if record.flags.hidden or (evidence_ref is not None and evidence_ref.hidden):
            return _hidden_payload("Evidence is hidden.")
        if evidence_ref is None:
            return _no_payload(_record_partial_reason(record))

        source = _payload_source(record, evidence_ref)
        if source == "unsupported":
            return _no_payload(_record_partial_reason(record))
        if not include_sanitized_payload:
            return PayloadDisclosureResult(
                disclosure=AuditDisclosure(
                    raw_payload_available=True,
                    raw_payload_shown=False,
                    partial_reason=_pre_request_partial_reason(record, source),
                ),
                payload=None,
            )

        if source == "event":
            return self._event_payload(record, evidence_ref, session=session)
        if source == "config":
            return _config_manifest_payload(session)
        if source == "log":
            return _log_excerpt_payload(session, evidence_ref)
        return _no_payload(_record_partial_reason(record))

    def _event_payload(
        self,
        record: AuditRecord,
        evidence_ref: EvidenceRef,
        *,
        session: Session,
    ) -> PayloadDisclosureResult:
        if self._audit_event_provider is None:
            return _source_missing_payload("EventStream source is not connected.")
        event_id = _payload_event_id(record, evidence_ref)
        if event_id is None:
            return _source_missing_payload("EventStream event id could not be resolved.")
        try:
            events = self._audit_event_provider.list_for_session(
                session,
                task_node_id=record.task_node_id,
            )
            event = next((item for item in events if item.event_id == event_id), None)
        except Exception as exc:  # noqa: BLE001 - disclosure must degrade safely.
            return _source_missing_payload(
                f"EventStream payload could not be read: {type(exc).__name__}."
            )
        if event is None:
            return _source_missing_payload("EventStream event was not found.")
        return _sanitize_json_payload(
            _safe_event_payload(event, task_node_id=record.task_node_id),
            session=session,
            partial_reason=(
                "Observation payload was summarized for safe audit display."
                if isinstance(event, BaseObservation)
                else None
            ),
        )


def _hidden_payload(reason: str) -> PayloadDisclosureResult:
    return PayloadDisclosureResult(
        disclosure=AuditDisclosure(
            raw_payload_available=True,
            raw_payload_shown=False,
            hidden_reason=reason,
        ),
        payload=None,
    )


def _no_payload(partial_reason: str | None = None) -> PayloadDisclosureResult:
    return PayloadDisclosureResult(
        disclosure=AuditDisclosure(
            raw_payload_available=False,
            raw_payload_shown=False,
            partial_reason=partial_reason,
        ),
        payload=None,
    )


def _source_missing_payload(reason: str) -> PayloadDisclosureResult:
    return PayloadDisclosureResult(
        disclosure=AuditDisclosure(
            raw_payload_available=False,
            raw_payload_shown=False,
            partial_reason=reason,
        ),
        payload=None,
    )


def _record_partial_reason(record: AuditRecord) -> str | None:
    return _AUDIT_PROJECTION_PARTIAL_REASON if record.flags.partial else None


def _pre_request_partial_reason(record: AuditRecord, source: str) -> str | None:
    if source == "log":
        return "Only a bounded log excerpt can be disclosed."
    if record.flags.partial and source in {"config", "event"}:
        return _record_partial_reason(record)
    return None


def _is_provider_payload_record(
    record: AuditRecord,
    evidence_ref: EvidenceRef | None,
) -> bool:
    candidates = (
        record.source_label,
        record.title,
        record.summary,
        "" if evidence_ref is None else evidence_ref.label,
    )
    return any(
        token in candidate.lower()
        for candidate in candidates
        for token in ("llm", "provider", "openai", "anthropic", "deepseek", "openrouter")
    )


def _payload_source(record: AuditRecord, evidence_ref: EvidenceRef) -> str:
    if evidence_ref.kind in {"config_snapshot"}:
        return "config"
    if evidence_ref.kind in {"log_excerpt"}:
        return "log"
    if (
        record.source_label == "EventStream"
        or record.id.startswith(("record-event-", "record-audit-verdict-"))
    ) and evidence_ref.kind in {"action", "observation", "event", "audit_observation"}:
        return "event"
    return "unsupported"


def _payload_event_id(record: AuditRecord, evidence_ref: EvidenceRef) -> str | None:
    prefixes = (
        "evidence-event-observation-",
        "evidence-event-action-",
        "evidence-audit-verdict-",
        "evidence-event-",
        "record-event-observation-",
        "record-event-action-",
        "record-audit-verdict-",
        "record-event-",
    )
    for value in (evidence_ref.id, record.id):
        for prefix in prefixes:
            if value.startswith(prefix):
                return value.removeprefix(prefix)
    return record.action_id


def _safe_event_payload(
    event: BaseEvent,
    *,
    task_node_id: str | None,
) -> dict[str, object]:
    payload = event.to_dict()
    safe: dict[str, object] = {
        "source": "event_stream",
        "eventId": event.event_id,
        "eventKind": event.kind,
        "timestamp": event.timestamp.isoformat(),
        "taskNodeId": task_node_id,
    }
    if isinstance(event, BaseAction):
        safe["eventFamily"] = "action"
        safe["actionSource"] = event.source
        safe["baselineRisk"] = float(getattr(type(event), "baseline_risk", 0.0))
    elif isinstance(event, BaseObservation):
        safe["eventFamily"] = "observation"
        safe["actionId"] = event.action_id
        safe["success"] = event.success
    else:
        safe["eventFamily"] = "event"

    for key, value in payload.items():
        if key in {"event_id", "timestamp", "kind", "source", "action_id", "success"}:
            continue
        safe[key] = value
    return safe


def _config_manifest_payload(session: Session) -> PayloadDisclosureResult:
    manifest = _read_session_log_manifest(session)
    if manifest is None:
        return _source_missing_payload("Logging config manifest was not found.")
    payload: dict[str, object] = {
        "source": "log_archive_manifest",
        "sessionId": manifest.session_id,
        "createdAt": manifest.created_at.isoformat(),
        "configHash": manifest.config_hash,
        "activeConfigPath": manifest.active_config_path,
        "archiveRoot": "session-logs://",
        "files": manifest.files,
    }
    return _sanitize_json_payload(payload, session=session)


def _read_session_log_manifest(session: Session) -> LogArchiveManifest | None:
    path = session.logs_dir / "manifest.json"
    if not path.exists():
        return None
    try:
        return LogArchiveManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - invalid manifests should not break Audit Page.
        return None


def _log_excerpt_payload(session: Session, evidence_ref: EvidenceRef) -> PayloadDisclosureResult:
    path = _safe_log_path(session, evidence_ref.label)
    if path is None:
        return _source_missing_payload("Log evidence file was not found.")
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return _source_missing_payload(
            f"Log evidence file could not be read: {type(exc).__name__}."
        )

    lines = raw.splitlines()
    excerpt_lines = lines[:_AUDIT_LOG_EXCERPT_LINE_LIMIT]
    partial_reason = None
    redactions: list[str] = []
    if len(lines) > _AUDIT_LOG_EXCERPT_LINE_LIMIT:
        partial_reason = "Log payload was truncated for safe audit display."
        redactions.append("truncated:log-lines")
    body = "\n".join(excerpt_lines)
    body, text_redactions = _sanitize_text(body, session=session)
    redactions.extend(text_redactions)
    content = f"Log file: {path.name}\nShowing {len(excerpt_lines)} line(s).\n\n{body}"
    if len(content) > _AUDIT_PAYLOAD_TEXT_LIMIT:
        content = f"{content[:_AUDIT_PAYLOAD_TEXT_LIMIT]}\n[truncated]"
        partial_reason = "Log payload was truncated for safe audit display."
        redactions.append("truncated:log-content")

    return PayloadDisclosureResult(
        disclosure=AuditDisclosure(
            raw_payload_available=True,
            raw_payload_shown=True,
            redaction_reason=(
                "Sensitive log content was redacted." if redactions else None
            ),
            partial_reason=partial_reason,
        ),
        payload=SanitizedRawPayload(
            format="text",
            content=content or "Log file was empty.",
            redactions=_compact_redactions(redactions),
        ),
    )


def _safe_log_path(session: Session, label: str) -> Path | None:
    if "/" in label or "\\" in label:
        return None
    candidate = (session.logs_dir / label).resolve()
    try:
        candidate.relative_to(session.logs_dir.resolve())
    except ValueError:
        return None
    if not candidate.is_file() or candidate.name == "manifest.json":
        return None
    if candidate.suffix.lower() not in {".jsonl", ".log"}:
        return None
    return candidate


def _sanitize_json_payload(
    payload: object,
    *,
    session: Session,
    partial_reason: str | None = None,
) -> PayloadDisclosureResult:
    redactions: list[str] = []
    sanitized = _sanitize_value(payload, session=session, redactions=redactions)
    content = json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True)
    if len(content) > _AUDIT_PAYLOAD_TEXT_LIMIT:
        content = f"{content[:_AUDIT_PAYLOAD_TEXT_LIMIT]}\n[truncated]"
        partial_reason = partial_reason or "Payload was truncated for safe audit display."
        redactions.append("truncated:payload")
    return PayloadDisclosureResult(
        disclosure=AuditDisclosure(
            raw_payload_available=True,
            raw_payload_shown=True,
            redaction_reason=(
                "Sensitive fields were redacted." if redactions else None
            ),
            partial_reason=partial_reason,
        ),
        payload=SanitizedRawPayload(
            format="json",
            content=content or "{}",
            redactions=_compact_redactions(redactions),
        ),
    )


def _sanitize_value(
    value: Any,
    *,
    session: Session,
    redactions: list[str],
) -> object:
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_secret_key(key_text):
                sanitized[key_text] = "[redacted:secret]"
                redactions.append(f"secret:{key_text}")
                continue
            if isinstance(item, str) and key_text in {"content", "code"}:
                sanitized[key_text] = f"[redacted:{key_text}:{len(item)} chars]"
                redactions.append(f"field:{key_text}")
                continue
            sanitized[key_text] = _sanitize_value(
                item,
                session=session,
                redactions=redactions,
            )
        return sanitized
    if isinstance(value, list | tuple):
        return tuple(
            _sanitize_value(item, session=session, redactions=redactions)
            for item in value
        )
    if isinstance(value, str):
        text, text_redactions = _sanitize_text(value, session=session)
        redactions.extend(text_redactions)
        if len(text) > _AUDIT_PAYLOAD_STRING_FIELD_LIMIT:
            redactions.append("truncated:string-field")
            return f"{text[:_AUDIT_PAYLOAD_STRING_FIELD_LIMIT]}[truncated]"
        return text
    if isinstance(value, int | float | bool) or value is None:
        return value
    return str(value)


def _is_secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    return normalized in _SECRET_KEY_PATTERNS or any(
        token in normalized for token in ("api_key", "access_token", "secret", "password")
    )


def _sanitize_text(text: str, *, session: Session) -> tuple[str, tuple[str, ...]]:
    redactions: list[str] = []

    def replace_json_secret(match: re.Match[str]) -> str:
        redactions.append("secret:json-field")
        return f'{match.group(1)}"[redacted:secret]"'

    def replace_secret(match: re.Match[str]) -> str:
        redactions.append(f"secret:{match.group(1).lower()}")
        return f"{match.group(1)}=[redacted:secret]"

    sanitized = _SECRET_JSON_FIELD_RE.sub(replace_json_secret, text)
    sanitized = _SECRET_ASSIGNMENT_RE.sub(replace_secret, sanitized)
    sanitized, path_redactions = _normalize_paths(sanitized, session=session)
    redactions.extend(path_redactions)
    return sanitized, _compact_redactions(redactions)


def _normalize_paths(text: str, *, session: Session) -> tuple[str, tuple[str, ...]]:
    redactions: list[str] = []
    normalized = text
    for root, label in (
        (session.project_dir, "workspace://"),
        (session.workspace_root, "workspace-root://"),
        (session.logs_dir, "session-logs://"),
    ):
        try:
            root_text = str(root.resolve())
        except OSError:
            root_text = str(root)
        if root_text and root_text in normalized:
            replacement = f"{label.rstrip('/')}/"
            normalized = normalized.replace(root_text, replacement)
            redactions.append(f"path:{label.rstrip(':/')}")

    home_text = str(Path.home())
    if home_text and home_text in normalized:
        normalized = normalized.replace(home_text, "[redacted:path]")
        redactions.append("path:home")

    for temp_prefix in ("/private/var/", "/var/folders/", "/tmp/"):
        if temp_prefix in normalized:
            normalized = normalized.replace(temp_prefix, "[redacted:temp-path]/")
            redactions.append("path:temp")
    return normalized, _compact_redactions(redactions)


def _compact_redactions(redactions: Iterable[str]) -> tuple[str, ...]:
    compact: list[str] = []
    seen: set[str] = set()
    for item in redactions:
        if item in seen:
            continue
        seen.add(item)
        compact.append(item)
        if len(compact) == 20:
            break
    remaining = len(seen) - len(compact)
    if remaining > 0:
        compact.append(f"+{remaining} more")
    return tuple(compact)
