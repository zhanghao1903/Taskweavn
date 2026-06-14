import type {
  AuditSnapshotRequest,
} from "../../shared/api/platoApi";
import type {
  AuditEntryKind,
  AuditFilterKind,
  AuditRecordId,
  EvidenceId,
  SessionId,
  TaskNodeId,
  WorkspaceId,
} from "../../shared/api/types";
import {
  buildMainSessionFallbackRoute,
  buildAuditSessionRoute,
  buildAuditTaskRoute,
  type AuditRouteQuery,
} from "../../app/routes";

export type ParsedAuditRoute = {
  evidenceId?: EvidenceId;
  request: AuditSnapshotRequest;
  returnFocus?: AuditRouteQuery["returnFocus"];
  returnSessionId?: SessionId;
  returnTaskNodeId?: TaskNodeId;
  routeKind: "session" | "task";
  workspaceId?: WorkspaceId;
};

const auditFilterKinds = new Set<AuditFilterKind>([
  "actions",
  "all",
  "config",
  "confirmations",
  "files",
  "logs",
  "results",
  "risks",
  "system",
]);

const auditEntryKinds = new Set<AuditEntryKind>([
  "from_confirmation",
  "from_file_change",
  "from_result",
  "from_session",
  "from_task",
]);

export function isAuditPath(pathname: string): boolean {
  return /^\/sessions\/[^/]+\/audit\/?$/.test(pathname) ||
    /^\/sessions\/[^/]+\/tasks\/[^/]+\/audit\/?$/.test(pathname);
}

export function parseAuditLocation(
  pathname: string,
  search = "",
): ParsedAuditRoute | null {
  const taskMatch = pathname.match(/^\/sessions\/([^/]+)\/tasks\/([^/]+)\/audit\/?$/);
  if (taskMatch !== null) {
    const sessionId = decodeSegment(taskMatch[1]);
    const taskNodeId = decodeSegment(taskMatch[2]);
    if (sessionId === null || taskNodeId === null) {
      return null;
    }

    const evidenceId = parseEvidenceId(search);
    return {
      ...(evidenceId === undefined ? {} : { evidenceId }),
      request: buildAuditSnapshotRequest(search, sessionId, taskNodeId),
      ...parseReturnQuery(search),
      routeKind: "task",
      workspaceId: parseWorkspaceId(search),
    };
  }

  const sessionMatch = pathname.match(/^\/sessions\/([^/]+)\/audit\/?$/);
  if (sessionMatch !== null) {
    const sessionId = decodeSegment(sessionMatch[1]);
    if (sessionId === null) {
      return null;
    }

    const evidenceId = parseEvidenceId(search);
    return {
      ...(evidenceId === undefined ? {} : { evidenceId }),
      request: buildAuditSnapshotRequest(search, sessionId),
      ...parseReturnQuery(search),
      routeKind: "session",
      workspaceId: parseWorkspaceId(search),
    };
  }

  return null;
}

export function buildAuditLocation(
  route: ParsedAuditRoute,
  query: {
    evidenceId?: EvidenceId | null;
    filter: AuditFilterKind;
    recordId: AuditRecordId | null;
  },
): string {
  const routeQuery: AuditRouteQuery = {
    entry: route.request.entry,
    evidenceId: query.evidenceId ?? undefined,
    filter: query.filter,
    recordId: query.recordId ?? undefined,
    returnFocus: route.returnFocus,
    returnSessionId: route.returnSessionId,
    returnTaskNodeId: route.returnTaskNodeId,
    workspaceId: route.workspaceId,
  };

  if (route.routeKind === "task" && route.request.taskNodeId !== undefined) {
    return buildAuditTaskRoute(
      route.request.sessionId,
      route.request.taskNodeId,
      routeQuery,
    );
  }

  return buildAuditSessionRoute(route.request.sessionId, routeQuery);
}

export function buildAuditReturnLocation(route: ParsedAuditRoute): string {
  return buildMainSessionFallbackRoute({
    sessionId: route.returnSessionId ?? route.request.sessionId,
    taskNodeId: route.returnTaskNodeId ?? route.request.taskNodeId,
    workspaceId: route.workspaceId,
  });
}

function buildAuditSnapshotRequest(
  search: string,
  sessionId: SessionId,
  taskNodeId?: TaskNodeId,
): AuditSnapshotRequest {
  const params = new URLSearchParams(search);
  const filter = parseFilter(params.get("filter")) ?? "all";
  const entry = parseEntry(params.get("entry"));
  const recordId = parseRecordId(params.get("recordId"));

  return {
    entry,
    filter,
    includeDetail: recordId !== undefined,
    limit: 50,
    recordId,
    sessionId,
    taskNodeId,
  };
}

function parseFilter(value: string | null): AuditFilterKind | undefined {
  if (value === null) {
    return undefined;
  }

  return auditFilterKinds.has(value as AuditFilterKind)
    ? (value as AuditFilterKind)
    : undefined;
}

function parseEntry(value: string | null): AuditEntryKind | undefined {
  if (value === null) {
    return undefined;
  }

  return auditEntryKinds.has(value as AuditEntryKind)
    ? (value as AuditEntryKind)
    : undefined;
}

function parseRecordId(value: string | null): AuditRecordId | undefined {
  if (value === null || value.trim() === "") {
    return undefined;
  }

  return value as AuditRecordId;
}

function parseEvidenceId(search: string): EvidenceId | undefined {
  return parseNonEmpty(new URLSearchParams(search).get("evidenceId")) as
    | EvidenceId
    | undefined;
}

function parseReturnQuery(search: string): Pick<
  ParsedAuditRoute,
  "returnFocus" | "returnSessionId" | "returnTaskNodeId"
> {
  const params = new URLSearchParams(search);
  const returnFocus = parseReturnFocus(params.get("returnFocus"));
  const returnSessionId = parseNonEmpty(params.get("returnSessionId")) as
    | SessionId
    | undefined;
  const returnTaskNodeId = parseNonEmpty(params.get("returnTaskNodeId")) as
    | TaskNodeId
    | undefined;
  const result: Pick<
    ParsedAuditRoute,
    "returnFocus" | "returnSessionId" | "returnTaskNodeId"
  > = {};

  if (returnFocus !== undefined) {
    result.returnFocus = returnFocus;
  }
  if (returnSessionId !== undefined) {
    result.returnSessionId = returnSessionId;
  }
  if (returnTaskNodeId !== undefined) {
    result.returnTaskNodeId = returnTaskNodeId;
  }
  return result;
}

function parseReturnFocus(
  value: string | null,
): AuditRouteQuery["returnFocus"] | undefined {
  if (
    value === "session" ||
    value === "task" ||
    value === "confirmation" ||
    value === "result" ||
    value === "file_change"
  ) {
    return value;
  }
  return undefined;
}

function parseNonEmpty(value: string | null): string | undefined {
  if (value === null || value.trim() === "") {
    return undefined;
  }
  return value;
}

function parseWorkspaceId(search: string): WorkspaceId | undefined {
  return parseNonEmpty(new URLSearchParams(search).get("workspaceId")) as
    | WorkspaceId
    | undefined;
}

function decodeSegment(value: string): string | null {
  try {
    return decodeURIComponent(value);
  } catch {
    return null;
  }
}
