export type DiagnosticsLogsRouteLocation = {
  pathname: string;
  search?: string;
};

export type DiagnosticsLogsRouteContext = {
  category: string | null;
  recordId: string | null;
  sessionId: string;
  taskNodeId: string | null;
};

export function isDiagnosticsLogsPath(pathname: string): boolean {
  return parseDiagnosticsLogsLocation(pathname, "") !== null;
}

export function parseDiagnosticsLogsLocation(
  pathname: string,
  search = "",
): DiagnosticsLogsRouteContext | null {
  const match = /^\/sessions\/([^/]+)\/diagnostics\/logs\/?$/.exec(pathname);
  if (match === null) {
    return null;
  }

  const params = new URLSearchParams(search);
  return {
    category: params.get("category"),
    recordId: params.get("recordId"),
    sessionId: decodeURIComponent(match[1]),
    taskNodeId: params.get("taskNodeId"),
  };
}
