import { useMemo } from "react";

import { MainPage } from "../pages/main-page/MainPage";
import type { MainPageStateId } from "../pages/main-page/mockPlatoApi";
import type { MainPageAdapter } from "../pages/main-page/runtime/adapter";
import {
  createMainPageAdapterFromRuntimeEnv,
  type PlatoRuntimeEnv,
  type PlatoWorkspaceEntryRuntime,
} from "./platoRuntime";

export type MainPageRouteProps = {
  adapter?: MainPageAdapter;
  auditRouteAvailable?: boolean;
  initialStateId?: MainPageStateId;
  runtimeEnv?: PlatoRuntimeEnv;
  workspaceEntryRuntime?: PlatoWorkspaceEntryRuntime;
};

export function MainPageRoute({
  adapter,
  auditRouteAvailable = true,
  initialStateId,
  runtimeEnv,
  workspaceEntryRuntime,
}: MainPageRouteProps = {}) {
  const runtimeAdapter = useMemo(
    () => adapter ?? createMainPageAdapterFromRuntimeEnv(runtimeEnv),
    [adapter, runtimeEnv],
  );

  return (
    <MainPage
      adapter={runtimeAdapter}
      auditRouteAvailable={auditRouteAvailable}
      initialStateId={initialStateId}
      workspaceRuntime={workspaceEntryRuntime}
    />
  );
}
