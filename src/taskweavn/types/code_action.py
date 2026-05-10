"""CodeAction schema (Phase 2.1).

A ``CodeAction`` is the agent's request to execute a snippet of code under a
declared side-effect contract. The contract has three parts:

* ``intent``  — a one-sentence description of what the snippet should
  accomplish. AuditAgent (Phase 2.3) compares this against the actual
  outcome to produce a verdict.
* ``code``    — the snippet itself.
* ``tracking``— :class:`TrackingConfig` declaring which workspace files and
  Python variables the sandbox (Phase 2.2) should snapshot so the auditor
  can verify the claim without re-running.

Side effects outside the declared scope are *not* blocked — the sandbox
records them as ``undeclared_changes`` on the resulting
:class:`CodeExecutionObservation`. Loose tracking gives the auditor signal
("the agent lied about scope") without forcing the runtime to be a security
oracle.
"""

from __future__ import annotations

import re
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from taskweavn.types.base import BaseAction, BaseObservation

_PY_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# ---------------------------------------------------------------------------
# Pure-data sub-models (not events; not registered)
# ---------------------------------------------------------------------------


class TrackingConfig(BaseModel):
    """Side-effect scope the agent claims this code will touch.

    Both fields are required — empty lists are allowed, but the LLM must
    declare them explicitly so "I won't touch anything" is a positive
    statement, not a missing field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    files: list[str] = Field(
        description=(
            "Workspace-relative file paths the snippet may read, create, or "
            "modify. Empty list means 'no file IO claimed'. Globs are not "
            "supported — list paths explicitly."
        ),
    )
    variables: list[str] = Field(
        description=(
            "Top-level Python variable names whose final values the sandbox "
            "should capture. Must be valid Python identifiers; nested "
            "attribute access (e.g. 'obj.field') is not supported."
        ),
    )

    @field_validator("variables")
    @classmethod
    def _validate_variable_names(cls, value: list[str]) -> list[str]:
        bad = [v for v in value if not _PY_IDENTIFIER.match(v)]
        if bad:
            raise ValueError(
                f"variables must be valid Python identifiers; got invalid: {bad!r}"
            )
        return value


class FileChange(BaseModel):
    """One file-system change observed by the sandbox.

    Either ``before_sha256`` or ``after_sha256`` is None when the change is a
    creation or deletion respectively. The diff text is intentionally not
    embedded — the sandbox writes a snapshot under
    ``<workspace>/.taskweavn/snapshots/<event_id>/`` and AuditAgent can pull
    the full content on demand.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(description="Workspace-relative path of the changed file.")
    change_type: Literal["created", "modified", "deleted"]
    before_sha256: str | None = Field(
        default=None,
        description="SHA-256 of the file before execution; None if the file did not exist.",
    )
    after_sha256: str | None = Field(
        default=None,
        description="SHA-256 of the file after execution; None if the file was deleted.",
    )
    size_delta: int = Field(
        description="after_size - before_size in bytes; negative on shrink/delete.",
    )


# ---------------------------------------------------------------------------
# Action / Observation
# ---------------------------------------------------------------------------


class CodeAction(BaseAction):
    """Execute a snippet of code under a declared tracking contract."""

    # See docs/interaction_layer_design.md Appendix B.
    baseline_risk: ClassVar[float] = 0.5

    intent: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "Single-sentence description of what this snippet is meant to "
            "accomplish. Forms the audit contract."
        ),
    )
    code: str = Field(
        min_length=1,
        description="The source snippet to execute.",
    )
    language: Literal["python"] = Field(
        default="python",
        description="Source language. Phase 2 only supports 'python'.",
    )
    tracking: TrackingConfig = Field(
        description="Declared scope of file IO and variables the sandbox should capture.",
    )


class CodeExecutionObservation(BaseObservation):
    """Result of running a :class:`CodeAction` in the sandbox.

    ``intent`` is echoed from the action so AuditAgent can consume the
    Observation alone without an EventStream lookup.
    """

    intent: str = Field(description="Echoed from the originating CodeAction.")
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float = Field(ge=0.0)
    timed_out: bool = False
    memory_exceeded: bool = False
    declared_changes: list[FileChange] = Field(
        default_factory=list,
        description="File changes inside the action's TrackingConfig.files set.",
    )
    undeclared_changes: list[FileChange] = Field(
        default_factory=list,
        description="File changes the sandbox observed outside the declared scope.",
    )
    variable_dump: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Final repr() of declared variables, truncated to ~1000 chars per value. "
            "Missing keys mean the name was never bound at module level."
        ),
    )
    blocked_reason: str | None = Field(
        default=None,
        description=(
            "Set when the sandbox refused to run the snippet (e.g. dangerous "
            "command pattern). When set, exit_code is -1 and IO/variable "
            "fields are empty."
        ),
    )
