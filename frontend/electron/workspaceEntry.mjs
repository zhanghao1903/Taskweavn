import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const STORE_FILENAME = "workspace-entry.json";
const STORE_SCHEMA_VERSION = 3;
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
      return normalizeStoredState({});
    }
    return normalizeStoredState({});
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
  const now = new Date().toISOString();
  const previousRecord = previous.workspaces.find(
    (record) => record.path === normalizedPath,
  );
  const workspace = workspaceRecord(normalizedPath, {
    addedAt: previousRecord?.addedAt ?? now,
    archived: false,
    archivedAt: null,
    lastOpenedAt: now,
  });
  const workspaces = [
    workspace,
    ...previous.workspaces.filter((record) => record.path !== normalizedPath),
  ];
  return await writeWorkspaceEntryStore(userDataPath, {
    currentPath: normalizedPath,
    preferences: previous.preferences,
    workspaces,
  });
}

export async function findWorkspacePathById(
  userDataPath,
  id,
  { includeArchived = false } = {},
) {
  const state = await readWorkspaceEntryStore(userDataPath);
  const record = state.workspaces.find(
    (candidate) =>
      workspaceId(candidate.path) === id &&
      (includeArchived || candidate.archived !== true),
  );
  return record?.path ?? null;
}

export async function archiveWorkspaceById(userDataPath, id) {
  const state = await readWorkspaceEntryStore(userDataPath);
  const now = new Date().toISOString();
  const target = state.workspaces.find(
    (candidate) => workspaceId(candidate.path) === id,
  );
  if (target === undefined) {
    return { state, workspacePath: null };
  }

  const workspaces = state.workspaces.map((record) =>
    record.path === target.path
      ? workspaceRecord(record.path, {
          ...record,
          archived: true,
          archivedAt: now,
        })
      : record,
  );
  const currentPath =
    state.currentPath === target.path
      ? firstActivePath(workspaces, target.path)
      : state.currentPath;
  const nextState = await writeWorkspaceEntryStore(userDataPath, {
    currentPath,
    preferences: state.preferences,
    workspaces,
  });
  return { state: nextState, workspacePath: target.path };
}

export async function restoreWorkspaceById(userDataPath, id) {
  const state = await readWorkspaceEntryStore(userDataPath);
  const target = state.workspaces.find(
    (candidate) => workspaceId(candidate.path) === id,
  );
  if (target === undefined) {
    return { state, workspacePath: null };
  }

  const workspaces = [
    workspaceRecord(target.path, {
      ...target,
      archived: false,
      archivedAt: null,
    }),
    ...state.workspaces.filter((record) => record.path !== target.path),
  ];
  const nextState = await writeWorkspaceEntryStore(userDataPath, {
    currentPath: state.currentPath ?? target.path,
    preferences: state.preferences,
    workspaces,
  });
  return { state: nextState, workspacePath: target.path };
}

export async function removeWorkspaceById(userDataPath, id) {
  const state = await readWorkspaceEntryStore(userDataPath);
  const target = state.workspaces.find(
    (candidate) => workspaceId(candidate.path) === id,
  );
  if (target === undefined) {
    return { state, workspacePath: null };
  }

  const workspaces = state.workspaces.filter(
    (record) => record.path !== target.path,
  );
  const currentPath =
    state.currentPath === target.path
      ? firstActivePath(workspaces, target.path)
      : state.currentPath;
  const nextState = await writeWorkspaceEntryStore(userDataPath, {
    currentPath,
    preferences: state.preferences,
    workspaces,
  });
  return { state: nextState, workspacePath: target.path };
}

export async function readWorkspaceGitInitializeOnOpenPreference(userDataPath) {
  const state = await readWorkspaceEntryStore(userDataPath);
  return state.preferences.initializeGitOnOpen;
}

export async function writeWorkspaceGitInitializeOnOpenPreference(
  userDataPath,
  enabled,
) {
  const state = await readWorkspaceEntryStore(userDataPath);
  return await writeWorkspaceEntryStore(userDataPath, {
    currentPath: state.currentPath,
    preferences: {
      ...state.preferences,
      initializeGitOnOpen: enabled === true,
    },
    workspaces: state.workspaces,
  });
}

export function workspaceArchiveRequiresRuntimeSwitch(
  currentWorkspaceRoot,
  archivedWorkspacePath,
) {
  if (currentWorkspaceRoot === null || archivedWorkspacePath === null) {
    return false;
  }
  return (
    normalizeWorkspacePath(currentWorkspaceRoot) ===
    normalizeWorkspacePath(archivedWorkspacePath)
  );
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
  const archivedPaths = state.workspaces
    .filter((record) => record.archived)
    .map((record) => record.path);

  return {
    currentWorkspace:
      selectedPath === null ? null : summarizeWorkspace(selectedPath, selectedPath),
    error,
    archivedWorkspaces: archivedPaths.map((candidate) =>
      summarizeWorkspace(candidate, selectedPath, "archived"),
    ),
    recentWorkspaces: recentPaths.map((candidate) =>
      summarizeWorkspace(candidate, selectedPath),
    ),
    status,
  };
}

export function summarizeWorkspace(
  workspacePath,
  currentPath = null,
  lifecycleStatus = "active",
) {
  const normalizedPath = normalizeWorkspacePath(workspacePath);
  const name = path.basename(normalizedPath) || "Workspace";
  return {
    id: workspaceId(normalizedPath),
    isCurrent:
      currentPath !== null && normalizeWorkspacePath(currentPath) === normalizedPath,
    label: name,
    lifecycleStatus,
    name,
    pathLabel: name,
  };
}

function normalizeStoredState(raw) {
  const schemaVersion =
    typeof raw?.schemaVersion === "number" ? raw.schemaVersion : null;
  const hasExplicitCurrentPath =
    raw !== null &&
    typeof raw === "object" &&
    Object.prototype.hasOwnProperty.call(raw, "currentPath");
  const currentPath =
    typeof raw?.currentPath === "string" && raw.currentPath.length > 0
      ? normalizeWorkspacePath(raw.currentPath)
      : null;
  const rawRecords = Array.isArray(raw?.workspaces)
    ? raw.workspaces
        .filter((record) => typeof record?.path === "string" && record.path.length > 0)
        .map((record) =>
          workspaceRecord(record.path, {
            addedAt: safeDate(record.addedAt),
            archived: record.archived === true,
            archivedAt: safeDate(record.archivedAt),
            lastOpenedAt: safeDate(record.lastOpenedAt),
          }),
        )
    : workspaceRecordsFromV1(raw, currentPath);
  const workspaces = limitVisibleRecords(uniqueWorkspaceRecords(rawRecords));
  const activePaths = workspaces
    .filter((record) => record.archived !== true)
    .map((record) => record.path);
  const safeCurrentPath = safeStoredCurrentPath({
    activePaths,
    currentPath,
    hasExplicitCurrentPath,
    schemaVersion,
  });

  return {
    currentPath: safeCurrentPath,
    preferences: normalizePreferences(raw?.preferences),
    recentPaths: activePaths.slice(0, MAX_RECENT_WORKSPACES),
    schemaVersion: STORE_SCHEMA_VERSION,
    workspaces,
  };
}

function safeStoredCurrentPath({
  activePaths,
  currentPath,
  hasExplicitCurrentPath,
  schemaVersion,
}) {
  if (currentPath !== null && activePaths.includes(currentPath)) {
    return currentPath;
  }
  if (schemaVersion === STORE_SCHEMA_VERSION && hasExplicitCurrentPath) {
    return null;
  }
  return activePaths[0] ?? null;
}

function normalizePreferences(raw) {
  return {
    initializeGitOnOpen:
      typeof raw?.initializeGitOnOpen === "boolean"
        ? raw.initializeGitOnOpen
        : null,
  };
}

function workspaceRecordsFromV1(raw, currentPath) {
  const paths = [
    ...(currentPath === null ? [] : [currentPath]),
    ...(Array.isArray(raw?.recentPaths) ? raw.recentPaths : []),
  ];
  return paths
    .filter((candidate) => typeof candidate === "string" && candidate.length > 0)
    .map((candidate) => workspaceRecord(candidate));
}

function uniqueWorkspaceRecords(records) {
  const seen = new Set();
  const unique = [];
  for (const record of records) {
    if (seen.has(record.path)) {
      continue;
    }
    seen.add(record.path);
    unique.push(record);
  }
  return unique;
}

function limitVisibleRecords(records) {
  let activeCount = 0;
  const output = [];
  for (const record of records) {
    if (record.archived) {
      output.push(record);
      continue;
    }
    activeCount += 1;
    if (activeCount <= MAX_RECENT_WORKSPACES) {
      output.push(record);
    }
  }
  return output;
}

function workspaceRecord(workspacePath, overrides = {}) {
  const normalizedPath = normalizeWorkspacePath(workspacePath);
  return {
    addedAt: safeDate(overrides.addedAt),
    archived: overrides.archived === true,
    archivedAt: safeDate(overrides.archivedAt),
    lastOpenedAt: safeDate(overrides.lastOpenedAt),
    path: normalizedPath,
  };
}

function firstActivePath(records, excludedPath = null) {
  return (
    records.find(
      (record) => !record.archived && record.path !== excludedPath,
    )?.path ?? null
  );
}

function safeDate(value) {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function normalizeWorkspacePath(workspacePath) {
  return path.resolve(workspacePath);
}

function workspaceId(workspacePath) {
  return createHash("sha256").update(normalizeWorkspacePath(workspacePath)).digest("hex").slice(0, 16);
}
