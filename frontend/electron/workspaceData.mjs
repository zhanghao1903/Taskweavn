import { lstat, realpath } from "node:fs/promises";
import path from "node:path";

export const PLATO_WORKSPACE_DATA_DIRS = [".plato", ".taskweavn", ".code-agent"];

export class WorkspaceDataDeletionError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
    this.name = "WorkspaceDataDeletionError";
  }
}

export async function resolveWorkspaceDataTargets(workspacePath) {
  const workspaceRoot = path.resolve(workspacePath);
  const workspaceRealPath = await realpath(workspaceRoot).catch(() => workspaceRoot);
  const targets = [];

  for (const dirName of PLATO_WORKSPACE_DATA_DIRS) {
    const target = path.join(workspaceRoot, dirName);
    const stat = await lstat(target).catch((error) => {
      if (error?.code === "ENOENT") {
        return null;
      }
      throw error;
    });
    if (stat === null) {
      continue;
    }
    if (stat.isSymbolicLink()) {
      throw new WorkspaceDataDeletionError(
        "unsafe_metadata_symlink",
        "Plato data directory is a symbolic link.",
      );
    }

    const targetRealPath = await realpath(target);
    if (!isInsideWorkspace(workspaceRealPath, targetRealPath)) {
      throw new WorkspaceDataDeletionError(
        "unsafe_metadata_path",
        "Plato data directory resolves outside the workspace.",
      );
    }
    targets.push(target);
  }

  return targets;
}

function isInsideWorkspace(workspaceRoot, candidate) {
  const relative = path.relative(workspaceRoot, candidate);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}
