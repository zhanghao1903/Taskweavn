import { spawn } from "node:child_process";
import {
  chmodSync,
  constants,
  accessSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  rmSync,
} from "node:fs";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";

export const APP_CONTROL_SERVICE_MANIFEST_SCHEMA =
  "plato.app_control.service_manifest.v1";

const DEFAULT_TIMEOUT_MS = 90_000;
const DEFAULT_POLL_INTERVAL_MS = 250;

export class ComputerUseHelperStartupError extends Error {
  constructor(message, diagnostics = {}) {
    super(message);
    this.name = "ComputerUseHelperStartupError";
    this.diagnostics = diagnostics;
  }
}

export async function startComputerUseHelper({
  allowedAppBundleIds = {},
  allowedApps = [],
  allowCoordinateClick = false,
  appPath,
  bundleId,
  killProcess = process.kill,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
  runtimeRoot,
  screenRecordingRequired = false,
  spawnProcess = spawn,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  toolTimeoutMs = 10_000,
  validateEndpoint = isUnixSocket,
}) {
  const resolvedAppPath = path.resolve(appPath);
  const resolvedRuntimeRoot = path.resolve(runtimeRoot);
  try {
    accessSync(resolvedAppPath, constants.R_OK);
  } catch {
    throw new ComputerUseHelperStartupError(
      `helper_app_missing: ${resolvedAppPath}`,
      { appPath: resolvedAppPath, failureKind: "helper_app_missing" },
    );
  }

  mkdirSync(resolvedRuntimeRoot, { recursive: true, mode: 0o700 });
  chmodSync(resolvedRuntimeRoot, 0o700);
  const socketPath = path.join(resolvedRuntimeRoot, "app-control.sock");
  const tokenPath = path.join(resolvedRuntimeRoot, "app-control.token");
  const manifestPath = path.join(resolvedRuntimeRoot, "app-control-service.json");
  cleanupRuntimePaths({ manifestPath, socketPath, tokenPath });

  const launchArgs = buildHelperLaunchArgs({
    allowedAppBundleIds,
    allowedApps,
    allowCoordinateClick,
    appPath: resolvedAppPath,
    bundleId,
    manifestPath,
    screenRecordingRequired,
    socketPath,
    timeoutMs: toolTimeoutMs,
    tokenPath,
  });
  const stderr = [];
  let exited = null;
  let spawnError = null;
  const launcher = spawnProcess("/usr/bin/open", launchArgs, {
    env: process.env,
    stdio: ["ignore", "ignore", "pipe"],
  });
  launcher.stderr?.on("data", (chunk) => stderr.push(String(chunk)));
  launcher.once("error", (error) => {
    spawnError = error;
  });
  launcher.once("exit", (code, signal) => {
    exited = { code, signal };
  });

  let manifest;
  try {
    manifest = await waitForHelperManifest({
      bundleId,
      getExited: () => exited,
      getSpawnError: () => spawnError,
      manifestPath,
      pollIntervalMs,
      timeoutMs,
      validateEndpoint,
    });
  } catch (error) {
    cleanupRuntimePaths({ manifestPath, socketPath, tokenPath });
    throw new ComputerUseHelperStartupError(
      error instanceof Error ? error.message : "Helper did not become ready.",
      {
        appPath: resolvedAppPath,
        bundleId,
        failureKind: "helper_start_failed",
        launcherExit: exited,
        stderr: stderr.join("").slice(-4000),
      },
    );
  }

  let stopped = false;
  return {
    appPath: resolvedAppPath,
    bundleId,
    manifest,
    manifestPath,
    pid: manifest.pid,
    stop() {
      if (stopped) {
        return;
      }
      stopped = true;
      stopHelperProcess({ killProcess, pid: manifest.pid });
      cleanupRuntimePaths({ manifestPath, socketPath, tokenPath });
    },
  };
}

export function buildHelperLaunchArgs({
  allowedAppBundleIds,
  allowedApps,
  allowCoordinateClick,
  appPath,
  bundleId,
  manifestPath,
  screenRecordingRequired,
  socketPath,
  timeoutMs,
  tokenPath,
}) {
  const args = [
    "-n",
    appPath,
    "--args",
    "--socket-path",
    socketPath,
    "--token-path",
    tokenPath,
    "--manifest-path",
    manifestPath,
    "--bundle-id",
    bundleId,
    "--app-path",
    appPath,
    "--allowed-apps",
    allowedApps.join(","),
    "--timeout-ms",
    String(timeoutMs),
  ];
  if (Object.keys(allowedAppBundleIds).length > 0) {
    args.push(
      "--allowed-app-bundle-ids-json",
      JSON.stringify(allowedAppBundleIds),
    );
  }
  if (allowCoordinateClick) {
    args.push("--allow-coordinate-click");
  }
  if (screenRecordingRequired) {
    args.push("--screen-recording-required");
  }
  return args;
}

export function readAndValidateHelperManifest(
  manifestPath,
  { bundleId, validateEndpoint = isUnixSocket },
) {
  let payload;
  try {
    payload = JSON.parse(readFileSync(manifestPath, "utf8"));
  } catch {
    return null;
  }
  if (
    payload?.schema !== APP_CONTROL_SERVICE_MANIFEST_SCHEMA ||
    payload?.transport !== "unix_socket" ||
    payload?.bundleId !== bundleId ||
    !Number.isInteger(payload?.pid) ||
    payload.pid <= 0 ||
    typeof payload?.endpoint !== "string" ||
    typeof payload?.tokenPath !== "string"
  ) {
    return null;
  }
  if (!existsSync(payload.tokenPath)) {
    return null;
  }
  if (!validateEndpoint(payload.endpoint)) {
    return null;
  }
  return payload;
}

export function cleanupRuntimePaths({ manifestPath, socketPath, tokenPath }) {
  for (const runtimePath of [manifestPath, socketPath, tokenPath]) {
    rmSync(runtimePath, { force: true });
  }
}

export function stopHelperProcess({ killProcess = process.kill, pid }) {
  if (!Number.isInteger(pid) || pid <= 1) {
    return;
  }
  try {
    killProcess(pid, "SIGTERM");
  } catch {
    return;
  }
  setTimeout(() => {
    try {
      killProcess(pid, "SIGKILL");
    } catch {
      // The Helper normally exits after SIGTERM.
    }
  }, 2_000).unref();
}

async function waitForHelperManifest({
  bundleId,
  getExited,
  getSpawnError,
  manifestPath,
  pollIntervalMs,
  timeoutMs,
  validateEndpoint,
}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const spawnError = getSpawnError();
    if (spawnError !== null) {
      throw new Error(`Helper launcher failed: ${spawnError.message}`);
    }
    const exited = getExited();
    if (exited !== null && exited.code !== 0) {
      throw new Error(
        `Helper launcher exited: code=${exited.code ?? "null"} signal=${
          exited.signal ?? "null"
        }`,
      );
    }
    const manifest = readAndValidateHelperManifest(manifestPath, {
      bundleId,
      validateEndpoint,
    });
    if (manifest !== null) {
      return manifest;
    }
    await delay(pollIntervalMs);
  }
  throw new Error(`Timed out waiting for Helper manifest: ${manifestPath}`);
}

function isUnixSocket(endpoint) {
  try {
    return lstatSync(endpoint).isSocket();
  } catch {
    return false;
  }
}
