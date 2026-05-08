"""Autonomy behavior + presets (Phase 3.2).

:class:`AutonomyBehavior` is the user-side knob for "when should the agent
ask, and what should it do if I don't reply?". The :class:`AutonomyGate`
(landing in 3.5) consumes it; this module is just the value object plus a
small library of vetted defaults.

Five presets cover the spectrum:

* ``full_auto``   — never ask, never block
* ``risk_gated`` — ask once risk crosses 0.5 (default)
* ``careful``    — ask earlier (0.3) and wait longer
* ``collaborative`` — ask whenever the agent isn't confident
* ``manual``     — ask before every action (learning / audit mode)

Presets are immutable templates. Users fork via ``replace`` (frozen dataclass
free helper) to customize per-session.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

# ---------------------------------------------------------------------------
# Enumerations (literal aliases so they show up in static analysis)
# ---------------------------------------------------------------------------

AutonomyTrigger = Literal["never", "on_risk", "on_uncertainty", "always"]
"""When the gate emits an actionable message."""

WaitStrategy = Literal["sync", "async"]
"""``sync`` blocks the agent loop until reply or timeout; ``async`` lets the
loop continue and folds the eventual response back as a system message in a
later iteration."""

TimeoutAction = Literal["wait", "proceed_default", "proceed_confident", "skip"]
"""What to do when a sync wait times out."""

AutonomyPresetName = Literal[
    "full_auto", "risk_gated", "careful", "collaborative", "manual"
]


# ---------------------------------------------------------------------------
# Behavior
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AutonomyBehavior:
    """Per-run autonomy contract.

    All fields have sensible defaults; passing no arguments yields the
    ``risk_gated`` preset's effective values.
    """

    # ── Trigger dimension ─────────────────────────────────────────────
    trigger: AutonomyTrigger = "on_risk"
    risk_threshold: float = 0.5
    """When ``trigger='on_risk'``: emit actionable iff ``final_risk >= threshold``.

    For ``never`` / ``always`` the threshold is ignored. For
    ``on_uncertainty`` it is unused (see ``confidence_threshold``).
    """

    confidence_threshold: float = 0.5
    """When ``trigger='on_uncertainty'``: emit actionable iff LLM confidence
    falls below this value. Ignored for other triggers; effective once a
    :class:`ConfidenceProvider` is wired in (Phase 3.7+)."""

    # ── Wait dimension ────────────────────────────────────────────────
    wait_strategy: WaitStrategy = "sync"
    wait_timeout: float | None = 300.0
    """Seconds. ``None`` means wait indefinitely. Ignored when
    ``wait_strategy='async'`` — async waits never block the loop."""

    timeout_action: TimeoutAction = "proceed_default"
    """What to do on sync timeout. ``async`` ignores it."""

    notify_on_proceed: bool = True
    """Whether to emit a follow-up informational message after a timeout
    self-decision, so the user sees what the agent did. The audit fact still
    lands on the EventStream regardless (see design Q2)."""

    # ── Validation ────────────────────────────────────────────────────
    def __post_init__(self) -> None:
        _validate_unit_interval("risk_threshold", self.risk_threshold)
        _validate_unit_interval("confidence_threshold", self.confidence_threshold)
        if self.wait_timeout is not None and self.wait_timeout <= 0:
            raise ValueError(
                f"wait_timeout must be positive or None; got {self.wait_timeout!r}"
            )
        if self.wait_strategy == "async" and self.timeout_action != "proceed_default":
            # async never times out — surfacing a non-default timeout_action
            # is a configuration smell. Allow it but don't pretend it matters.
            # We deliberately don't raise: composing presets via `replace`
            # shouldn't be hostile.
            pass


def _validate_unit_interval(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name}={value!r} must lie in [0.0, 1.0]")


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------


_FULL_AUTO: Final = AutonomyBehavior(
    trigger="never",
    wait_strategy="async",
    wait_timeout=None,
    timeout_action="proceed_default",
    notify_on_proceed=False,
)

_RISK_GATED: Final = AutonomyBehavior(
    trigger="on_risk",
    risk_threshold=0.5,
    wait_strategy="sync",
    wait_timeout=300.0,
    timeout_action="proceed_default",
    notify_on_proceed=True,
)

_CAREFUL: Final = AutonomyBehavior(
    trigger="on_risk",
    risk_threshold=0.3,
    wait_strategy="sync",
    wait_timeout=600.0,
    timeout_action="proceed_default",
    notify_on_proceed=True,
)

_COLLABORATIVE: Final = AutonomyBehavior(
    trigger="on_uncertainty",
    confidence_threshold=0.5,
    wait_strategy="sync",
    wait_timeout=None,
    timeout_action="wait",
    notify_on_proceed=True,
)

_MANUAL: Final = AutonomyBehavior(
    trigger="always",
    wait_strategy="sync",
    wait_timeout=None,
    timeout_action="wait",
    notify_on_proceed=True,
)


AUTONOMY_PRESETS: Final[dict[AutonomyPresetName, AutonomyBehavior]] = {
    "full_auto": _FULL_AUTO,
    "risk_gated": _RISK_GATED,
    "careful": _CAREFUL,
    "collaborative": _COLLABORATIVE,
    "manual": _MANUAL,
}


def get_preset(name: AutonomyPresetName) -> AutonomyBehavior:
    """Return the preset by name. Raises :class:`KeyError` for unknown names.

    The returned behavior is immutable — fork via :func:`dataclasses.replace`
    to customize.
    """
    try:
        return AUTONOMY_PRESETS[name]
    except KeyError as exc:
        valid = ", ".join(sorted(AUTONOMY_PRESETS))
        raise KeyError(
            f"unknown autonomy preset {name!r}; valid: {valid}"
        ) from exc
