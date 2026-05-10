"""Configuration for the thought-storage subsystem (Phase 2.4).

The loop always holds *some* :class:`ThoughtStore`; whether it actually
persists anything is decided here. Three knobs:

* ``enabled``   — master switch. When False, the loop gets
  :class:`NullThoughtStore` regardless of ``backend`` / ``db_path``.
* ``backend``   — ``"null"`` | ``"sqlite"``. ``"null"`` is also what an
  ``enabled=False`` config builds; making them separate lets callers ask
  "did the user opt into persistence?" without inspecting the resulting
  store.
* ``phases``    — optional allow-list of phase names. ``None`` means "store
  everything"; a tuple narrows persistence to specific lifecycle phases
  (e.g. ``("plan", "reflect")``) without altering loop behavior.
* ``db_path``   — required when ``backend == "sqlite"``.

The :func:`build_store` factory turns a config into a ready-to-use store
and is the only place callers should construct stores from config.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from taskweavn.memory.sqlite_thought_store import SqliteThoughtStore
from taskweavn.memory.thought_store import NullThoughtStore, ThoughtStore

ThoughtBackend = Literal["null", "sqlite"]


class ThoughtConfigError(ValueError):
    """Raised when a ThoughtConfig describes an unbuildable combination."""


@dataclass(frozen=True)
class ThoughtConfig:
    """Per-run configuration for thought persistence."""

    enabled: bool = False
    backend: ThoughtBackend = "null"
    db_path: Path | None = None
    phases: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.backend not in ("null", "sqlite"):
            raise ThoughtConfigError(f"unknown backend {self.backend!r}")
        if self.enabled and self.backend == "sqlite" and self.db_path is None:
            raise ThoughtConfigError(
                "backend='sqlite' requires db_path to be set"
            )

    @classmethod
    def from_env(cls) -> ThoughtConfig:
        """Build from ``THOUGHTS_*`` env vars.

        * ``THOUGHTS_ENABLED`` — truthy strings ``1/true/yes/on`` (case-insensitive).
        * ``THOUGHTS_BACKEND`` — ``null`` or ``sqlite``; default ``null``.
        * ``THOUGHTS_DB_PATH`` — required when backend is ``sqlite``.
        * ``THOUGHTS_PHASES``  — comma-separated list of phase names. If unset,
          all phases pass through.
        """
        enabled = os.environ.get("THOUGHTS_ENABLED", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        backend_raw = os.environ.get("THOUGHTS_BACKEND", "null").strip().lower()
        if backend_raw not in ("null", "sqlite"):
            raise ThoughtConfigError(
                f"THOUGHTS_BACKEND must be 'null' or 'sqlite', got {backend_raw!r}"
            )
        backend: ThoughtBackend = backend_raw  # type: ignore[assignment]
        db_path_str = os.environ.get("THOUGHTS_DB_PATH")
        db_path = Path(db_path_str) if db_path_str else None
        phases_csv = os.environ.get("THOUGHTS_PHASES", "").strip()
        phases = (
            tuple(p.strip() for p in phases_csv.split(",") if p.strip())
            if phases_csv
            else None
        )
        return cls(
            enabled=enabled,
            backend=backend,
            db_path=db_path,
            phases=phases,
        )


def build_store(config: ThoughtConfig) -> ThoughtStore:
    """Materialize a :class:`ThoughtStore` from a :class:`ThoughtConfig`.

    Disabled configs always return a fresh :class:`NullThoughtStore` so the
    loop never has to special-case ``None``.
    """
    if not config.enabled or config.backend == "null":
        return NullThoughtStore()
    assert config.db_path is not None  # __post_init__ guarantees this.
    return SqliteThoughtStore(config.db_path, phases=config.phases)
