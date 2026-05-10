"""Auto-registries for Action and Observation subclasses.

Every concrete subclass of :class:`BaseAction` / :class:`BaseObservation`
registers itself by ``kind`` (defaulting to its class name) so events can be
serialized to JSON and deserialized back to the right type — essential for
EventStream replay, cross-process Runtime, and ThoughtStore retrieval.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from taskweavn.types.base import BaseAction, BaseEvent, BaseObservation


class _Registry[E: "BaseEvent"]:
    """Map from ``kind`` string to event subclass.

    One instance per event family (Action, Observation). Subclasses opt in by
    calling :meth:`register` from their ``__init_subclass__`` hook.
    """

    def __init__(self, family: str) -> None:
        self._family = family
        self._by_kind: dict[str, type[E]] = {}

    def register(self, cls: type[E], kind: str | None = None) -> str:
        resolved = kind or cls.__name__
        existing = self._by_kind.get(resolved)
        if existing is not None and existing is not cls:
            raise ValueError(
                f"{self._family} kind {resolved!r} is already registered to "
                f"{existing.__module__}.{existing.__name__}; cannot re-register "
                f"{cls.__module__}.{cls.__name__}."
            )
        self._by_kind[resolved] = cls
        return resolved

    def get(self, kind: str) -> type[E]:
        try:
            return self._by_kind[kind]
        except KeyError as exc:
            raise KeyError(f"Unknown {self._family} kind: {kind!r}") from exc

    def all_kinds(self) -> list[str]:
        return sorted(self._by_kind)

    def deserialize(self, data: dict[str, Any]) -> E:
        if "kind" not in data:
            raise ValueError(f"{self._family} payload missing 'kind' field: {data!r}")
        payload = dict(data)
        kind = payload.pop("kind")
        cls = self.get(kind)
        return cls.model_validate(payload)


ActionRegistry: _Registry[BaseAction] = _Registry("Action")
ObservationRegistry: _Registry[BaseObservation] = _Registry("Observation")
