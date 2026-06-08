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

export type AppProps = {
  readinessApi?: SettingsReadinessApi;
  runtimeEnv?: PlatoRuntimeEnv;
  settingsApi?: SettingsRouteApi;
  workspaceEntryRuntime?: PlatoWorkspaceEntryRuntime;
};

export function App({
  readinessApi,
  runtimeEnv = resolvePlatoRuntimeEnv(),
  settingsApi,
  workspaceEntryRuntime = resolvePlatoWorkspaceEntryRuntime(),
}: AppProps = {}) {
  const [pathname, setPathname] = useState(() => globalThis.location.pathname);

  useEffect(() => {
    const handleRouteChange = () => {
      setPathname(globalThis.location.pathname);
    };

    globalThis.addEventListener("popstate", handleRouteChange);
    globalThis.addEventListener(PLATO_NAVIGATION_EVENT, handleRouteChange);
    return () => {
      globalThis.removeEventListener("popstate", handleRouteChange);
      globalThis.removeEventListener(PLATO_NAVIGATION_EVENT, handleRouteChange);
    };
  }, []);

  return (
    <AppErrorBoundary>
      {workspaceEntryRuntime.isRequired ? (
        <WorkspaceEntryGate bridge={workspaceEntryRuntime.bridge} />
      ) : isAuditPath(pathname) ? (
        <AuditPageRoute runtimeEnv={runtimeEnv} />
      ) : isDiagnosticsLogsPath(pathname) ? (
        <DiagnosticsLogsRoute runtimeEnv={runtimeEnv} />
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
  );
}
