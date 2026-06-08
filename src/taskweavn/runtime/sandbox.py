"""Docker-based sandbox executor for :class:`CodeAction` (Phase 2.2).

The executor allocates **one container per AgentLoop.run()** and reuses it
across many ``CodeAction`` invocations:

* :meth:`SandboxExecutor.start` runs ``docker run -d ... sleep infinity`` with
  the workspace bind-mounted at ``/workspace`` and an isolated network.
* :meth:`SandboxExecutor.execute` writes the snippet (plus a tiny
  instrumentation wrapper) into ``<workspace>/.plato/runs/<event_id>/``,
  then calls ``docker exec`` on the running container.
* :meth:`SandboxExecutor.stop` removes the container.

Critical contract: each ``docker exec`` is a **fresh Python interpreter**.
Container reuse buys filesystem persistence + amortised startup cost +
network isolation, but Python globals do *not* survive between actions —
state must flow through declared file IO. See ``docs/agent_project_plan.md``
Phase 2.2 for the full rationale.

Side-effect tracking
--------------------
Before executing, the sandbox snapshots SHA-256 of every file under the
workspace (skipping Plato metadata so our own bookkeeping doesn't show up
as undeclared churn). After the run it diffs the snapshot to produce
``FileChange`` records, partitioned into ``declared_changes`` (paths inside
``action.tracking.files``) and ``undeclared_changes`` (everything else).

Variable capture is performed by a small wrapper script that ``exec``\\s the
user's snippet in a fresh module dict and writes ``repr()`` of each tracked
name to ``track.json`` inside the run dir under a ``try/finally`` so partial
results survive an exception.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from taskweavn.core.workspace_layout import (
    PROTECTED_WORKSPACE_METADATA_DIR_NAMES,
    WORKSPACE_META_DIR_NAME,
)
from taskweavn.observability import LogContext, get_object_logger
from taskweavn.types.code_action import (
    CodeAction,
    CodeExecutionObservation,
    FileChange,
)

if TYPE_CHECKING:
    from docker import DockerClient  # type: ignore[import-untyped]
    from docker.models.containers import Container  # type: ignore[import-untyped]

_SANDBOX_LOGGER = get_object_logger("sandbox")

#: Subdirectory inside the workspace where per-run intermediates live.
RUNS_SUBDIR = f"{WORKSPACE_META_DIR_NAME}/runs"

#: Maximum repr length kept per variable in the dump (post-truncation).
VARIABLE_REPR_MAX_CHARS = 1000

#: Filename written into each run dir holding the captured variable dump.
TRACK_FILENAME = "track.json"

#: Filename written into each run dir holding the wrapped script the
#: container actually executes.
SCRIPT_FILENAME = "script.py"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SandboxConfig:
    """Sandbox-wide knobs. Per-action overrides are intentionally not supported —
    keeping the LLM's surface area small means the agent can't talk itself
    out of the safety envelope."""

    image: str = "python:3.12-slim"
    timeout_seconds: int = 30
    memory_mb: int = 512
    cpus: float = 1.0
    network_mode: str = "none"
    workdir: str = "/workspace"
    container_name_prefix: str = "taskweavn-sandbox"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _hash_file(path: Path, *, chunk: int = 65536) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _snapshot_workspace(root: Path) -> dict[str, tuple[str, int]]:
    """Walk ``root`` and return ``{relpath: (sha256, size)}``.

    Anything under Plato metadata is skipped so the runtime's own scratch
    dir does not pollute the diff. Symlinks are read at face value (their
    target's content); broken links are ignored.
    """
    snapshot: dict[str, tuple[str, int]] = {}
    skip_prefixes = tuple(root / name for name in PROTECTED_WORKSPACE_METADATA_DIR_NAMES)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            if any(
                path == skip_prefix or skip_prefix in path.parents
                for skip_prefix in skip_prefixes
            ):
                continue
            rel = path.relative_to(root).as_posix()
            stat = path.stat()
            snapshot[rel] = (_hash_file(path), stat.st_size)
        except OSError:
            # Race or unreadable file — treat as missing.
            continue
    return snapshot


def _diff_snapshots(
    before: dict[str, tuple[str, int]],
    after: dict[str, tuple[str, int]],
) -> list[FileChange]:
    """Compute ``FileChange`` records from two workspace snapshots."""
    paths = set(before) | set(after)
    changes: list[FileChange] = []
    for path in sorted(paths):
        b = before.get(path)
        a = after.get(path)
        if b is None and a is not None:
            changes.append(
                FileChange(
                    path=path,
                    change_type="created",
                    before_sha256=None,
                    after_sha256=a[0],
                    size_delta=a[1],
                )
            )
        elif b is not None and a is None:
            changes.append(
                FileChange(
                    path=path,
                    change_type="deleted",
                    before_sha256=b[0],
                    after_sha256=None,
                    size_delta=-b[1],
                )
            )
        elif b is not None and a is not None and b[0] != a[0]:
            changes.append(
                FileChange(
                    path=path,
                    change_type="modified",
                    before_sha256=b[0],
                    after_sha256=a[0],
                    size_delta=a[1] - b[1],
                )
            )
    return changes


def _normalize_relpath(path: str) -> str:
    """Canonicalise a workspace-relative path for set membership.

    Strips ``./`` prefixes, collapses ``//``, and rejects nothing — partition
    is comparison only, never disk access.
    """
    p = PurePosixPath(path)
    parts = [part for part in p.parts if part not in ("", ".")]
    return PurePosixPath(*parts).as_posix() if parts else ""


def _partition_changes(
    changes: list[FileChange], declared: list[str]
) -> tuple[list[FileChange], list[FileChange]]:
    """Split changes into (declared, undeclared) by normalized path equality."""
    declared_set = {_normalize_relpath(p) for p in declared}
    inside: list[FileChange] = []
    outside: list[FileChange] = []
    for change in changes:
        if _normalize_relpath(change.path) in declared_set:
            inside.append(change)
        else:
            outside.append(change)
    return inside, outside


def _build_wrapper_script(
    user_code: str, variables: list[str], track_path: str
) -> str:
    """Wrap ``user_code`` so we capture variable values even on exception.

    The wrapper runs the snippet in a fresh module dict, then dumps ``repr()``
    of each tracked name (truncated) to ``track_path`` in a ``finally`` block.
    Names that were never bound are simply absent from the dump.

    ``track_path`` should be an absolute container path so the dump lands in
    the per-event run dir regardless of the snippet's cwd or any cwd changes
    the snippet itself performs.
    """
    return f"""# Auto-generated by SandboxExecutor — do not edit.
from __future__ import annotations

import json
import sys
import traceback

_TRACKED = {variables!r}
_MAX = {VARIABLE_REPR_MAX_CHARS}
_TRACK_PATH = {track_path!r}

_user_globals: dict[str, object] = {{"__name__": "__main__"}}
_exit_code = 0
try:
    exec(compile({user_code!r}, "<code-action>", "exec"), _user_globals)
except SystemExit as _e:
    _exit_code = int(_e.code) if isinstance(_e.code, int) else 1
except BaseException:
    traceback.print_exc()
    _exit_code = 1
finally:
    _dump: dict[str, str] = {{}}
    for _name in _TRACKED:
        if _name in _user_globals:
            try:
                _r = repr(_user_globals[_name])
            except Exception as _re:  # noqa: BLE001
                _r = f"<repr() raised {{type(_re).__name__}}: {{_re}}>"
            if len(_r) > _MAX:
                _r = _r[:_MAX] + f"...<truncated {{len(_r) - _MAX}} chars>"
            _dump[_name] = _r
    try:
        with open(_TRACK_PATH, "w", encoding="utf-8") as _fh:
            json.dump(_dump, _fh, ensure_ascii=False)
    except OSError:
        pass

sys.exit(_exit_code)
"""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SandboxError(RuntimeError):
    """Raised when the sandbox itself fails (daemon down, image missing,
    container crash). Per-action failures are reported as
    :class:`CodeExecutionObservation` instead."""


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


@dataclass
class SandboxExecutor:
    """Owns one Docker container for the duration of a task."""

    workspace_root: Path
    config: SandboxConfig = field(default_factory=SandboxConfig)
    docker_client: Any = None  # docker.DockerClient — typed loosely so unit
    # tests can pass a Mock without importing docker at module load.

    _container: Container | None = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the long-lived container. Idempotent — second call is a no-op."""
        if self._container is not None:
            return

        client = self._get_client()
        self._ensure_image(client)

        runs_dir = self.workspace_root / RUNS_SUBDIR
        runs_dir.mkdir(parents=True, exist_ok=True)

        name = f"{self.config.container_name_prefix}-{int(time.time() * 1000)}"
        # nano_cpus is the docker-py knob for --cpus.
        nano_cpus = int(self.config.cpus * 1_000_000_000)
        self._container = client.containers.run(
            image=self.config.image,
            command=["sleep", "infinity"],
            name=name,
            detach=True,
            auto_remove=False,
            network_mode=self.config.network_mode,
            mem_limit=f"{self.config.memory_mb}m",
            nano_cpus=nano_cpus,
            working_dir=self.config.workdir,
            volumes={
                str(self.workspace_root.resolve()): {
                    "bind": self.config.workdir,
                    "mode": "rw",
                }
            },
        )
        _SANDBOX_LOGGER.info(
            "container_started",
            context=LogContext(workspace_root=str(self.workspace_root)),
            data={
                "container_name": name,
                "image": self.config.image,
                "network_mode": self.config.network_mode,
                "memory_mb": self.config.memory_mb,
                "cpus": self.config.cpus,
            },
        )

    def stop(self) -> None:
        """Stop and remove the container. Tolerates missing/already-removed."""
        if self._container is None:
            return
        try:
            self._container.remove(force=True)
        except Exception:  # noqa: BLE001 — teardown must not raise.
            _SANDBOX_LOGGER.error(
                "container_remove_failed",
                context=LogContext(workspace_root=str(self.workspace_root)),
                data={"container": repr(self._container)},
            )
        finally:
            _SANDBOX_LOGGER.info(
                "container_stopped",
                context=LogContext(workspace_root=str(self.workspace_root)),
            )
            self._container = None

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, action: CodeAction) -> CodeExecutionObservation:
        """Run a single :class:`CodeAction` inside the container."""
        if self._container is None:
            raise SandboxError("SandboxExecutor.execute() called before start().")
        context = LogContext(
            action_id=action.event_id,
            workspace_root=str(self.workspace_root),
        )

        run_dir = self.workspace_root / RUNS_SUBDIR / action.event_id
        run_dir.mkdir(parents=True, exist_ok=True)
        script_path = run_dir / SCRIPT_FILENAME
        track_path = run_dir / TRACK_FILENAME
        rel_run_dir_early = run_dir.relative_to(self.workspace_root).as_posix()
        container_track_path = (
            f"{self.config.workdir}/{rel_run_dir_early}/{TRACK_FILENAME}"
        )
        script_path.write_text(
            _build_wrapper_script(
                action.code,
                list(action.tracking.variables),
                container_track_path,
            ),
            encoding="utf-8",
        )

        before = _snapshot_workspace(self.workspace_root)

        # The container always runs with cwd = /workspace (config.workdir) so
        # the snippet's relative file IO resolves at the workspace root, the
        # same place the LLM declared paths against.
        container_script = (
            f"{self.config.workdir}/{rel_run_dir_early}/{SCRIPT_FILENAME}"
        )
        container_workdir = self.config.workdir

        cmd = [
            "timeout",
            "--signal=KILL",
            str(self.config.timeout_seconds),
            "python",
            "-I",
            container_script,
        ]

        start = time.monotonic()
        _SANDBOX_LOGGER.info(
            "execute_start",
            context=context,
            data={
                "intent": action.intent,
                "tracking_files": list(action.tracking.files),
                "tracking_variables": list(action.tracking.variables),
                "timeout_seconds": self.config.timeout_seconds,
                "run_dir": rel_run_dir_early,
            },
        )
        try:
            exec_result = self._container.exec_run(
                cmd=cmd,
                workdir=container_workdir,
                demux=True,
                tty=False,
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.monotonic() - start) * 1000
            _SANDBOX_LOGGER.error(
                "execute_failed",
                context=context,
                data={
                    "error_type": type(exc).__name__,
                    "error_summary": str(exc)[:500],
                    "duration_ms": duration_ms,
                },
            )
            return CodeExecutionObservation(
                action_id=action.event_id,
                intent=action.intent,
                exit_code=-1,
                stdout="",
                stderr=f"sandbox exec failed: {type(exc).__name__}: {exc}",
                duration_ms=duration_ms,
                success=False,
                blocked_reason="sandbox_error",
            )
        duration_ms = (time.monotonic() - start) * 1000

        exit_code = int(exec_result.exit_code or 0)
        stdout_bytes, stderr_bytes = exec_result.output if exec_result.output else (b"", b"")
        stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
        stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")

        # `timeout` exits 124 on SIGTERM, 137 on SIGKILL.
        timed_out = exit_code in (124, 137)

        after = _snapshot_workspace(self.workspace_root)
        all_changes = _diff_snapshots(before, after)
        declared_changes, undeclared_changes = _partition_changes(
            all_changes, list(action.tracking.files)
        )

        variable_dump = self._read_variable_dump(track_path)
        _SANDBOX_LOGGER.info(
            "execute_result",
            context=context,
            data={
                "exit_code": exit_code,
                "success": exit_code == 0 and not timed_out,
                "timed_out": timed_out,
                "duration_ms": duration_ms,
                "declared_change_count": len(declared_changes),
                "undeclared_change_count": len(undeclared_changes),
                "captured_variable_count": len(variable_dump),
            },
        )

        return CodeExecutionObservation(
            action_id=action.event_id,
            intent=action.intent,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            timed_out=timed_out,
            declared_changes=declared_changes,
            undeclared_changes=undeclared_changes,
            variable_dump=variable_dump,
            success=(exit_code == 0 and not timed_out),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_client(self) -> DockerClient:
        if self.docker_client is not None:
            return self.docker_client
        try:
            import docker  # local import: optional at module load
        except ImportError as exc:  # pragma: no cover — dependency is required.
            raise SandboxError("docker SDK not installed") from exc
        try:
            self.docker_client = docker.from_env()
        except Exception as exc:
            raise SandboxError(
                "could not connect to Docker daemon — is it running?"
            ) from exc
        return self.docker_client

    def _ensure_image(self, client: DockerClient) -> None:
        """Lazy-pull the configured image if it isn't present locally."""
        try:
            client.images.get(self.config.image)
            return
        except Exception:  # noqa: BLE001 — fall through to pull.
            pass
        _SANDBOX_LOGGER.info(
            "image_pull_start",
            context=LogContext(workspace_root=str(self.workspace_root)),
            data={"image": self.config.image},
        )
        try:
            client.images.pull(self.config.image)
        except Exception as exc:  # noqa: BLE001
            _SANDBOX_LOGGER.error(
                "image_pull_failed",
                context=LogContext(workspace_root=str(self.workspace_root)),
                data={
                    "image": self.config.image,
                    "error_type": type(exc).__name__,
                    "error_summary": str(exc)[:500],
                },
            )
            raise SandboxError(
                f"failed to pull sandbox image {self.config.image!r}: {exc}"
            ) from exc

    @staticmethod
    def _read_variable_dump(track_path: Path) -> dict[str, str]:
        if not track_path.exists():
            return {}
        try:
            data = json.loads(track_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        # Defensive: coerce any non-str values to str.
        return {str(k): str(v) for k, v in data.items()}
