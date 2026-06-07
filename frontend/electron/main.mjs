import { app, BrowserWindow, ipcMain, shell } from "electron";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { startPythonSidecar } from "./sidecarProcess.mjs";
import {
  buildStartupDiagnostics,
  createStartupId,
  startupDiagnosticsDataUrl,
} from "./startupDiagnostics.mjs";
import { resolveElectronWorkspaceRoot } from "./workspacePaths.mjs";

const electronDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(electronDir, "..");
const repoRoot = path.resolve(frontendRoot, "..");
const preloadPath = path.join(electronDir, "preload.mjs");

const startupId = createStartupId();
const appVersion = process.env.npm_package_version ?? "0.1.0";
let mainWindow = null;
let sidecarRuntime = null;
let lastStartupDiagnostics = null;

app.name = "Plato";
if (process.env.PLATO_ELECTRON_USER_DATA_DIR) {
  app.setPath("userData", process.env.PLATO_ELECTRON_USER_DATA_DIR);
}
if (process.env.PLATO_ELECTRON_SMOKE === "1") {
  app.disableHardwareAcceleration();
}

ipcMain.handle("plato:get-startup-diagnostics", () => lastStartupDiagnostics);

app.whenReady().then(async () => {
  app.on("web-contents-created", (_event, contents) => {
    contents.setWindowOpenHandler(({ url }) => {
      if (url.startsWith("https://") || url.startsWith("http://")) {
        void shell.openExternal(url);
      }
      return { action: "deny" };
    });
  });

  mainWindow = createMainWindow();
  await showStartupDiagnostics({
    message: "Starting the local Python sidecar.",
    status: "starting_sidecar",
  });

  try {
    sidecarRuntime = await resolveSidecarRuntime();
    setRendererRuntimeConfig({
      apiBaseUrl: sidecarRuntime.baseUrl,
      apiMode: "http",
      appVersion,
      disableEvents: process.env.PLATO_ELECTRON_DISABLE_EVENTS === "1",
      sessionId: null,
      startupId,
    });
    await loadRenderer(mainWindow);
    await runSmokeIfRequested();
  } catch (error) {
    const diagnostics =
      error && typeof error === "object" && "diagnostics" in error
        ? error.diagnostics
        : buildStartupDiagnostics({
            appVersion,
            electronVersion: process.versions.electron ?? "unknown",
            message: "The local Python sidecar could not start.",
            startupId,
            status: "sidecar_failed",
          });
    await showStartupDiagnostics(diagnostics);
    await runStartupDiagnosticsSmokeIfRequested();
    exitUnexpectedStartupFailureSmokeIfRequested();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    mainWindow = createMainWindow();
    void restoreWindowContent();
  }
});

app.on("before-quit", () => {
  sidecarRuntime?.stop();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

function createMainWindow() {
  const window = new BrowserWindow({
    backgroundColor: "#eef5f8",
    height: 900,
    minHeight: 720,
    minWidth: 1024,
    show: false,
    title: "Plato",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: preloadPath,
      sandbox: false,
    },
    width: 1280,
  });

  window.once("ready-to-show", () => {
    window.show();
    if (process.env.PLATO_ELECTRON_OPEN_DEVTOOLS === "1") {
      window.webContents.openDevTools({ mode: "detach" });
    }
  });

  return window;
}

async function showStartupDiagnostics(input) {
  lastStartupDiagnostics =
    typeof input.status === "string" && typeof input.message === "string"
      ? buildStartupDiagnostics({
          appVersion,
          electronVersion: process.versions.electron ?? "unknown",
          startupId,
          ...input,
        })
      : input;
  setRendererRuntimeConfig({
    apiMode: "mock",
    appVersion,
    startupId,
    startupDiagnostics: lastStartupDiagnostics,
  });
  await mainWindow?.loadURL(startupDiagnosticsDataUrl(lastStartupDiagnostics));
}

async function loadRenderer(window) {
  const rendererUrl = process.env.PLATO_ELECTRON_RENDERER_URL;
  if (rendererUrl) {
    await window.loadURL(rendererUrl);
    return;
  }

  await window.loadURL(
    pathToFileURL(path.join(frontendRoot, "dist", "index.html")).toString(),
  );
}

function setRendererRuntimeConfig(config) {
  process.env.PLATO_ELECTRON_RUNTIME_CONFIG = JSON.stringify(config);
}

async function resolveSidecarRuntime() {
  const externalBaseUrl = process.env.PLATO_ELECTRON_SIDECAR_BASE_URL;
  if (externalBaseUrl) {
    return {
      baseUrl: externalBaseUrl,
      diagnostics: buildStartupDiagnostics({
        appVersion,
        baseUrl: externalBaseUrl,
        electronVersion: process.versions.electron ?? "unknown",
        healthUrl: `${externalBaseUrl.replace(/\/$/, "")}/api/v1/health`,
        message: "Using seeded external sidecar for Electron smoke.",
        startupId,
        status: "ready",
      }),
      healthUrl: `${externalBaseUrl.replace(/\/$/, "")}/api/v1/health`,
      pid: null,
      process: null,
      stop() {
        return undefined;
      },
    };
  }

  const sidecarLauncherPath = resolveSidecarLauncherPath();
  const workspaceRoot = resolveElectronWorkspaceRoot({
    env: process.env,
    isPackaged: app.isPackaged,
    repoRoot,
    sidecarLauncherPath,
    userDataPath: app.getPath("userData"),
  });
  return await startPythonSidecar({
    appVersion,
    electronVersion: process.versions.electron ?? "unknown",
    launcherPath: sidecarLauncherPath,
    repoRoot:
      sidecarLauncherPath === null
        ? process.env.PLATO_ELECTRON_REPO_ROOT ?? repoRoot
        : null,
    startupId,
    timeoutMs: Number(process.env.PLATO_ELECTRON_SIDECAR_TIMEOUT_MS ?? 20_000),
    workspaceRoot,
  });
}

function resolveSidecarLauncherPath() {
  const explicitLauncherPath = process.env.PLATO_ELECTRON_SIDECAR_LAUNCHER_PATH;
  if (explicitLauncherPath) {
    return explicitLauncherPath;
  }

  const packagedLauncherPath = path.join(
    frontendRoot,
    "sidecar",
    "plato-sidecar-launcher.mjs",
  );
  return existsSync(packagedLauncherPath) ? packagedLauncherPath : null;
}

async function runSmokeIfRequested() {
  if (process.env.PLATO_ELECTRON_SMOKE !== "1") {
    return;
  }

  if (process.env.PLATO_ELECTRON_SMOKE_KIND === "startup-diagnostics") {
    console.error(
      "[plato-electron-smoke] fail expected startup diagnostics, but sidecar became ready",
    );
    app.exit(1);
    return;
  }

  try {
    const { runElectronSmoke } = await import("./smokeRunner.mjs");
    await runElectronSmoke({
      baseUrl: sidecarRuntime.baseUrl,
      fixture: JSON.parse(process.env.PLATO_ELECTRON_SMOKE_FIXTURE ?? "{}"),
      kind: process.env.PLATO_ELECTRON_SMOKE_KIND ?? "configured",
      window: mainWindow,
    });
    console.log("[plato-electron-smoke] pass");
    app.exit(0);
  } catch (error) {
    console.error(
      "[plato-electron-smoke] fail",
      error instanceof Error ? error.stack ?? error.message : String(error),
    );
    app.exit(1);
  }
}

async function runStartupDiagnosticsSmokeIfRequested() {
  if (
    process.env.PLATO_ELECTRON_SMOKE !== "1" ||
    process.env.PLATO_ELECTRON_SMOKE_KIND !== "startup-diagnostics"
  ) {
    return;
  }

  try {
    const { runElectronStartupDiagnosticsSmoke } = await import(
      "./smokeRunner.mjs"
    );
    await runElectronStartupDiagnosticsSmoke({
      fixture: JSON.parse(process.env.PLATO_ELECTRON_SMOKE_FIXTURE ?? "{}"),
      window: mainWindow,
    });
    console.log("[plato-electron-smoke] pass");
    app.exit(0);
  } catch (error) {
    console.error(
      "[plato-electron-smoke] fail",
      error instanceof Error ? error.stack ?? error.message : String(error),
    );
    app.exit(1);
  }
}

function exitUnexpectedStartupFailureSmokeIfRequested() {
  if (process.env.PLATO_ELECTRON_SMOKE !== "1") {
    return;
  }
  if (process.env.PLATO_ELECTRON_SMOKE_KIND === "startup-diagnostics") {
    return;
  }

  console.error("[plato-electron-smoke] fail sidecar startup failed");
  app.exit(1);
}

async function restoreWindowContent() {
  if (sidecarRuntime !== null) {
    setRendererRuntimeConfig({
      apiBaseUrl: sidecarRuntime.baseUrl,
      apiMode: "http",
      appVersion,
      disableEvents: process.env.PLATO_ELECTRON_DISABLE_EVENTS === "1",
      sessionId: null,
      startupId,
    });
    await loadRenderer(mainWindow);
    return;
  }

  if (lastStartupDiagnostics !== null) {
    await mainWindow?.loadURL(startupDiagnosticsDataUrl(lastStartupDiagnostics));
  }
}
