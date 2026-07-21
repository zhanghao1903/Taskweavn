import path from "node:path";

import { startComputerUseHelper } from "./computerUseHelperProcess.mjs";

const DEV_BUNDLE_ID = "com.taskweavn.plato.computer-use-helper.dev";
const RELEASE_BUNDLE_ID = "com.taskweavn.plato.computer-use-helper";
const DEV_APP_NAME = "Plato Computer Use Helper Dev.app";
const RELEASE_APP_NAME = "Plato Computer Use Helper.app";

export function createComputerUseHelperManager({
  app,
  env = process.env,
  platform = process.platform,
  resourcesPath = process.resourcesPath,
  startHelper = startComputerUseHelper,
}) {
  let launchAttempted = false;
  let runtime = null;
  let startupFailure = null;

  function requestedBackend() {
    const configured = (env.PLATO_COMPUTER_USE_BACKEND ?? "")
      .trim()
      .toLowerCase();
    if (["disabled", "none", "off"].includes(configured)) {
      return "disabled";
    }
    if (platform === "darwin") {
      return "helper";
    }
    return "disabled";
  }

  function allowedApps() {
    const configured = parseAllowedApps(env.PLATO_COMPUTER_USE_ALLOWED_APPS);
    if (configured.length > 0) {
      return configured;
    }
    return requestedBackend() === "helper" && platform === "darwin"
      ? ["WeChat"]
      : [];
  }

  function allowCoordinateClick() {
    const configured = env.PLATO_COMPUTER_USE_ALLOW_COORDINATE_CLICK;
    return configured === undefined ? true : parseBoolean(configured);
  }

  function resolvePaths() {
    const runtimeRoot = path.join(app.getPath("userData"), "computer-use-helper");
    const manifestPath = path.join(runtimeRoot, "app-control-service.json");
    const bundleId =
      env.PLATO_COMPUTER_USE_HELPER_BUNDLE_ID ??
      (app.isPackaged ? RELEASE_BUNDLE_ID : DEV_BUNDLE_ID);
    const defaultAppPath = app.isPackaged
      ? path.resolve(
          resourcesPath,
          "..",
          "Library",
          "LoginItems",
          RELEASE_APP_NAME,
        )
      : path.join(app.getPath("home"), "Applications", DEV_APP_NAME);
    return {
      appPath: env.PLATO_COMPUTER_USE_HELPER_APP_PATH ?? defaultAppPath,
      bundleId,
      manifestPath,
      runtimeRoot,
    };
  }

  async function ensureStarted() {
    if (requestedBackend() !== "helper" || launchAttempted) {
      return snapshot();
    }
    launchAttempted = true;
    const paths = resolvePaths();
    try {
      runtime = await startHelper({
        allowedAppBundleIds: parseBundleIds(
          env.PLATO_COMPUTER_USE_ALLOWED_APP_BUNDLE_IDS_JSON,
          allowedApps(),
        ),
        allowedApps: allowedApps(),
        allowCoordinateClick: allowCoordinateClick(),
        appPath: paths.appPath,
        bundleId: paths.bundleId,
        runtimeRoot: paths.runtimeRoot,
        screenRecordingRequired: parseBoolean(
          env.PLATO_COMPUTER_USE_SCREEN_RECORDING_REQUIRED,
        ),
        timeoutMs: positiveInteger(
          env.PLATO_COMPUTER_USE_HELPER_STARTUP_TIMEOUT_MS,
          90_000,
        ),
        toolTimeoutMs: positiveInteger(
          env.PLATO_COMPUTER_USE_TIMEOUT_MS,
          10_000,
        ),
      });
    } catch (error) {
      startupFailure = {
        failureKind:
          error?.diagnostics?.failureKind ?? "helper_start_failed",
        message:
          error instanceof Error ? error.message : "Computer Use Helper failed.",
      };
      console.error(
        `[plato-computer-use-helper] ${startupFailure.failureKind}: ${startupFailure.message}`,
      );
    }
    return snapshot();
  }

  function buildSidecarEnv() {
    const sidecarEnv = { ...env };
    if (requestedBackend() === "helper") {
      sidecarEnv.PLATO_COMPUTER_USE_BACKEND = "helper";
      sidecarEnv.PLATO_COMPUTER_USE_ALLOWED_APPS = allowedApps().join(",");
      sidecarEnv.PLATO_COMPUTER_USE_ALLOW_COORDINATE_CLICK = String(
        allowCoordinateClick(),
      );
      sidecarEnv.PLATO_COMPUTER_USE_HELPER_MANIFEST =
        runtime?.manifestPath ?? resolvePaths().manifestPath;
      if (startupFailure !== null) {
        sidecarEnv.PLATO_COMPUTER_USE_HELPER_STARTUP_FAILURE = JSON.stringify(
          startupFailure,
        );
      }
    } else if (env.PLATO_COMPUTER_USE_BACKEND !== undefined) {
      sidecarEnv.PLATO_COMPUTER_USE_BACKEND = "disabled";
    }
    return sidecarEnv;
  }

  function stop() {
    runtime?.stop();
    runtime = null;
  }

  function snapshot() {
    return {
      available: runtime !== null,
      launchAttempted,
      manifestPath:
        requestedBackend() === "helper"
          ? runtime?.manifestPath ?? resolvePaths().manifestPath
          : null,
      startupFailure,
    };
  }

  return {
    buildSidecarEnv,
    ensureStarted,
    snapshot,
    stop,
  };
}

function parseAllowedApps(raw) {
  if (!raw) {
    return [];
  }
  return raw
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function parseBundleIds(raw, allowedApps) {
  if (raw) {
    try {
      const payload = JSON.parse(raw);
      if (
        payload &&
        typeof payload === "object" &&
        !Array.isArray(payload) &&
        Object.values(payload).every((value) => typeof value === "string")
      ) {
        return payload;
      }
    } catch {
      // Invalid diagnostics input falls back to the bounded product default.
    }
  }
  return allowedApps.includes("WeChat")
    ? { WeChat: "com.tencent.xinWeChat" }
    : {};
}

function parseBoolean(raw) {
  return ["1", "true", "yes", "on"].includes(String(raw ?? "").toLowerCase());
}

function positiveInteger(raw, fallback) {
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : fallback;
}
