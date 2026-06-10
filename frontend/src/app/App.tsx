import { useEffect, useState } from "react";

import { AppErrorBoundary } from "./AppErrorBoundary";
import { MainPageRoute } from "./MainPageRoute";
import { PLATO_NAVIGATION_EVENT } from "./navigation";
import {
  resolvePlatoRuntimeEnv,
  resolvePlatoWorkspaceEntryRuntime,
  type PlatoWorkspaceEntryRuntime,
  type PlatoRuntimeEnv,
} from "./platoRuntime";
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

  return (
    <UiTextProvider locale={uiLocale}>
      <AppErrorBoundary>
        {workspaceEntryRuntime.isRequired ? (
          <WorkspaceEntryGate bridge={workspaceEntryRuntime.bridge} />
        ) : isAuditPath(pathname) ? (
          <AuditPageRoute runtimeEnv={runtimeEnv} />
        ) : isDiagnosticsLogsPath(pathname) ? (
          <DiagnosticsLogsRoute runtimeEnv={runtimeEnv} />
        ) : isWorkspaceInspectionPath(pathname) ? (
          <WorkspaceInspectionRoute location={location} runtimeEnv={runtimeEnv} />
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
