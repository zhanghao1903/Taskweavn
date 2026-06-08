import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import {
  buildWorkspaceEntryState,
  findWorkspacePathById,
  readWorkspaceEntryStore,
  rememberWorkspace,
  summarizeWorkspace,
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
      recentPaths: [],
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
    expect(raw.recentPaths).toEqual([second, first]);

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

  it("resolves a recent workspace by opaque id", async () => {
    const userDataPath = await tempDir();
    const workspacePath = path.join(userDataPath, "Selected");
    await rememberWorkspace(userDataPath, workspacePath);

    const summary = summarizeWorkspace(workspacePath, workspacePath);

    await expect(findWorkspacePathById(userDataPath, summary.id)).resolves.toBe(
      workspacePath,
    );
  });
});

async function tempDir() {
  const dir = await mkdtemp(path.join(os.tmpdir(), "plato-workspace-entry-"));
  tempDirs.push(dir);
  return dir;
}
