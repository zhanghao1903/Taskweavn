import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const STORE_FILENAME = "workspace-entry.json";
const MAX_RECENT_WORKSPACES = 8;

export function workspaceEntryStorePath(userDataPath) {
  return path.join(userDataPath, STORE_FILENAME);
}

export async function readWorkspaceEntryStore(userDataPath) {
  try {
    const raw = await readFile(workspaceEntryStorePath(userDataPath), "utf8");
    const parsed = JSON.parse(raw);
    return normalizeStoredState(parsed);
  } catch (error) {
    if (error?.code === "ENOENT") {
      return { currentPath: null, recentPaths: [] };
    }
    return { currentPath: null, recentPaths: [] };
  }
}

export async function writeWorkspaceEntryStore(userDataPath, state) {
  const normalized = normalizeStoredState(state);
  await mkdir(userDataPath, { recursive: true });
  await writeFile(
    workspaceEntryStorePath(userDataPath),
    `${JSON.stringify(normalized, null, 2)}\n`,
    "utf8",
  );
  return normalized;
}

export async function rememberWorkspace(userDataPath, workspacePath) {
  const normalizedPath = normalizeWorkspacePath(workspacePath);
  const previous = await readWorkspaceEntryStore(userDataPath);
  const recentPaths = [
    normalizedPath,
    ...previous.recentPaths.filter((candidate) => candidate !== normalizedPath),
  ].slice(0, MAX_RECENT_WORKSPACES);
  return await writeWorkspaceEntryStore(userDataPath, {
    currentPath: normalizedPath,
    recentPaths,
  });
}

export async function findWorkspacePathById(userDataPath, id) {
  const state = await readWorkspaceEntryStore(userDataPath);
  const allPaths = [
    ...(state.currentPath === null ? [] : [state.currentPath]),
    ...state.recentPaths,
  ];
  return allPaths.find((candidate) => workspaceId(candidate) === id) ?? null;
}

export async function buildWorkspaceEntryState({
  currentPath = null,
  error = null,
  status,
  userDataPath,
}) {
  const state = await readWorkspaceEntryStore(userDataPath);
  const selectedPath = currentPath ?? state.currentPath;
  const recentPaths = state.recentPaths.filter(
    (candidate) => candidate !== selectedPath,
  );

  return {
    currentWorkspace:
      selectedPath === null ? null : summarizeWorkspace(selectedPath, selectedPath),
    error,
    recentWorkspaces: recentPaths.map((candidate) =>
      summarizeWorkspace(candidate, selectedPath),
    ),
    status,
  };
}

export function summarizeWorkspace(workspacePath, currentPath = null) {
  const normalizedPath = normalizeWorkspacePath(workspacePath);
  const name = path.basename(normalizedPath) || "Workspace";
  return {
    id: workspaceId(normalizedPath),
    isCurrent:
      currentPath !== null && normalizeWorkspacePath(currentPath) === normalizedPath,
    label: name,
    name,
    pathLabel: name,
  };
}

function normalizeStoredState(raw) {
  const currentPath =
    typeof raw?.currentPath === "string" && raw.currentPath.length > 0
      ? normalizeWorkspacePath(raw.currentPath)
      : null;
  const recentPaths = Array.isArray(raw?.recentPaths)
    ? raw.recentPaths
        .filter((candidate) => typeof candidate === "string" && candidate.length > 0)
        .map((candidate) => normalizeWorkspacePath(candidate))
    : [];
  return {
    currentPath,
    recentPaths: [...new Set(recentPaths)].slice(0, MAX_RECENT_WORKSPACES),
  };
}

function normalizeWorkspacePath(workspacePath) {
  return path.resolve(workspacePath);
}

function workspaceId(workspacePath) {
  return createHash("sha256").update(normalizeWorkspacePath(workspacePath)).digest("hex").slice(0, 16);
}
