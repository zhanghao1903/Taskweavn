import { spawn } from "node:child_process";
import { constants, accessSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";

import {
  buildStartupDiagnostics,
  createStartupLogBuffer,
} from "./startupDiagnostics.mjs";
import { markStartupTiming } from "./startupTiming.mjs";

const DEFAULT_HOST = "127.0.0.1";
const DEFAULT_TIMEOUT_MS = 20_000;
const DEFAULT_POLL_INTERVAL_MS = 250;

export class SidecarStartupError extends Error {
  constructor(message, diagnostics) {
    super(message);
    this.name = "SidecarStartupError";
    this.diagnostics = diagnostics;
  }
}

export async function startPythonSidecar({
  appVersion,
  electronVersion,
  env = process.env,
  fetchHealth = defaultFetchHealth,
  findPort = findAvailablePort,
  healthPollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
  host = DEFAULT_HOST,
  launcherEnv = {},
  launcherNodePath = process.execPath,
  launcherPath = null,
  repoRoot,
  spawnProcess = spawn,
  startupId,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  validateLauncher = true,
  workspaceRegistry = [],
  workspaceRoot,
}) {
  const resolvedWorkspaceRoot = path.resolve(workspaceRoot);
  const resolvedWorkspaceRegistry = workspaceRegistry.map((entry) => ({
    ...entry,
    rootPath: path.resolve(entry.rootPath),
  }));
  const resolvedLauncherPath = launcherPath === null ? null : path.resolve(launcherPath);
  const resolvedRepoRoot =
    repoRoot === undefined || repoRoot === null ? null : path.resolve(repoRoot);
  const launchMode = resolvedLauncherPath === null ? "repo" : "launcher";
  markStartupTiming("electron_sidecar_process_start_begin", {
    startupId,
    launchMode,
  });
  const port = await findPort(host);
  markStartupTiming("electron_sidecar_port_selected", {
    startupId,
    launchMode,
    port,
  });
  const baseUrl = `http://${host}:${port}`;
  const healthUrl = `${baseUrl}/api/v1/health`;
  const redactionPaths = [
    resolvedWorkspaceRoot,
    ...resolvedWorkspaceRegistry.map((entry) => entry.rootPath),
    resolvedRepoRoot,
    resolvedLauncherPath === null ? null : path.dirname(resolvedLauncherPath),
  ].filter(Boolean);
  const stdout = createStartupLogBuffer({ redactionPaths });
  const stderr = createStartupLogBuffer({ redactionPaths });
  const stdoutStartupTiming = createStartupTimingForwarder();
  const launch = buildLaunchCommand({
    appVersion,
    env,
    host,
    launcherEnv,
    launcherNodePath,
    launcherPath: resolvedLauncherPath,
    port,
    repoRoot: resolvedRepoRoot,
    startupId,
    validateLauncher,
    workspaceRegistry: resolvedWorkspaceRegistry,
    workspaceRoot: resolvedWorkspaceRoot,
  });
  let exited = null;
  let spawnError = null;

  if (launch.diagnostics !== null) {
    markStartupTiming("electron_sidecar_launch_invalid", {
      startupId,
      launchMode,
    });
    throw new SidecarStartupError(launch.diagnostics.message, launch.diagnostics);
  }

  markStartupTiming("electron_sidecar_spawn_begin", {
    startupId,
    launchMode,
    port,
  });
  const child = spawnProcess(launch.command, launch.args, {
    cwd: launch.cwd,
    env: launch.env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  markStartupTiming("electron_sidecar_spawned", {
    startupId,
    launchMode,
    pid: child.pid ?? null,
    port,
  });

  child.stdout?.on("data", (chunk) => {
    stdout.append(chunk);
    stdoutStartupTiming.append(chunk);
  });
  child.stderr?.on("data", (chunk) => stderr.append(chunk));
  child.once("error", (error) => {
    spawnError = error;
  });
  child.once("exit", (code, signal) => {
    exited = { code, signal };
  });

  try {
    await waitForHealth({
      child,
      fetchHealth,
      healthPollIntervalMs,
      healthUrl,
      timeoutMs,
      getExited: () => exited,
      getSpawnError: () => spawnError,
    });
    markStartupTiming("electron_sidecar_health_ready", {
      startupId,
      launchMode,
      pid: child.pid ?? null,
      port,
    });
  } catch (error) {
    markStartupTiming("electron_sidecar_health_failed", {
      startupId,
      launchMode,
      pid: child.pid ?? null,
      port,
    });
    const diagnostics = buildStartupDiagnostics({
      appVersion,
      baseUrl,
      electronVersion,
      exitCode: exited?.code ?? child.exitCode ?? null,
      healthUrl,
      message:
        error instanceof Error
          ? error.message
          : "The Python sidecar did not become ready.",
      pid: child.pid ?? null,
      signal: exited?.signal ?? child.signalCode ?? null,
      startupId,
      status: "sidecar_failed",
      stderr: stderr.snapshot(),
      stdout: stdout.snapshot(),
      timeoutMs,
    });
    stopSidecarProcess({ child });
    throw new SidecarStartupError(diagnostics.message, diagnostics);
  }

  return {
    baseUrl,
    diagnostics: buildStartupDiagnostics({
      appVersion,
      baseUrl,
      electronVersion,
      healthUrl,
      message: "The Python sidecar is ready.",
      pid: child.pid ?? null,
      startupId,
      status: "ready",
      stderr: stderr.snapshot(),
      stdout: stdout.snapshot(),
      timeoutMs,
    }),
    healthUrl,
    pid: child.pid ?? null,
    process: child,
    stop() {
      stopSidecarProcess({ child });
    },
  };
}

export function buildSidecarArgs({ host, port, workspaceRegistry = [], workspaceRoot }) {
  const args = [
    "run",
    "taskweavn",
    "plato-sidecar",
    "--workspace",
    workspaceRoot,
    "--host",
    host,
    "--port",
    String(port),
  ];
  if (workspaceRegistry.length > 0) {
    args.push("--workspace-registry-json", JSON.stringify(workspaceRegistry));
  }
  return args;
}

export function buildLauncherSidecarArgs({
  host,
  port,
  workspaceRegistry = [],
  workspaceRoot,
}) {
  const args = [
    "--workspace",
    workspaceRoot,
    "--host",
    host,
    "--port",
    String(port),
  ];
  if (workspaceRegistry.length > 0) {
    args.push("--workspace-registry-json", JSON.stringify(workspaceRegistry));
  }
  return args;
}

function buildLaunchCommand({
  appVersion,
  env,
  host,
  launcherEnv,
  launcherNodePath,
  launcherPath,
  port,
  repoRoot,
  startupId,
  validateLauncher,
  workspaceRegistry,
  workspaceRoot,
}) {
  if (launcherPath !== null) {
    const startupEnv = buildStartupProcessEnv(env, startupId);
    if (validateLauncher) {
      try {
        accessSync(launcherPath, constants.X_OK);
      } catch {
        return {
          diagnostics: buildStartupDiagnostics({
            appVersion,
            baseUrl: `http://${host}:${port}`,
            healthUrl: `http://${host}:${port}/api/v1/health`,
            message: "launcher_missing: packaged sidecar launcher is missing or not executable.",
            startupId,
            status: "sidecar_failed",
            stderr: ["launcher_missing: packaged sidecar launcher is missing or not executable."],
          }),
        };
      }
    }
    return {
      args: [
        launcherPath,
        ...buildLauncherSidecarArgs({
          host,
          port,
          workspaceRegistry,
          workspaceRoot,
        }),
      ],
      command: launcherNodePath,
      cwd: path.dirname(launcherPath),
      diagnostics: null,
      env: {
        ...env,
        ...launcherEnv,
        ELECTRON_RUN_AS_NODE: "1",
        ...startupEnv,
      },
    };
  }

  if (repoRoot === null) {
    return {
      diagnostics: buildStartupDiagnostics({
        appVersion,
        baseUrl: `http://${host}:${port}`,
        healthUrl: `http://${host}:${port}/api/v1/health`,
        message: "repo_runtime_missing: repository runtime root is required without a sidecar launcher.",
        startupId,
        status: "sidecar_failed",
        stderr: ["repo_runtime_missing: repository runtime root is required without a sidecar launcher."],
      }),
    };
  }

  return {
    args: buildSidecarArgs({ host, port, workspaceRegistry, workspaceRoot }),
    command: "uv",
    cwd: repoRoot,
    diagnostics: null,
    env: {
      ...env,
      ...buildStartupProcessEnv(env, startupId),
    },
  };
}

function buildStartupProcessEnv(env, startupId) {
  return {
    PLATO_STARTUP_ID: startupId,
    PLATO_STARTUP_PARENT_EPOCH_MS:
      env.PLATO_STARTUP_PARENT_EPOCH_MS ?? String(Date.now()),
  };
}

function createStartupTimingForwarder() {
  let pending = "";
  return {
    append(chunk) {
      pending += Buffer.isBuffer(chunk) ? chunk.toString("utf8") : String(chunk);
      const lines = pending.split(/\r?\n/);
      pending = lines.pop() ?? "";
      for (const line of lines) {
        if (line.startsWith("[plato-startup-timing] ")) {
          console.log(line);
        }
      }
    },
  };
}

export async function findAvailablePort(host = DEFAULT_HOST) {
  return await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, host, () => {
      const address = server.address();
      const port =
        typeof address === "object" && address !== null ? address.port : null;
      server.close(() => {
        if (port === null) {
          reject(new Error("could not resolve an available sidecar port"));
          return;
        }
        resolve(port);
      });
    });
  });
}

export function stopSidecarProcess({ child }) {
  if (!child || child.exitCode !== null || child.signalCode !== null) {
    return;
  }
  child.kill("SIGINT");
  setTimeout(() => {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill("SIGKILL");
    }
  }, 2_000).unref();
}

async function waitForHealth({
  fetchHealth,
  healthPollIntervalMs,
  healthUrl,
  timeoutMs,
  getExited,
  getSpawnError,
}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const spawnError = getSpawnError();
    if (spawnError !== null) {
      throw new Error(
        `Sidecar launcher failed before readiness: ${spawnError.message}`,
      );
    }

    const exited = getExited();
    if (exited !== null) {
      throw new Error(
        `Python sidecar exited before readiness: code=${exited.code ?? "null"} signal=${
          exited.signal ?? "null"
        }`,
      );
    }

    try {
      if (await fetchHealth(healthUrl)) {
        return;
      }
    } catch {
      // Health polling is intentionally tolerant until timeout or process exit.
    }

    await delay(healthPollIntervalMs);
  }
  throw new Error(`Timed out waiting for Python sidecar health at ${healthUrl}`);
}

async function defaultFetchHealth(healthUrl) {
  const response = await fetch(healthUrl, {
    signal: AbortSignal.timeout(1_000),
  });
  return response.ok;
}
