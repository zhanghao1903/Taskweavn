import type { SessionId, TaskNodeId, WorkspaceId } from "../../shared/api/types";
import type { RouteReturnFocus } from "../../app/routes";

export type WorkspaceInspectionViewMode = "status" | "file" | "diff";

export type WorkspaceInspectionRouteLocation = {
  pathname: string;
  search?: string;
};

export type WorkspaceInspectionRouteContext = {
  evidenceId: string | null;
  mode: WorkspaceInspectionViewMode;
  path: string | null;
  returnFocus: RouteReturnFocus | null;
  returnSessionId: SessionId | null;
  returnTaskNodeId: TaskNodeId | null;
  sessionId: SessionId | null;
  taskNodeId: TaskNodeId | null;
  workspaceId: WorkspaceId;
};

export function isWorkspaceInspectionPath(pathname: string): boolean {
  return parseWorkspaceInspectionLocation(pathname, "") !== null;
}

export function parseWorkspaceInspectionLocation(
  pathname: string,
  search = "",
): WorkspaceInspectionRouteContext | null {
  const match = /^\/workspaces\/([^/]+)\/inspection\/?$/.exec(pathname);
  if (match === null) {
    return null;
  }

  const params = new URLSearchParams(search);
  const path = params.get("path");
  const evidenceId = params.get("evidenceId");
  return {
    evidenceId,
    mode: normalizeMode(params.get("view"), path, evidenceId),
    path,
    returnFocus: parseReturnFocus(params.get("returnFocus")),
    returnSessionId: params.get("returnSessionId"),
    returnTaskNodeId: params.get("returnTaskNodeId"),
    sessionId: params.get("sessionId"),
    taskNodeId: params.get("taskNodeId"),
    workspaceId: decodeURIComponent(match[1]),
  };
}

function parseReturnFocus(value: string | null): RouteReturnFocus | null {
  if (
    value === "session" ||
    value === "task" ||
    value === "confirmation" ||
    value === "result" ||
    value === "file_change"
  ) {
    return value;
  }
  return null;
}

function normalizeMode(
  value: string | null,
  path: string | null,
  evidenceId: string | null,
): WorkspaceInspectionViewMode {
  if (value === "file" || value === "diff" || value === "status") {
    return value;
  }

  return path !== null || evidenceId !== null ? "file" : "status";
}
