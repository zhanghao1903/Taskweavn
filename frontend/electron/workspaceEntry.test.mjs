import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import {
  archiveWorkspaceById,
  buildWorkspaceEntryState,
  findWorkspacePathById,
  removeWorkspaceById,
  readWorkspaceGitInitializeOnOpenPreference,
  readWorkspaceEntryStore,
  rememberWorkspace,
  restoreWorkspaceById,
  summarizeWorkspace,
  writeWorkspaceGitInitializeOnOpenPreference,
  workspaceArchiveRequiresRuntimeSwitch,
  workspaceEntryStorePath,
} from "./workspaceEntry.mjs";

let tempDirs = [];

afterEach(async () => {
  await Promise.all(
    tempDirs.map((dir) => rm(dir, { force: true, recursive: true })),
  );
  tempDirs = [];
});

describe("workspace entry store", () => {
  it("returns an empty state when no persisted workspace exists", async () => {
    const userDataPath = await tempDir();

    await expect(readWorkspaceEntryStore(userDataPath)).resolves.toEqual({
      currentPath: null,
      preferences: {
        initializeGitOnOpen: null,
      },
      recentPaths: [],
      schemaVersion: 3,
      workspaces: [],
    });
  });

  it("persists the current workspace and recent workspace summaries", async () => {
    const userDataPath = await tempDir();
    const first = path.join(userDataPath, "Project One");
    const second = path.join(userDataPath, "Project Two");

    await rememberWorkspace(userDataPath, first);
    await rememberWorkspace(userDataPath, second);

    const raw = JSON.parse(
      await readFile(workspaceEntryStorePath(userDataPath), "utf8"),
    );
    expect(raw.currentPath).toBe(second);
    expect(raw.preferences).toEqual({ initializeGitOnOpen: null });
    expect(raw.recentPaths).toEqual([second, first]);
    expect(raw.schemaVersion).toBe(3);
    expect(raw.workspaces).toEqual([
      expect.objectContaining({ archived: false, path: second }),
      expect.objectContaining({ archived: false, path: first }),
    ]);

    const state = await buildWorkspaceEntryState({
      status: "ready",
      userDataPath,
    });
    expect(state.currentWorkspace).toMatchObject({
      isCurrent: true,
      name: "Project Two",
      pathLabel: "Project Two",
    });
    expect(state.recentWorkspaces).toEqual([
      expect.objectContaining({ name: "Project One" }),
    ]);
  });

  it("migrates the legacy current/recent path store shape", async () => {
    const userDataPath = await tempDir();
    const first = path.join(userDataPath, "Legacy One");
    const second = path.join(userDataPath, "Legacy Two");
    await writeFile(
      workspaceEntryStorePath(userDataPath),
      `${JSON.stringify({ currentPath: first, recentPaths: [second] })}\n`,
      "utf8",
    );

    await expect(readWorkspaceEntryStore(userDataPath)).resolves.toMatchObject({
      currentPath: first,
      preferences: {
        initializeGitOnOpen: null,
      },
      recentPaths: [first, second],
      schemaVersion: 3,
      workspaces: [
        expect.objectContaining({ archived: false, path: first }),
        expect.objectContaining({ archived: false, path: second }),
      ],
    });
  });

  it("resolves a recent workspace by opaque id", async () => {
    const userDataPath = await tempDir();
    const workspacePath = path.join(userDataPath, "Selected");
    await rememberWorkspace(userDataPath, workspacePath);

    const summary = summarizeWorkspace(workspacePath, workspacePath);

    await expect(findWorkspacePathById(userDataPath, summary.id)).resolves.toBe(
      workspacePath,
    );
  });

  it("archives, restores, and removes workspaces without exposing paths in summaries", async () => {
    const userDataPath = await tempDir();
    const first = path.join(userDataPath, "Archive One");
    const second = path.join(userDataPath, "Archive Two");
    await rememberWorkspace(userDataPath, first);
    await rememberWorkspace(userDataPath, second);

    const secondSummary = summarizeWorkspace(second, second);
    await archiveWorkspaceById(userDataPath, secondSummary.id);

    let state = await buildWorkspaceEntryState({
      status: "ready",
      userDataPath,
    });
    expect(state.currentWorkspace).toMatchObject({ name: "Archive One" });
    expect(state.archivedWorkspaces).toEqual([
      expect.objectContaining({
        lifecycleStatus: "archived",
        name: "Archive Two",
        pathLabel: "Archive Two",
      }),
    ]);
    expect(state.archivedWorkspaces[0].pathLabel).not.toContain(userDataPath);

    await restoreWorkspaceById(userDataPath, secondSummary.id);
    state = await buildWorkspaceEntryState({
      status: "ready",
      userDataPath,
    });
    expect(state.currentWorkspace).toMatchObject({ name: "Archive One" });
    expect(state.recentWorkspaces).toEqual([
      expect.objectContaining({ name: "Archive Two" }),
    ]);

    await removeWorkspaceById(userDataPath, secondSummary.id);
    state = await buildWorkspaceEntryState({
      status: "ready",
      userDataPath,
    });
    expect(state.recentWorkspaces).toEqual([]);
    expect(state.archivedWorkspaces).toEqual([]);
  });

  it("requires a runtime switch only when archiving the current workspace", async () => {
    const userDataPath = await tempDir();
    const current = path.join(userDataPath, "Current");
    const other = path.join(userDataPath, "Other");

    expect(workspaceArchiveRequiresRuntimeSwitch(current, current)).toBe(true);
    expect(workspaceArchiveRequiresRuntimeSwitch(current, other)).toBe(false);
    expect(workspaceArchiveRequiresRuntimeSwitch(null, other)).toBe(false);
    expect(workspaceArchiveRequiresRuntimeSwitch(current, null)).toBe(false);
  });

  it("persists workspace Git initialization preference in user data", async () => {
    const userDataPath = await tempDir();
    const workspacePath = path.join(userDataPath, "Project");

    await expect(
      readWorkspaceGitInitializeOnOpenPreference(userDataPath),
    ).resolves.toBeNull();

    await writeWorkspaceGitInitializeOnOpenPreference(userDataPath, true);
    await rememberWorkspace(userDataPath, workspacePath);

    await expect(
      readWorkspaceGitInitializeOnOpenPreference(userDataPath),
    ).resolves.toBe(true);

    await writeWorkspaceGitInitializeOnOpenPreference(userDataPath, false);

    await expect(
      readWorkspaceGitInitializeOnOpenPreference(userDataPath),
    ).resolves.toBe(false);
  });
});

async function tempDir() {
  const dir = await mkdtemp(path.join(os.tmpdir(), "plato-workspace-entry-"));
  tempDirs.push(dir);
  return dir;
}
