"""Execution environment registry for the Execution Plane."""

from __future__ import annotations

from collections.abc import Iterable
from threading import RLock
from typing import Protocol, runtime_checkable

from taskweavn.execution_plane.models import CapabilityPolicy, ExecutionEnv, utcnow


@runtime_checkable
class ExecutionEnvRegistry(Protocol):
    def upsert(self, env: ExecutionEnv) -> ExecutionEnv: ...

    def get(self, env_id: str) -> ExecutionEnv | None: ...

    def list(self) -> tuple[ExecutionEnv, ...]: ...

    def find_compatible(self, policy: CapabilityPolicy) -> ExecutionEnv | None: ...


class InMemoryExecutionEnvRegistry:
    def __init__(self, envs: Iterable[ExecutionEnv] = ()) -> None:
        self._lock = RLock()
        self._envs: dict[str, ExecutionEnv] = {}
        for env in envs:
            self.upsert(env)

    def upsert(self, env: ExecutionEnv) -> ExecutionEnv:
        with self._lock:
            updated = env.model_copy(
                update={"last_heartbeat_at": env.last_heartbeat_at or utcnow()}
            )
            self._envs[updated.env_id] = updated
            return updated

    def get(self, env_id: str) -> ExecutionEnv | None:
        with self._lock:
            return self._envs.get(env_id)

    def list(self) -> tuple[ExecutionEnv, ...]:
        with self._lock:
            return tuple(sorted(self._envs.values(), key=lambda env: env.env_id))

    def find_compatible(self, policy: CapabilityPolicy) -> ExecutionEnv | None:
        with self._lock:
            candidates = [
                env
                for env in self._envs.values()
                if env.supports(policy)
            ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda env: env.env_id)[0]


def default_local_execution_env(
    *,
    capabilities: tuple[str, ...] = ("execute", "testing"),
    tool_pool: tuple[str, ...] = (),
) -> ExecutionEnv:
    return ExecutionEnv(
        env_id="local-default",
        display_name="Local Default Execution Env",
        status="online",
        capabilities=capabilities,
        tool_pool=tool_pool,
        runtime_version="local",
    )
