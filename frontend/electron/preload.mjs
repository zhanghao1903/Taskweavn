import { contextBridge, ipcRenderer } from "electron";

const runtimeConfig = parseRuntimeConfig(
  process.env.PLATO_ELECTRON_RUNTIME_CONFIG,
);

contextBridge.exposeInMainWorld("platoRuntimeConfig", {
  apiBaseUrl: runtimeConfig.apiBaseUrl,
  apiMode: runtimeConfig.apiMode,
  appVersion: runtimeConfig.appVersion,
  disableEvents: runtimeConfig.disableEvents,
  sessionId: runtimeConfig.sessionId ?? null,
  startupId: runtimeConfig.startupId,
});

contextBridge.exposeInMainWorld("platoElectron", {
  getStartupDiagnostics: () => ipcRenderer.invoke("plato:get-startup-diagnostics"),
});

function parseRuntimeConfig(raw) {
  if (!raw) {
    return {};
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
  };
}
