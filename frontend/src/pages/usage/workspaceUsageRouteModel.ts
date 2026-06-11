import type { SessionId, TaskNodeId, WorkspaceId } from "../../shared/api/types";

export type WorkspaceUsageRouteContext = {
  workspaceId: WorkspaceId;
  sessionId: SessionId | null;
  planId: string | null;
  taskNodeId: TaskNodeId | null;
};

export type WorkspaceUsageRouteLocation = {
  pathname: string;
  search: string;
};

export function isWorkspaceUsagePath(pathname: string): boolean {
  return /^\/workspaces\/[^/]+\/usage\/?$/.test(pathname);
}

export function parseWorkspaceUsageLocation(
  pathname: string,
  search: string,
): WorkspaceUsageRouteContext | null {
  const match = pathname.match(/^\/workspaces\/([^/]+)\/usage\/?$/);
  if (match === null) {
    return null;
  }

  const params = new URLSearchParams(search);
  return {
    workspaceId: decodeSegment(match[1]) as WorkspaceId,
    sessionId: parseNonEmpty(params.get("sessionId")) as SessionId | null,
    planId: parseNonEmpty(params.get("planId")),
    taskNodeId: parseNonEmpty(params.get("taskNodeId")) as TaskNodeId | null,
  };
}

function parseNonEmpty(value: string | null): string | null {
  if (value === null || value.trim() === "") {
    return null;
  }
  return value;
}

function decodeSegment(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}
