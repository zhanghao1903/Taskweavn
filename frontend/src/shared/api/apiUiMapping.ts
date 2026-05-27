import type {
  ActionAvailability,
  ApiError,
  AuditPageSnapshot,
  AuditPageState,
  QueryResponse,
} from "./types";

export type ApiUiBoundaryKind =
  | "ready"
  | "loading"
  | "empty"
  | "partial"
  | "hidden_evidence"
  | "permission_denied"
  | "stale_resync"
  | "backend_busy"
  | "recoverable_error"
  | "fatal_error";

export type ApiUiBoundaryState = {
  kind: ApiUiBoundaryKind;
  code?: string;
  message: string;
  retryable: boolean;
  shouldResync: boolean;
  disableMutations: boolean;
};

export function mapApiErrorToUiBoundary(
  error: ApiError,
): ApiUiBoundaryState {
  switch (error.code) {
    case "permission_denied":
      return boundary({
        code: error.code,
        disableMutations: true,
        kind: "permission_denied",
        message: error.message,
        retryable: error.retryable,
      });
    case "version_conflict":
    case "resync_required":
      return boundary({
        code: error.code,
        disableMutations: true,
        kind: "stale_resync",
        message: error.message,
        retryable: true,
        shouldResync: true,
      });
    case "backend_busy":
      return boundary({
        code: error.code,
        disableMutations: true,
        kind: "backend_busy",
        message: error.message,
        retryable: true,
      });
    case "bad_request":
    case "command_rejected":
    case "not_found":
      return boundary({
        code: error.code,
        kind: "recoverable_error",
        message: error.message,
        retryable: error.retryable,
      });
    case "internal_error":
      return boundary({
        code: error.code,
        kind: error.retryable ? "recoverable_error" : "fatal_error",
        message: error.message,
        retryable: error.retryable,
      });
  }
}

export function mapQueryResponseToUiBoundary<T>(
  response: QueryResponse<T>,
): ApiUiBoundaryState {
  if (!response.ok && response.error !== null) {
    return mapApiErrorToUiBoundary(response.error);
  }

  if (!response.ok) {
    return boundary({
      code: "unknown_query_error",
      kind: "recoverable_error",
      message: "Query failed without a structured API error.",
      retryable: true,
    });
  }

  if (response.data === null) {
    return boundary({
      code: "empty_query_data",
      kind: "empty",
      message: "Query succeeded but returned no data.",
      retryable: true,
    });
  }

  return boundary({
    kind: "ready",
    message: "Query data is ready.",
    retryable: false,
  });
}

export function mapAuditPageStateToUiBoundary(
  pageState: AuditPageState,
): ApiUiBoundaryState {
  switch (pageState.kind) {
    case "loading":
      return boundary({
        disableMutations: true,
        kind: "loading",
        message: pageState.message,
        retryable: false,
      });
    case "ready":
      return boundary({
        kind: "ready",
        message: "Audit snapshot is ready.",
        retryable: false,
      });
    case "empty":
      return boundary({
        kind: "empty",
        message: pageState.reason,
        retryable: false,
      });
    case "partial":
      return boundary({
        kind: "partial",
        message: pageState.reason,
        retryable: true,
      });
    case "hidden_evidence":
      return boundary({
        kind: "hidden_evidence",
        message: pageState.reason,
        retryable: false,
      });
    case "permission_denied":
      return boundary({
        disableMutations: true,
        kind: "permission_denied",
        message: pageState.reason,
        retryable: false,
      });
    case "error":
      return boundary({
        code: pageState.code,
        disableMutations: true,
        kind: pageState.retryable ? "recoverable_error" : "fatal_error",
        message: pageState.message,
        retryable: pageState.retryable,
      });
    case "stale":
      return boundary({
        disableMutations: true,
        kind: "stale_resync",
        message: pageState.reason,
        retryable: true,
        shouldResync: true,
      });
  }
}

export function mapAuditSnapshotToUiBoundary(
  snapshot: AuditPageSnapshot,
): ApiUiBoundaryState {
  if (!snapshot.permissions.canViewAudit) {
    return boundary({
      disableMutations: true,
      kind: "permission_denied",
      message:
        snapshot.permissions.readonlyReason ??
        "Current user cannot view this audit scope.",
      retryable: false,
    });
  }

  return mapAuditPageStateToUiBoundary(snapshot.pageState);
}

export function actionAvailabilityForBoundary(
  state: ApiUiBoundaryState,
): ActionAvailability {
  switch (state.kind) {
    case "permission_denied":
      return "disabled_permission";
    case "stale_resync":
      return "disabled_stale";
    case "backend_busy":
      return "pending_command";
    case "loading":
      return "disabled_state";
    case "fatal_error":
    case "recoverable_error":
      return state.disableMutations ? "disabled_state" : "enabled";
    case "empty":
    case "hidden_evidence":
    case "partial":
    case "ready":
      return "enabled";
  }
}

function boundary({
  code,
  disableMutations = false,
  kind,
  message,
  retryable,
  shouldResync = false,
}: {
  code?: string;
  disableMutations?: boolean;
  kind: ApiUiBoundaryKind;
  message: string;
  retryable: boolean;
  shouldResync?: boolean;
}): ApiUiBoundaryState {
  return {
    code,
    disableMutations,
    kind,
    message,
    retryable,
    shouldResync,
  };
}
