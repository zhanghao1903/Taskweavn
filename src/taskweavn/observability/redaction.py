"""Payload redaction helpers for structured logs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

DEFAULT_REDACT_KEYS = (
    "api_key",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
)


def redact_payload(value: Any) -> Any:
    """Recursively redact common secret-looking fields."""
    if isinstance(value, BaseModel):
        return redact_payload(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if _should_redact(key_str):
                redacted[key_str] = "<redacted>"
            else:
                redacted[key_str] = redact_payload(item)
        return redacted
    if isinstance(value, str):
        return value
    if isinstance(value, Sequence):
        return [redact_payload(item) for item in value]
    return value


def _should_redact(key: str) -> bool:
    normalized = key.lower()
    return any(marker in normalized for marker in DEFAULT_REDACT_KEYS)


__all__ = ["DEFAULT_REDACT_KEYS", "redact_payload"]
