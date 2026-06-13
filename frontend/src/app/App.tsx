import { useEffect, useState } from "react";

import { AppErrorBoundary } from "./AppErrorBoundary";
import { MainPageRoute } from "./MainPageRoute";
import { PLATO_NAVIGATION_EVENT } from "./navigation";
import {
  resolvePlatoRuntimeEnv,
  resolvePlatoStartupRuntime,
  resolvePlatoWorkspaceEntryRuntime,
  type PlatoStartupRuntime,
  type PlatoWorkspaceEntryRuntime,
  type PlatoRuntimeEnv,
} from "./platoRuntime";
import { StartupShell } from "./StartupShell";
import { AuditPageRoute } from "../pages/audit-page/AuditPageRoute";
import { isAuditPath } from "../pages/audit-page/auditRouteModel";
import { DiagnosticsLogsRoute } from "../pages/diagnostics/DiagnosticsLogsRoute";
import { isDiagnosticsLogsPath } from "../pages/diagnostics/diagnosticsRouteModel";
import {
  FirstRunReadinessGate,
  type SettingsReadinessApi,
} from "../pages/settings/FirstRunReadinessGate";
import { SettingsRoute, type SettingsRouteApi } from "../pages/settings/SettingsRoute";
import { isSettingsPath } from "../pages/settings/settingsRouteModel";
import { WorkspaceEntryGate } from "../pages/workspace/WorkspaceEntryGate";
import { WorkspaceInspectionRoute } from "../pages/workspace-inspection/WorkspaceInspectionRoute";
import { isWorkspaceInspectionPath } from "../pages/workspace-inspection/workspaceInspectionRouteModel";
import { WorkspaceUsageRoute } from "../pages/usage/WorkspaceUsageRoute";
import { isWorkspaceUsagePath } from "../pages/usage/workspaceUsageRouteModel";
import {
  readUiLocalePreference,
  resolveUiLocale,
  UI_LOCALE_PREFERENCE_CHANGED_EVENT,
  UI_LOCALE_PREFERENCE_STORAGE_KEY,
  UiTextProvider,
} from "../shared/ui-text";

export type AppProps = {
  readinessApi?: SettingsReadinessApi;
  runtimeEnv?: PlatoRuntimeEnv;
  settingsApi?: SettingsRouteApi;
  startupRuntime?: PlatoStartupRuntime;
  workspaceEntryRuntime?: PlatoWorkspaceEntryRuntime;
};

type AppLocation = {
  pathname: string;
  search: string;
};

export function App({
  readinessApi,
  runtimeEnv = resolvePlatoRuntimeEnv(),
  settingsApi,
  startupRuntime = resolvePlatoStartupRuntime(),
  workspaceEntryRuntime = resolvePlatoWorkspaceEntryRuntime(),
}: AppProps = {}) {
  const [location, setLocation] = useState(currentAppLocation);
  const [uiLocalePreference, setUiLocalePreference] = useState(() =>
    readUiLocalePreference(),
  );
  const { pathname } = location;
  const uiLocale = resolveUiLocale({
    electronRuntimeLocale: globalThis.window?.platoRuntimeConfig?.uiLocale,
    persistedLocale: uiLocalePreference,
    runtimeEnv,
  });

  useEffect(() => {
    const handleRouteChange = () => {
      setLocation(currentAppLocation());
    };

    globalThis.addEventListener("popstate", handleRouteChange);
    globalThis.addEventListener(PLATO_NAVIGATION_EVENT, handleRouteChange);
    return () => {
      globalThis.removeEventListener("popstate", handleRouteChange);
      globalThis.removeEventListener(PLATO_NAVIGATION_EVENT, handleRouteChange);
    };
  }, []);

  useEffect(() => {
    const refreshPreference = () => {
      setUiLocalePreference(readUiLocalePreference());
    };
    const handleStorage = (event: StorageEvent) => {
      if (event.key === UI_LOCALE_PREFERENCE_STORAGE_KEY) {
        refreshPreference();
      }
    };

    globalThis.addEventListener(
      UI_LOCALE_PREFERENCE_CHANGED_EVENT,
      refreshPreference,
    );
    globalThis.addEventListener("storage", handleStorage);
    return () => {
      globalThis.removeEventListener(
        UI_LOCALE_PREFERENCE_CHANGED_EVENT,
        refreshPreference,
      );
      globalThis.removeEventListener("storage", handleStorage);
    };
  }, []);

  useEffect(() => {
    if (startupRuntime.status === "starting_sidecar") {
      markRendererStartupTiming("renderer_startup_shell_ready", {
        hasWorkspace: startupRuntime.workspace !== null,
      });
      return;
    }
    markRendererStartupTiming("renderer_app_ready", {
      apiMode: runtimeEnv.VITE_PLATO_API_MODE ?? "mock",
      routeKind: routeKindForPathname(pathname),
      workspaceEntryRequired: workspaceEntryRuntime.isRequired,
    });
  }, [
    pathname,
    runtimeEnv.VITE_PLATO_API_MODE,
    startupRuntime.status,
    startupRuntime.workspace,
    workspaceEntryRuntime.isRequired,
  ]);

  return (
    <UiTextProvider locale={uiLocale}>
      <AppErrorBoundary>
        {startupRuntime.status === "starting_sidecar" ? (
          <StartupShell workspaceName={startupRuntime.workspace?.name} />
        ) : workspaceEntryRuntime.isRequired ? (
          <WorkspaceEntryGate bridge={workspaceEntryRuntime.bridge} />
        ) : isAuditPath(pathname) ? (
          <AuditPageRoute runtimeEnv={runtimeEnv} />
        ) : isDiagnosticsLogsPath(pathname) ? (
          <DiagnosticsLogsRoute runtimeEnv={runtimeEnv} />
        ) : isWorkspaceInspectionPath(pathname) ? (
          <WorkspaceInspectionRoute location={location} runtimeEnv={runtimeEnv} />
        ) : isWorkspaceUsagePath(pathname) ? (
          <WorkspaceUsageRoute location={location} runtimeEnv={runtimeEnv} />
        ) : isSettingsPath(pathname) ? (
          <>
            <FirstRunReadinessGate api={readinessApi} runtimeEnv={runtimeEnv}>
              <MainPageRoute
                runtimeEnv={runtimeEnv}
                workspaceEntryRuntime={workspaceEntryRuntime}
              />
            </FirstRunReadinessGate>
            <SettingsRoute
              api={settingsApi}
              presentation="modal"
              runtimeEnv={runtimeEnv}
              workspaceBridge={workspaceEntryRuntime.bridge}
            />
          </>
        ) : (
          <FirstRunReadinessGate api={readinessApi} runtimeEnv={runtimeEnv}>
            <MainPageRoute
              runtimeEnv={runtimeEnv}
              workspaceEntryRuntime={workspaceEntryRuntime}
            />
          </FirstRunReadinessGate>
        )}
      </AppErrorBoundary>
    </UiTextProvider>
  );
}

function currentAppLocation(): AppLocation {
  return {
    pathname: globalThis.location.pathname,
    search: globalThis.location.search,
  };
}

function markRendererStartupTiming(
  event: string,
  attributes: Record<string, string | number | boolean | null>,
) {
  globalThis.window?.platoStartupTiming?.mark(event, attributes);
}

function routeKindForPathname(pathname: string): string {
  if (isAuditPath(pathname)) {
    return "audit";
  }
  if (isDiagnosticsLogsPath(pathname)) {
    return "diagnostics";
  }
  if (isWorkspaceInspectionPath(pathname)) {
    return "workspace-inspection";
  }
  if (isWorkspaceUsagePath(pathname)) {
    return "usage";
  }
  if (isSettingsPath(pathname)) {
    return "settings";
  }
  return "main";
}
