import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getWorkspaceGitStatus,
  prepareWorkspaceGit,
  safeWorkspaceGitPreparationMessage,
  WorkspaceGitPreparationError,
} from "./workspaceGit.mjs";

let tempDirs = [];

afterEach(async () => {
  await Promise.all(
    tempDirs.map((dir) => rm(dir, { force: true, recursive: true })),
  );
  tempDirs = [];
});

describe("workspace Git preparation", () => {
  it("reports available Git without exposing command details", async () => {
    const execFile = vi.fn(async () => ({
      stderr: "",
      stdout: "git version 2.45.0\n",
    }));

    await expect(getWorkspaceGitStatus({ execFile })).resolves.toEqual({
      status: "available",
      version: "git version 2.45.0",
    });
    expect(execFile).toHaveBeenCalledWith(
      "git",
      ["--version"],
      expect.objectContaining({ shell: false }),
    );
  });

  it("reports missing Git safely", async () => {
    const execFile = vi.fn(async () => {
      const error = new Error("spawn git ENOENT");
      error.code = "ENOENT";
      throw error;
    });

    await expect(getWorkspaceGitStatus({ execFile })).resolves.toEqual({
      status: "missing",
    });
  });

  it("initializes a plain workspace and writes .plato to local Git exclude", async () => {
    const workspacePath = await tempDir();
    const execFile = vi.fn(async (_command, args) => {
      if (args.join(" ") === "--version") {
        return { stderr: "", stdout: "git version 2.45.0\n" };
      }
      if (args.includes("--is-inside-work-tree")) {
        const error = new Error("not a git repository");
        error.code = 128;
        throw error;
      }
      if (args.includes("init")) {
        return { stderr: "", stdout: "Initialized empty Git repository\n" };
      }
      if (args.includes("--git-path")) {
        return { stderr: "", stdout: ".git/info/exclude\n" };
      }
      throw new Error(`unexpected git args: ${args.join(" ")}`);
    });

    await expect(prepareWorkspaceGit(workspacePath, { execFile })).resolves.toEqual({
      excludeUpdated: true,
      initialized: true,
      status: "ready",
    });

    expect(execFile).toHaveBeenCalledWith(
      "git",
      ["-C", workspacePath, "init"],
      expect.objectContaining({ shell: false }),
    );
    await expect(
      readFile(path.join(workspacePath, ".git", "info", "exclude"), "utf8"),
    ).resolves.toContain(".plato/");
  });

  it("does not reinitialize an existing repository or duplicate the exclude rule", async () => {
    const workspacePath = await tempDir();
    await writeFile(
      path.join(await mkdirp(workspacePath, ".git", "info"), "exclude"),
      "# local excludes\n.plato/\n",
      "utf8",
    );
    const execFile = vi.fn(async (_command, args) => {
      if (args.join(" ") === "--version") {
        return { stderr: "", stdout: "git version 2.45.0\n" };
      }
      if (args.includes("--is-inside-work-tree")) {
        return { stderr: "", stdout: "true\n" };
      }
      if (args.includes("--git-path")) {
        return { stderr: "", stdout: ".git/info/exclude\n" };
      }
      throw new Error(`unexpected git args: ${args.join(" ")}`);
    });

    const result = await prepareWorkspaceGit(workspacePath, { execFile });

    expect(result).toEqual({
      excludeUpdated: false,
      initialized: false,
      status: "ready",
    });
    expect(execFile).not.toHaveBeenCalledWith(
      "git",
      ["-C", workspacePath, "init"],
      expect.anything(),
    );
    const exclude = await readFile(
      path.join(workspacePath, ".git", "info", "exclude"),
      "utf8",
    );
    expect(exclude.match(/\.plato\//gu)).toHaveLength(1);
  });

  it("maps Git failures to safe product messages", async () => {
    const workspacePath = await tempDir();
    const execFile = vi.fn(async () => {
      const error = new Error(`raw failure in ${workspacePath}`);
      error.code = "ENOENT";
      throw error;
    });

    await expect(prepareWorkspaceGit(workspacePath, { execFile })).rejects.toThrow(
      WorkspaceGitPreparationError,
    );

    try {
      await prepareWorkspaceGit(workspacePath, { execFile });
    } catch (error) {
      const message = safeWorkspaceGitPreparationMessage(error);
      expect(message).toBe(
        "Git not found. Install Git to enable automatic workspace initialization.",
      );
      expect(message).not.toContain(workspacePath);
      expect(message).not.toContain("raw failure");
    }
  });
});

async function tempDir() {
  const dir = await mkdtemp(path.join(os.tmpdir(), "plato-workspace-git-"));
  tempDirs.push(dir);
  return dir;
}

async function mkdirp(...segments) {
  const dir = path.join(...segments);
  await mkdir(dir, { recursive: true });
  return dir;
}
