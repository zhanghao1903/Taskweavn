export const WORKSPACE_GIT_INITIALIZE_ON_OPEN_STORAGE_KEY =
  "plato.workspaceGit.initializeOnOpen";
export const WORKSPACE_GIT_INITIALIZE_ON_OPEN_CHANGED_EVENT =
  "plato.workspaceGit.initializeOnOpenChanged";

type StorageLike = Pick<Storage, "getItem" | "setItem">;

export function readWorkspaceGitInitializeOnOpenPreference(
  storage: StorageLike | null | undefined = safeLocalStorage(),
): boolean {
  return readStoredWorkspaceGitInitializeOnOpenPreference(storage) === true;
}

export function readStoredWorkspaceGitInitializeOnOpenPreference(
  storage: StorageLike | null | undefined = safeLocalStorage(),
): boolean | null {
  if (storage === null || storage === undefined) {
    return null;
  }

  try {
    const stored = storage.getItem(WORKSPACE_GIT_INITIALIZE_ON_OPEN_STORAGE_KEY);
    if (stored === "1") {
      return true;
    }
    if (stored === "0") {
      return false;
    }
    return null;
  } catch {
    return null;
  }
}

export function writeWorkspaceGitInitializeOnOpenPreference(
  enabled: boolean,
  storage: StorageLike | null | undefined = safeLocalStorage(),
  eventTarget: Pick<typeof globalThis, "dispatchEvent"> | null | undefined =
    globalThis,
): void {
  if (storage !== null && storage !== undefined) {
    try {
      storage.setItem(
        WORKSPACE_GIT_INITIALIZE_ON_OPEN_STORAGE_KEY,
        enabled ? "1" : "0",
      );
    } catch {
      // Ignore storage failures; the current UI state can still update.
    }
  }

  try {
    eventTarget?.dispatchEvent(
      new CustomEvent(WORKSPACE_GIT_INITIALIZE_ON_OPEN_CHANGED_EVENT, {
        detail: { enabled },
      }),
    );
  } catch {
    // Older test environments may not support CustomEvent construction.
  }
}

export function workspaceGitSelectionOptionsFromPreference(
  storage: StorageLike | null | undefined = safeLocalStorage(),
): PlatoWorkspaceSelectionOptions | undefined {
  return readWorkspaceGitInitializeOnOpenPreference(storage)
    ? { initializeGitOnOpen: true }
    : undefined;
}

function safeLocalStorage(): StorageLike | null {
  try {
    if (globalThis.window?.localStorage) {
      return globalThis.window.localStorage;
    }
  } catch {
    // Fall back to global storage below.
  }

  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
}
