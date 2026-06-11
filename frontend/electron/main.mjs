import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { startPythonSidecar } from "./sidecarProcess.mjs";
import { resolvePackagedSidecarLauncherPath } from "./sidecarLauncherPath.mjs";
import {
  buildStartupDiagnostics,
  createStartupId,
  startupDiagnosticsDataUrl,
} from "./startupDiagnostics.mjs";
import {
  getWorkspaceGitStatus,
  prepareWorkspaceGit,
  safeWorkspaceGitPreparationMessage,
} from "./workspaceGit.mjs";
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
} from "./workspaceEntry.mjs";
import { resolveWorkspaceDataTargets } from "./workspaceData.mjs";
import { resolveElectronWorkspaceRoot } from "./workspacePaths.mjs";

const electronDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(electronDir, "..");
const repoRoot = path.resolve(frontendRoot, "..");
const preloadPath = path.join(electronDir, "preload.mjs");

const startupId = createStartupId();
const appVersion = resolveAppVersion();
let mainWindow = null;
let sidecarRuntime = null;
let lastStartupDiagnostics = null;
let currentWorkspaceRoot = null;
let isWorkspaceSidecarStarting = false;

app.name = "Plato";
if (process.env.PLATO_ELECTRON_USER_DATA_DIR) {
  app.setPath("userData", process.env.PLATO_ELECTRON_USER_DATA_DIR);
}
if (process.env.PLATO_ELECTRON_SMOKE === "1") {
  app.disableHardwareAcceleration();
}

ipcMain.handle("plato:get-startup-diagnostics", () => lastStartupDiagnostics);

function resolveAppVersion() {
  const explicitVersion =
    process.env.PLATO_ELECTRON_APP_VERSION ?? process.env.npm_package_version;
  if (explicitVersion) {
    return explicitVersion;
  }

  try {
    const packageJson = JSON.parse(
      readFileSync(path.join(frontendRoot, "package.json"), "utf8"),
    );
    return packageJson.platoReleaseVersion ?? packageJson.version ?? "0.1.0";
  } catch {
    return "0.1.0";
  }
}

app.whenReady().then(async () => {
  app.on("web-contents-created", (_event, contents) => {
    contents.setWindowOpenHandler(({ url }) => {
      if (url.startsWith("https://") || url.startsWith("http://")) {
        void shell.openExternal(url);
      }
      return { action: "deny" };
    });
  });
  registerWorkspaceEntryIpc();

  mainWindow = createMainWindow();

  try {
    const initialWorkspace = await resolveInitialWorkspaceRoot();
    if (initialWorkspace === null) {
      await showWorkspaceEntry();
      await runSmokeIfRequested();
      return;
    }
    await startSidecarForWorkspace(initialWorkspace);
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
  const uiLocale = process.env.PLATO_ELECTRON_UI_LOCALE;
  process.env.PLATO_ELECTRON_RUNTIME_CONFIG = JSON.stringify({
    ...config,
    ...(typeof uiLocale === "string" && uiLocale.length > 0
      ? { uiLocale }
      : {}),
  });
}

async function resolveInitialWorkspaceRoot() {
  if (process.env.PLATO_ELECTRON_SIDECAR_BASE_URL) {
    return process.env.PLATO_ELECTRON_WORKSPACE ?? resolveDefaultWorkspaceRoot();
  }

  if (process.env.PLATO_ELECTRON_WORKSPACE) {
    return process.env.PLATO_ELECTRON_WORKSPACE;
  }

  const persisted = await readWorkspaceEntryStore(app.getPath("userData"));
  if (persisted.currentPath !== null) {
    return persisted.currentPath;
  }

  if (process.env.PLATO_ELECTRON_REQUIRE_WORKSPACE_SELECTION === "1") {
    return null;
  }

  if (process.env.PLATO_ELECTRON_ALLOW_DEFAULT_WORKSPACE === "1") {
    return resolveDefaultWorkspaceRoot();
  }

  return null;
}

function resolveDefaultWorkspaceRoot() {
  const sidecarLauncherPath = resolveSidecarLauncherPath();
  return resolveElectronWorkspaceRoot({
    env: process.env,
    isPackaged: app.isPackaged,
    repoRoot,
    sidecarLauncherPath,
    userDataPath: app.getPath("userData"),
  });
}

async function startSidecarForWorkspace(workspaceRoot) {
  currentWorkspaceRoot = workspaceRoot;
  isWorkspaceSidecarStarting = true;
  await showStartupDiagnostics({
    message: "Starting the local Python sidecar.",
    status: "starting_sidecar",
  });
  try {
    sidecarRuntime?.stop();
    sidecarRuntime = await resolveSidecarRuntime(workspaceRoot);
    setRendererRuntimeConfig({
      apiBaseUrl: sidecarRuntime.baseUrl,
      apiMode: "http",
      appVersion,
      disableEvents: process.env.PLATO_ELECTRON_DISABLE_EVENTS === "1",
      sessionId: null,
      startupId,
      workspace:
        workspaceRoot === null ? null : summarizeWorkspace(workspaceRoot, workspaceRoot),
      workspaceEntryRequired: false,
    });
    await loadRenderer(mainWindow);
  } finally {
    isWorkspaceSidecarStarting = false;
  }
}

async function resolveSidecarRuntime(workspaceRoot) {
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
  const resolvedWorkspaceRoot = workspaceRoot ?? resolveDefaultWorkspaceRoot();
  const workspaceRegistry = await buildSidecarWorkspaceRegistry(resolvedWorkspaceRoot);
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
    workspaceRegistry,
    workspaceRoot: resolvedWorkspaceRoot,
  });
}

async function showWorkspaceEntry() {
  setRendererRuntimeConfig({
    apiMode: "mock",
    appVersion,
    startupId,
    workspace: null,
    workspaceEntryRequired: true,
  });
  await loadRenderer(mainWindow);
}

function registerWorkspaceEntryIpc() {
  ipcMain.handle("plato:workspace:git-status", async () => getWorkspaceGitStatus());

  ipcMain.handle("plato:workspace:get-git-preference", async () => ({
    initializeGitOnOpen: await readWorkspaceGitInitializeOnOpenPreference(
      app.getPath("userData"),
    ),
  }));

  ipcMain.handle("plato:workspace:set-git-preference", async (_event, value) => {
    const enabled =
      typeof value === "object" &&
      value !== null &&
      value.initializeGitOnOpen === true;
    await writeWorkspaceGitInitializeOnOpenPreference(
      app.getPath("userData"),
      enabled,
    );
    return { initializeGitOnOpen: enabled };
  });

  ipcMain.handle("plato:workspace:get-state", async () =>
    workspaceEntryState(
      currentWorkspaceRoot === null ? "needs_selection" : "ready",
    )
  );

  ipcMain.handle("plato:workspace:choose", async (_event, options) => {
    const result = await dialog.showOpenDialog(mainWindow, {
      buttonLabel: "Open Workspace",
      message: "Choose the folder Plato should use as its workspace.",
      properties: ["openDirectory", "createDirectory"],
      title: "Open Plato Workspace",
    });
    if (result.canceled || result.filePaths.length === 0) {
      return {
        state: await workspaceEntryState("needs_selection"),
        status: "cancelled",
      };
    }

    return await selectWorkspace(
      result.filePaths[0],
      normalizeWorkspaceSelectionOptions(options),
    );
  });

  ipcMain.handle("plato:workspace:use", async (_event, id, options) => {
    if (typeof id !== "string" || id.length === 0) {
      return {
        state: await workspaceEntryState("failed", "Unknown workspace."),
        status: "cancelled",
      };
    }
    const workspacePath = await findWorkspacePathById(app.getPath("userData"), id);
    if (workspacePath === null) {
      return {
        state: await workspaceEntryState("failed", "Recent workspace not found."),
        status: "cancelled",
      };
    }
    return await selectWorkspace(
      workspacePath,
      normalizeWorkspaceSelectionOptions(options),
    );
  });

  ipcMain.handle("plato:workspace:archive", async (_event, id) => {
    if (typeof id !== "string" || id.length === 0) {
      return await workspaceLifecycleResult("failed", "Unknown workspace.");
    }
    const result = await archiveWorkspaceById(app.getPath("userData"), id);
    if (result.workspacePath === null) {
      return await workspaceLifecycleResult("failed", "Workspace not found.");
    }
    if (
      workspaceArchiveRequiresRuntimeSwitch(
        currentWorkspaceRoot,
        result.workspacePath,
      )
    ) {
      await applyWorkspaceStoreState(result.state);
    }
    return await workspaceLifecycleResult("ok");
  });

  ipcMain.handle("plato:workspace:restore", async (_event, id) => {
    if (typeof id !== "string" || id.length === 0) {
      return await workspaceLifecycleResult("failed", "Unknown workspace.");
    }
    const result = await restoreWorkspaceById(app.getPath("userData"), id);
    if (result.workspacePath === null) {
      return await workspaceLifecycleResult("failed", "Workspace not found.");
    }
    await applyWorkspaceStoreState(result.state);
    return await workspaceLifecycleResult("ok");
  });

  ipcMain.handle("plato:workspace:delete-data", async (_event, id) => {
    if (typeof id !== "string" || id.length === 0) {
      return await workspaceLifecycleResult("failed", "Unknown workspace.");
    }
    const workspacePath = await findWorkspacePathById(app.getPath("userData"), id, {
      includeArchived: true,
    });
    if (workspacePath === null) {
      return await workspaceLifecycleResult("failed", "Workspace not found.");
    }

    try {
      await deletePlatoDataForWorkspace(workspacePath);
      const result = await removeWorkspaceById(app.getPath("userData"), id);
      await applyWorkspaceStoreState(result.state);
      return await workspaceLifecycleResult("ok");
    } catch {
      return await workspaceLifecycleResult(
        "failed",
        "Plato data could not be deleted safely.",
      );
    }
  });
}

async function selectWorkspace(workspacePath, options = {}) {
  const initializeGitOnOpen =
    options.initializeGitOnOpen ??
    ((await readWorkspaceGitInitializeOnOpenPreference(app.getPath("userData"))) ===
      true);

  if (initializeGitOnOpen) {
    try {
      await prepareWorkspaceGit(workspacePath);
    } catch (error) {
      return {
        state: await workspaceEntryState(
          "failed",
          safeWorkspaceGitPreparationMessage(error),
        ),
        status: "cancelled",
      };
    }
  }

  currentWorkspaceRoot = workspacePath;
  await rememberWorkspace(app.getPath("userData"), workspacePath);
  void startSidecarForWorkspace(workspacePath).catch((error) => {
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
    void showStartupDiagnostics(diagnostics);
  });
  return {
    state: await workspaceEntryState("starting"),
    status: "ready",
  };
}

async function applyWorkspaceStoreState(state) {
  if (state.currentPath === null) {
    sidecarRuntime?.stop();
    sidecarRuntime = null;
    currentWorkspaceRoot = null;
    await showWorkspaceEntry();
    return;
  }
  await startSidecarForWorkspace(state.currentPath);
}

async function workspaceLifecycleResult(status, error = null) {
  return {
    error,
    state: await workspaceEntryState(
      error === null ? (currentWorkspaceRoot === null ? "needs_selection" : "ready") : "failed",
      error,
    ),
    status,
  };
}

async function deletePlatoDataForWorkspace(workspacePath) {
  if (
    currentWorkspaceRoot !== null &&
    path.resolve(currentWorkspaceRoot) === path.resolve(workspacePath)
  ) {
    sidecarRuntime?.stop();
    sidecarRuntime = null;
  }
  const targets = await resolveWorkspaceDataTargets(workspacePath);
  for (const target of targets) {
    await shell.trashItem(target);
  }
}

function normalizeWorkspaceSelectionOptions(options) {
  const hasInitializeGitOnOpen =
    typeof options === "object" &&
    options !== null &&
    typeof options.initializeGitOnOpen === "boolean";
  return {
    initializeGitOnOpen: hasInitializeGitOnOpen
      ? options.initializeGitOnOpen === true
      : null,
  };
}

async function workspaceEntryState(status, error = null) {
  return await buildWorkspaceEntryState({
    currentPath: currentWorkspaceRoot,
    error,
    status: isWorkspaceSidecarStarting ? "starting" : status,
    userDataPath: app.getPath("userData"),
  });
}

async function buildSidecarWorkspaceRegistry(currentPath) {
  const state = await readWorkspaceEntryStore(app.getPath("userData"));
  const normalizedCurrentPath = path.resolve(currentPath);
  const paths = [
    normalizedCurrentPath,
    ...state.recentPaths.filter(
      (candidate) => path.resolve(candidate) !== normalizedCurrentPath,
    ),
  ];
  return paths.map((workspacePath) => {
    const summary = summarizeWorkspace(workspacePath, normalizedCurrentPath);
    return {
      workspaceId: summary.id,
      rootPath: path.resolve(workspacePath),
      label: summary.name,
      isCurrent: summary.isCurrent,
      lastOpenedAt: null,
    };
  });
}

function resolveSidecarLauncherPath() {
  return resolvePackagedSidecarLauncherPath({
    appIsPackaged: app.isPackaged,
    env: process.env,
    frontendRoot,
    resourcesPath: process.resourcesPath,
  });
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
      baseUrl: sidecarRuntime?.baseUrl ?? null,
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
      workspace:
        currentWorkspaceRoot === null
          ? null
          : summarizeWorkspace(currentWorkspaceRoot, currentWorkspaceRoot),
      workspaceEntryRequired: false,
    });
    await loadRenderer(mainWindow);
    return;
  }

  if (lastStartupDiagnostics !== null) {
    await mainWindow?.loadURL(startupDiagnosticsDataUrl(lastStartupDiagnostics));
    return;
  }

  if (
    currentWorkspaceRoot === null &&
    process.env.PLATO_ELECTRON_REQUIRE_WORKSPACE_SELECTION === "1"
  ) {
    await showWorkspaceEntry();
  }
}
