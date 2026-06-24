"""Read-only runtime configuration registry."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from taskweavn.runtime_config.models import RuntimeConfigKey


class RuntimeConfigRegistryError(ValueError):
    """Raised when runtime configuration registry metadata is invalid."""


@dataclass
class RuntimeConfigRegistry:
    """In-memory registry of supported runtime configuration keys."""

    _keys: dict[str, RuntimeConfigKey] = field(default_factory=dict)

    def register(self, key: RuntimeConfigKey) -> None:
        if key.key in self._keys:
            raise RuntimeConfigRegistryError(f"duplicate runtime config key: {key.key}")
        self._keys[key.key] = key

    def get(self, key: str) -> RuntimeConfigKey:
        try:
            return self._keys[key]
        except KeyError as exc:
            raise RuntimeConfigRegistryError(f"unknown runtime config key: {key}") from exc

    def has(self, key: str) -> bool:
        return key in self._keys

    def all(self) -> tuple[RuntimeConfigKey, ...]:
        return tuple(self._keys[name] for name in sorted(self._keys))

    def domain(self, domain: str) -> tuple[RuntimeConfigKey, ...]:
        return tuple(key for key in self.all() if key.domain == domain)

    def register_many(self, keys: Iterable[RuntimeConfigKey]) -> None:
        for key in keys:
            self.register(key)

    def to_schema_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": "plato.runtime_config_schema.v1",
            "keys": [key.model_dump(mode="json", by_alias=True) for key in self.all()],
        }


__all__ = [
    "RuntimeConfigRegistry",
    "RuntimeConfigRegistryError",
]
