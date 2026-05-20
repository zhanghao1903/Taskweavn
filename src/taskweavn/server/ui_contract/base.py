"""Shared base model and serialization helpers for Plato UI contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    """Convert snake_case field names to lower camelCase aliases."""

    head, *tail = value.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


def utcnow() -> datetime:
    return datetime.now(UTC)


class UiContractModel(BaseModel):
    """Frozen transport-facing model with frontend-compatible JSON aliases."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
        validate_assignment=True,
    )

    def to_contract_dict(self) -> dict[str, Any]:
        """Return the stable JSON-ready contract shape."""

        return self.model_dump(mode="json")
