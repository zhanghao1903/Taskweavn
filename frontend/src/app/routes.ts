import type {
  AuditEntryKind,
  AuditFilterKind,
  AuditRecordId,
  ProjectId,
  SessionId,
  TaskNodeId,
  WorkspaceId,
  WorkflowId,
} from "../shared/api/types";

export const routes = {
  main: "/",
  mainSession: "/projects/:projectId/workflows/:workflowId/sessions/:sessionId",
  mainSessionFallback: "/sessions/:sessionId",
  auditSession: "/sessions/:sessionId/audit",
  auditTask: "/sessions/:sessionId/tasks/:taskNodeId/audit",
  diagnosticsLogs: "/sessions/:sessionId/diagnostics/logs",
  settings: "/settings",
  workspaceInspection: "/workspaces/:workspaceId/inspection",
  workspaceUsage: "/workspaces/:workspaceId/usage",
} as const;

export type AppRoute = (typeof routes)[keyof typeof routes];

export type AuditRouteQuery = {
  entry?: AuditEntryKind;
  filter?: AuditFilterKind;
  recordId?: AuditRecordId;
  returnFocus?: "session" | "task" | "confirmation" | "result" | "file_change";
  returnSessionId?: SessionId;
  returnTaskNodeId?: TaskNodeId;
  workspaceId?: WorkspaceId;
};

export type WorkspaceInspectionRouteQuery = {
  evidenceId?: string;
  path?: string;
  returnSessionId?: SessionId;
  returnTaskNodeId?: TaskNodeId;
  sessionId?: SessionId;
  taskNodeId?: TaskNodeId;
  view?: "status" | "file" | "diff";
};

export type WorkspaceUsageRouteQuery = {
  sessionId?: SessionId;
  planId?: string;
  taskNodeId?: TaskNodeId;
};

export function buildMainSessionRoute(params: {
  projectId: ProjectId;
  workflowId: WorkflowId;
  sessionId: SessionId;
  taskNodeId?: TaskNodeId;
  messageId?: string;
}): string {
  const path = `/projects/${segment(params.projectId)}/workflows/${segment(
    params.workflowId,
  )}/sessions/${segment(params.sessionId)}`;
  return withQuery(path, {
    messageId: params.messageId,
    taskNodeId: params.taskNodeId,
  });
}

export function buildMainSessionFallbackRoute(params: {
  sessionId: SessionId;
  taskNodeId?: TaskNodeId;
  workspaceId?: WorkspaceId;
}): string {
  return withQuery(`/sessions/${segment(params.sessionId)}`, {
    taskNodeId: params.taskNodeId,
    workspaceId: params.workspaceId,
  });
}

export function buildAuditSessionRoute(
  sessionId: SessionId,
  query: AuditRouteQuery = {},
): string {
  return withQuery(`/sessions/${segment(sessionId)}/audit`, query);
}

export function buildAuditTaskRoute(
  sessionId: SessionId,
  taskNodeId: TaskNodeId,
  query: AuditRouteQuery = {},
): string {
  return withQuery(
    `/sessions/${segment(sessionId)}/tasks/${segment(taskNodeId)}/audit`,
    query,
  );
}

export function buildDiagnosticsLogsRoute(params: {
  sessionId: SessionId;
  taskNodeId?: TaskNodeId;
  recordId?: AuditRecordId;
  category?: string;
}): string {
  return withQuery(`/sessions/${segment(params.sessionId)}/diagnostics/logs`, {
    category: params.category,
    recordId: params.recordId,
    taskNodeId: params.taskNodeId,
  });
}

export function buildWorkspaceInspectionRoute(params: {
  workspaceId: WorkspaceId;
} & WorkspaceInspectionRouteQuery): string {
  return withQuery(`/workspaces/${segment(params.workspaceId)}/inspection`, {
    evidenceId: params.evidenceId,
    path: params.path,
    returnSessionId: params.returnSessionId,
    returnTaskNodeId: params.returnTaskNodeId,
    sessionId: params.sessionId,
    taskNodeId: params.taskNodeId,
    view: params.view,
  });
}

export function buildWorkspaceUsageRoute(params: {
  workspaceId: WorkspaceId;
} & WorkspaceUsageRouteQuery): string {
  return withQuery(`/workspaces/${segment(params.workspaceId)}/usage`, {
    planId: params.planId,
    sessionId: params.sessionId,
    taskNodeId: params.taskNodeId,
  });
}

function segment(value: string): string {
  return encodeURIComponent(value);
}

function withQuery(
  path: string,
  query: Record<string, string | undefined> = {},
): string {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") {
      params.set(key, value);
    }
  }

  const queryString = params.toString();
  return queryString.length > 0 ? `${path}?${queryString}` : path;
}
