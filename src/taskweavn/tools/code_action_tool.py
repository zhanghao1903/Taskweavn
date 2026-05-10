"""Tool wrapper around :class:`SandboxExecutor`.

Exposes ``CodeAction`` to the LLM as the ``run_code`` tool. The tool owns
the executor for the duration of one ``AgentLoop.run()`` — :meth:`startup`
brings the container up, :meth:`shutdown` tears it down, and every
:meth:`execute` runs through the same long-lived container.
"""

from __future__ import annotations

from typing import ClassVar

from taskweavn.runtime.sandbox import SandboxConfig, SandboxExecutor
from taskweavn.tools.base import Tool
from taskweavn.tools.workspace import Workspace
from taskweavn.types.base import BaseAction, BaseObservation
from taskweavn.types.code_action import CodeAction, CodeExecutionObservation


class CodeActionTool(Tool[CodeAction, CodeExecutionObservation]):
    """LLM-facing tool that executes Python snippets under a tracking contract."""

    name: ClassVar[str] = "run_code"
    description: ClassVar[str] = (
        "Execute a Python snippet inside an isolated sandbox. You MUST declare "
        "every workspace file the snippet may read or write in `tracking.files` "
        "and every top-level variable whose final value you want captured in "
        "`tracking.variables`. Side effects outside the declared scope are "
        "recorded as `undeclared_changes` and may be flagged during audit. "
        "Each call gets a fresh Python interpreter — share state between calls "
        "by writing files inside the workspace."
    )
    action_type: ClassVar[type[BaseAction]] = CodeAction
    observation_type: ClassVar[type[BaseObservation]] = CodeExecutionObservation

    def __init__(
        self,
        workspace: Workspace,
        config: SandboxConfig | None = None,
        executor: SandboxExecutor | None = None,
    ) -> None:
        self._workspace = workspace
        self._executor = executor or SandboxExecutor(
            workspace_root=workspace.root,
            config=config or SandboxConfig(),
        )

    def startup(self) -> None:
        self._executor.start()

    def shutdown(self) -> None:
        self._executor.stop()

    def execute(self, action: CodeAction) -> CodeExecutionObservation:
        return self._executor.execute(action)
