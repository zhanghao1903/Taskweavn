import { useMemo } from "react";

import { MainPage } from "../pages/main-page/MainPage";
import {
  listMainPageStateOptions,
  type MainPageStateId,
} from "../pages/main-page/mockPlatoApi";
import type { MainPageFocusTarget } from "../pages/main-page/runtime/mainPageFocusScrollRuntime";
import type { MainPageAdapter } from "../pages/main-page/runtime/adapter";
import type { SessionId, TaskNodeId, WorkspaceId } from "../shared/api/types";
import {
  createMainPageAdapterFromRuntimeEnv,
  resolvePlatoRuntimeEnv,
  type PlatoRuntimeEnv,
  type PlatoWorkspaceEntryRuntime,
} from "./platoRuntime";

const mainPageStateIds = new Set(
  listMainPageStateOptions().map((option) => option.id),
);

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
  const runtimeMode = resolvePlatoRuntimeEnv(runtimeEnv).VITE_PLATO_API_MODE;
  const routeInitialStateId =
    adapter === undefined && runtimeMode === "http" ? undefined : routeContext.stateId;
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
      initialStateId={initialStateId ?? routeInitialStateId}
      initialTaskNodeId={routeContext.taskNodeId}
      routeFocusTarget={routeContext.focusTarget}
      workspaceRuntime={workspaceEntryRuntime}
    />
  );
}

type MainPageRouteContext = {
  focusTarget?: MainPageFocusTarget | null;
  sessionId?: SessionId | null;
  stateId?: MainPageStateId;
  taskNodeId?: TaskNodeId | null;
  workspaceId?: WorkspaceId | null;
};

function parseMainPageRoute(pathname: string, search: string): MainPageRouteContext {
  const params = new URLSearchParams(search);
  const sessionId = parseSessionId(pathname);
  return {
    focusTarget: parseRouteFocusTarget(params),
    sessionId,
    stateId: parseStateId(params.get("stateId") ?? params.get("state")),
    taskNodeId: parseNonEmpty(params.get("taskNodeId")) as TaskNodeId | undefined,
    workspaceId: parseNonEmpty(params.get("workspaceId")) as WorkspaceId | undefined,
  };
}

function parseRouteFocusTarget(
  params: URLSearchParams,
): MainPageFocusTarget | null {
  const returnFocus = parseNonEmpty(params.get("returnFocus"));
  if (returnFocus === "ask") {
    return "ask_card";
  }
  if (returnFocus === "composer") {
    return "input_composer";
  }
  if (returnFocus === "session") {
    return "conversation";
  }
  if (returnFocus === "result") {
    return "detail_panel";
  }
  if (returnFocus === "file_change") {
    return "file_changes";
  }
  if (
    returnFocus === "task" ||
    returnFocus === "confirmation" ||
    parseNonEmpty(params.get("taskNodeId"))
  ) {
    return "selected_task";
  }
  return null;
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

function parseStateId(value: string | null): MainPageStateId | undefined {
  const parsed = parseNonEmpty(value);
  if (parsed === undefined) {
    return undefined;
  }
  return mainPageStateIds.has(parsed as MainPageStateId)
    ? (parsed as MainPageStateId)
    : undefined;
}
