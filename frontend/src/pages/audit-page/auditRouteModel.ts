import type {
  AuditSnapshotRequest,
} from "../../shared/api/platoApi";
import type {
  AuditEntryKind,
  AuditFilterKind,
  AuditRecordId,
  SessionId,
  TaskNodeId,
} from "../../shared/api/types";
import {
  buildAuditSessionRoute,
  buildAuditTaskRoute,
  type AuditRouteQuery,
} from "../../app/routes";

export type ParsedAuditRoute = {
  request: AuditSnapshotRequest;
  routeKind: "session" | "task";
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

    return {
      request: buildAuditSnapshotRequest(search, sessionId, taskNodeId),
      routeKind: "task",
    };
  }

  const sessionMatch = pathname.match(/^\/sessions\/([^/]+)\/audit\/?$/);
  if (sessionMatch !== null) {
    const sessionId = decodeSegment(sessionMatch[1]);
    if (sessionId === null) {
      return null;
    }

    return {
      request: buildAuditSnapshotRequest(search, sessionId),
      routeKind: "session",
    };
  }

  return null;
}

export function buildAuditLocation(
  route: ParsedAuditRoute,
  query: {
    filter: AuditFilterKind;
    recordId: AuditRecordId | null;
  },
): string {
  const routeQuery: AuditRouteQuery = {
    entry: route.request.entry,
    filter: query.filter,
    recordId: query.recordId ?? undefined,
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

function decodeSegment(value: string): string | null {
  try {
    return decodeURIComponent(value);
  } catch {
    return null;
  }
}
