import { useMemo } from "react";

import { MainPage } from "../pages/main-page/MainPage";
import type { MainPageStateId } from "../pages/main-page/mockPlatoApi";
import type { MainPageAdapter } from "../pages/main-page/runtime/adapter";
import type { SessionId, TaskNodeId, WorkspaceId } from "../shared/api/types";
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
  const routeContext = parseMainPageRoute(
    globalThis.location.pathname,
    globalThis.location.search,
  );
  const runtimeAdapter = useMemo(
    () =>
      adapter ??
      createMainPageAdapterFromRuntimeEnv(runtimeEnv, {
        sessionId: routeContext.sessionId,
        workspaceId: routeContext.workspaceId,
      }),
    [adapter, routeContext.sessionId, routeContext.workspaceId, runtimeEnv],
  );

  return (
    <MainPage
      adapter={runtimeAdapter}
      auditRouteAvailable={auditRouteAvailable}
      initialStateId={initialStateId}
      initialTaskNodeId={routeContext.taskNodeId}
      workspaceRuntime={workspaceEntryRuntime}
    />
  );
}

type MainPageRouteContext = {
  sessionId?: SessionId | null;
  taskNodeId?: TaskNodeId | null;
  workspaceId?: WorkspaceId | null;
};

function parseMainPageRoute(pathname: string, search: string): MainPageRouteContext {
  const params = new URLSearchParams(search);
  const sessionId = parseSessionId(pathname);
  return {
    sessionId,
    taskNodeId: parseNonEmpty(params.get("taskNodeId")) as TaskNodeId | undefined,
    workspaceId: parseNonEmpty(params.get("workspaceId")) as WorkspaceId | undefined,
  };
}

function parseSessionId(pathname: string): SessionId | undefined {
  const fallbackMatch = pathname.match(/^\/sessions\/([^/]+)\/?$/);
  const canonicalMatch = pathname.match(
    /^\/projects\/[^/]+\/workflows\/[^/]+\/sessions\/([^/]+)\/?$/,
  );
  const value = fallbackMatch?.[1] ?? canonicalMatch?.[1];
  if (value === undefined) {
    return undefined;
  }
  return decodeSegment(value);
}

function decodeSegment(value: string): string | undefined {
  try {
    return decodeURIComponent(value);
  } catch {
    return undefined;
  }
}

function parseNonEmpty(value: string | null): string | undefined {
  if (value === null || value.trim() === "") {
    return undefined;
  }
  return value;
}
