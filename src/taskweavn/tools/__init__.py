"""Tool layer: file + shell tools the agent can invoke."""

from taskweavn.tools.ask import AskUserTool
from taskweavn.tools.base import Tool
from taskweavn.tools.code_action_tool import CodeActionTool
from taskweavn.tools.confirmation import RequestConfirmationTool
from taskweavn.tools.computer_use import (
    ComputerUseBackend,
    ComputerUseTool,
    DisabledComputerUseBackend,
    ScriptedComputerUseBackend,
)
from taskweavn.tools.fs import (
    DirEntry,
    DirListingObservation,
    FileContentObservation,
    FileWriteObservation,
    ListDirAction,
    ListDirTool,
    ReadFileAction,
    ReadFileTool,
    WriteFileAction,
    WriteFileTool,
)
from taskweavn.tools.precision_fs import (
    AppendFileAction,
    AppendFileTool,
    FileRangeObservation,
    PrecisionFileContentHash,
    PrecisionFileMutationObservation,
    ReadFileRangeAction,
    ReadFileRangeTool,
    ReplaceFileRangeAction,
    ReplaceFileRangeTool,
    SearchWorkspaceAction,
    SearchWorkspaceTool,
    WorkspaceSearchObservation,
)
from taskweavn.tools.shell import (
    CommandResultObservation,
    RunCommandAction,
    RunCommandTool,
)
from taskweavn.tools.web_search import (
    WebSearchAction,
    WebSearchObservation,
    WebSearchTool,
)
from taskweavn.tools.web_fetch import (
    WebFetchAction,
    WebFetchObservation,
    WebFetchTool,
)
from taskweavn.tools.workspace import (
    PathOutsideWorkspaceError,
    PathProtectedWorkspaceError,
    Workspace,
)

__all__ = [
    "AskUserTool",
    "AppendFileAction",
    "AppendFileTool",
    "CodeActionTool",
    "CommandResultObservation",
    "ComputerUseBackend",
    "ComputerUseTool",
    "DirEntry",
    "DirListingObservation",
    "DisabledComputerUseBackend",
    "FileContentObservation",
    "FileRangeObservation",
    "FileWriteObservation",
    "ListDirAction",
    "ListDirTool",
    "PathOutsideWorkspaceError",
    "PathProtectedWorkspaceError",
    "PrecisionFileContentHash",
    "PrecisionFileMutationObservation",
    "ReadFileAction",
    "ReadFileRangeAction",
    "ReadFileRangeTool",
    "ReadFileTool",
    "ReplaceFileRangeAction",
    "ReplaceFileRangeTool",
    "RequestConfirmationTool",
    "RunCommandAction",
    "RunCommandTool",
    "SearchWorkspaceAction",
    "SearchWorkspaceTool",
    "ScriptedComputerUseBackend",
    "Tool",
    "WebFetchAction",
    "WebFetchObservation",
    "WebFetchTool",
    "WebSearchAction",
    "WebSearchObservation",
    "WebSearchTool",
    "Workspace",
    "WorkspaceSearchObservation",
    "WriteFileAction",
    "WriteFileTool",
]
