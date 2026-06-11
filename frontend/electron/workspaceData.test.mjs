import { mkdtemp, mkdir, rm, symlink } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import {
  resolveWorkspaceDataTargets,
  WorkspaceDataDeletionError,
} from "./workspaceData.mjs";

let tempDirs = [];

afterEach(async () => {
  await Promise.all(
    tempDirs.map((dir) => rm(dir, { force: true, recursive: true })),
  );
  tempDirs = [];
});

describe("workspace data deletion targets", () => {
  it("returns only Plato-owned metadata roots that exist", async () => {
    const workspace = await tempDir();
    await mkdir(path.join(workspace, ".plato"));
    await mkdir(path.join(workspace, ".taskweavn"));
    await mkdir(path.join(workspace, "src"));

    await expect(resolveWorkspaceDataTargets(workspace)).resolves.toEqual([
      path.join(workspace, ".plato"),
      path.join(workspace, ".taskweavn"),
    ]);
  });

  it("rejects symlinked metadata roots", async () => {
    const workspace = await tempDir();
    const outside = await tempDir();
    await symlink(outside, path.join(workspace, ".plato"));

    await expect(resolveWorkspaceDataTargets(workspace)).rejects.toBeInstanceOf(
      WorkspaceDataDeletionError,
    );
  });
});

async function tempDir() {
  const dir = await mkdtemp(path.join(os.tmpdir(), "plato-workspace-data-"));
  tempDirs.push(dir);
  return dir;
}
