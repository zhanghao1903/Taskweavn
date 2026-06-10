import { execFile } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const PLATO_GIT_EXCLUDE_RULE = ".plato/";

export class WorkspaceGitPreparationError extends Error {
  constructor(code, safeMessage) {
    super(safeMessage);
    this.name = "WorkspaceGitPreparationError";
    this.code = code;
    this.safeMessage = safeMessage;
  }
}

export async function getWorkspaceGitStatus(options = {}) {
  try {
    const result = await runGit(["--version"], options);
    return {
      status: "available",
      version: safeGitVersion(result.stdout),
    };
  } catch (error) {
    if (error?.code === "ENOENT") {
      return { status: "missing" };
    }
    return { status: "failed" };
  }
}

export async function prepareWorkspaceGit(workspacePath, options = {}) {
  const gitStatus = await getWorkspaceGitStatus(options);
  if (gitStatus.status === "missing") {
    throw new WorkspaceGitPreparationError(
      "git_missing",
      "Git not found. Install Git to enable automatic workspace initialization.",
    );
  }
  if (gitStatus.status !== "available") {
    throw new WorkspaceGitPreparationError(
      "git_failed",
      "Git availability check failed.",
    );
  }

  const normalizedWorkspacePath = path.resolve(workspacePath);
  const insideWorkTree = await isInsideWorkTree(normalizedWorkspacePath, options);
  let initialized = false;
  if (!insideWorkTree) {
    try {
      await runGit(["-C", normalizedWorkspacePath, "init"], options);
      initialized = true;
    } catch {
      throw new WorkspaceGitPreparationError(
        "git_init_failed",
        "Could not initialize Git for that workspace.",
      );
    }
  }

  try {
    const excludePath = await resolveGitExcludePath(
      normalizedWorkspacePath,
      options,
    );
    const excludeUpdated = await ensurePlatoGitExclude(excludePath, options);
    return {
      excludeUpdated,
      initialized,
      status: "ready",
    };
  } catch (error) {
    if (error instanceof WorkspaceGitPreparationError) {
      throw error;
    }
    throw new WorkspaceGitPreparationError(
      "git_exclude_failed",
      "Could not update Git exclude rules for that workspace.",
    );
  }
}

export function safeWorkspaceGitPreparationMessage(error) {
  return error instanceof WorkspaceGitPreparationError
    ? error.safeMessage
    : "Could not initialize Git for that workspace.";
}

async function isInsideWorkTree(workspacePath, options) {
  try {
    const result = await runGit(
      ["-C", workspacePath, "rev-parse", "--is-inside-work-tree"],
      options,
    );
    return result.stdout.trim() === "true";
  } catch {
    return false;
  }
}

async function resolveGitExcludePath(workspacePath, options) {
  const result = await runGit(
    ["-C", workspacePath, "rev-parse", "--git-path", "info/exclude"],
    options,
  );
  const rawPath = result.stdout.trim();
  if (!rawPath) {
    throw new WorkspaceGitPreparationError(
      "git_exclude_failed",
      "Could not update Git exclude rules for that workspace.",
    );
  }
  return path.isAbsolute(rawPath) ? rawPath : path.resolve(workspacePath, rawPath);
}

async function ensurePlatoGitExclude(excludePath, options) {
  const fsApi = resolveFsApi(options);
  let current = "";
  try {
    current = await fsApi.readFile(excludePath, "utf8");
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw error;
    }
  }

  if (
    current
      .split(/\r?\n/u)
      .map((line) => line.trim())
      .includes(PLATO_GIT_EXCLUDE_RULE)
  ) {
    return false;
  }

  await fsApi.mkdir(path.dirname(excludePath), { recursive: true });
  const prefix = current.length > 0 && !current.endsWith("\n") ? "\n" : "";
  await fsApi.writeFile(
    excludePath,
    `${current}${prefix}${PLATO_GIT_EXCLUDE_RULE}\n`,
    "utf8",
  );
  return true;
}

async function runGit(args, options) {
  const runner = options.execFile ?? execFileAsync;
  return await runner("git", args, {
    maxBuffer: 64_000,
    shell: false,
    timeout: 10_000,
    windowsHide: true,
  });
}

function resolveFsApi(options) {
  return {
    mkdir: options.mkdir ?? mkdir,
    readFile: options.readFile ?? readFile,
    writeFile: options.writeFile ?? writeFile,
  };
}

function safeGitVersion(stdout) {
  const firstLine = String(stdout ?? "").split(/\r?\n/u)[0]?.trim() ?? "";
  if (/^git version [0-9A-Za-z.+\- ()/_]{1,80}$/u.test(firstLine)) {
    return firstLine;
  }
  return "git available";
}
