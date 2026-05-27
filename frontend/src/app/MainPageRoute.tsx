import { useMemo } from "react";

import { MainPage } from "../pages/main-page/MainPage";
import type { MainPageStateId } from "../pages/main-page/mockPlatoApi";
import type { MainPageAdapter } from "../pages/main-page/runtime/adapter";
import {
  createMainPageAdapterFromRuntimeEnv,
  type PlatoRuntimeEnv,
} from "./platoRuntime";

export type MainPageRouteProps = {
  adapter?: MainPageAdapter;
  initialStateId?: MainPageStateId;
  runtimeEnv?: PlatoRuntimeEnv;
};

export function MainPageRoute({
  adapter,
  initialStateId,
  runtimeEnv,
}: MainPageRouteProps = {}) {
  const runtimeAdapter = useMemo(
    () => adapter ?? createMainPageAdapterFromRuntimeEnv(runtimeEnv),
    [adapter, runtimeEnv],
  );

  return <MainPage adapter={runtimeAdapter} initialStateId={initialStateId} />;
}
