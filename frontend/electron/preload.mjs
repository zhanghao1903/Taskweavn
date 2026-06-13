import { contextBridge, ipcRenderer } from "electron";

const runtimeConfig = parseRuntimeConfig(
  readRuntimeConfig(),
);

contextBridge.exposeInMainWorld("platoRuntimeConfig", {
  apiBaseUrl: runtimeConfig.apiBaseUrl,
  apiMode: runtimeConfig.apiMode,
  appVersion: runtimeConfig.appVersion,
  disableEvents: runtimeConfig.disableEvents,
  sessionId: runtimeConfig.sessionId ?? null,
  startupId: runtimeConfig.startupId,
  startupStatus: runtimeConfig.startupStatus,
  uiLocale: runtimeConfig.uiLocale,
  workspace: runtimeConfig.workspace ?? null,
  workspaceEntryRequired: runtimeConfig.workspaceEntryRequired,
});

contextBridge.exposeInMainWorld("platoElectron", {
  getStartupDiagnostics: () => ipcRenderer.invoke("plato:get-startup-diagnostics"),
});

contextBridge.exposeInMainWorld("platoStartupTiming", {
  mark: (event, attributes) =>
    ipcRenderer.send("plato:startup-timing", event, attributes ?? {}),
});

contextBridge.exposeInMainWorld("platoElectronWorkspace", {
  archiveWorkspace: (id) => ipcRenderer.invoke("plato:workspace:archive", id),
  chooseWorkspace: (options) =>
    ipcRenderer.invoke("plato:workspace:choose", options),
  deleteWorkspaceData: (id, options) =>
    ipcRenderer.invoke("plato:workspace:delete-data", id, options),
  getGitPreference: () =>
    ipcRenderer.invoke("plato:workspace:get-git-preference"),
  getGitStatus: () => ipcRenderer.invoke("plato:workspace:git-status"),
  getState: () => ipcRenderer.invoke("plato:workspace:get-state"),
  restoreWorkspace: (id) => ipcRenderer.invoke("plato:workspace:restore", id),
  setGitPreference: (value) =>
    ipcRenderer.invoke("plato:workspace:set-git-preference", value),
  useWorkspace: (id, options) =>
    ipcRenderer.invoke("plato:workspace:use", id, options),
});

function parseRuntimeConfig(raw) {
  if (!raw) {
    return {};
  }

  if (typeof raw === "object") {
    return sanitizeRuntimeConfig(raw);
  }

  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      return {};
    }
    return sanitizeRuntimeConfig(parsed);
  } catch {
    return {};
  }
}

function readRuntimeConfig() {
  try {
    return ipcRenderer.sendSync("plato:get-runtime-config-sync");
  } catch {
    return process.env.PLATO_ELECTRON_RUNTIME_CONFIG;
  }
}

function sanitizeRuntimeConfig(config) {
  const apiMode = config.apiMode === "http" ? "http" : "mock";
  return {
    apiBaseUrl:
      typeof config.apiBaseUrl === "string" ? config.apiBaseUrl : undefined,
    apiMode,
    appVersion:
      typeof config.appVersion === "string" ? config.appVersion : undefined,
    disableEvents: config.disableEvents === true,
    sessionId:
      typeof config.sessionId === "string" || config.sessionId === null
        ? config.sessionId
        : undefined,
    startupId:
      typeof config.startupId === "string" ? config.startupId : undefined,
    startupStatus:
      config.startupStatus === "starting_sidecar"
        ? config.startupStatus
        : undefined,
    uiLocale:
      typeof config.uiLocale === "string" ? config.uiLocale : undefined,
    workspace:
      config.workspace && typeof config.workspace === "object"
        ? sanitizeWorkspaceSummary(config.workspace)
        : null,
    workspaceEntryRequired: config.workspaceEntryRequired === true,
  };
}

function sanitizeWorkspaceSummary(summary) {
  const id = typeof summary.id === "string" ? summary.id : "";
  const name = typeof summary.name === "string" ? summary.name : "Workspace";
  const label = typeof summary.label === "string" ? summary.label : name;
  const pathLabel =
    typeof summary.pathLabel === "string" ? summary.pathLabel : label;
  return {
    id,
    isCurrent: summary.isCurrent === true,
    label,
    name,
    pathLabel,
  };
}
