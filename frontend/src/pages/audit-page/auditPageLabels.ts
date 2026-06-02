import type { ApiUiBoundaryState } from "../../shared/api/apiUiMapping";
import type {
  AuditCompleteness,
  AuditFilterKind,
  AuditPageSnapshot,
  AuditVerdict,
} from "../../shared/api/types";
import type { AuditPageRuntimeState } from "./auditRuntimeEvents";

export type AuditVerdictClassKey =
  | "failed"
  | "inconclusive"
  | "passed"
  | "warning";

export const auditOverviewMetricFilters: Array<{
  filter: AuditFilterKind;
  label: string;
}> = [
  { filter: "confirmations", label: "Confirmations" },
  { filter: "risks", label: "Risks" },
  { filter: "files", label: "Files" },
  { filter: "results", label: "Results" },
];

const auditFilterLabels: Record<AuditFilterKind, string> = {
  actions: "Actions",
  all: "All records",
  config: "Config",
  confirmations: "Confirmations",
  files: "Files",
  logs: "Logs",
  results: "Results",
  risks: "Risks",
  system: "System",
};

export function auditFilterLabel(
  filter: AuditFilterKind,
  fallback?: string,
): string {
  return auditFilterLabels[filter] ?? fallback ?? filter;
}

export function auditLiveStatusCopy(
  liveState: AuditPageRuntimeState,
): { message: string; title: string } {
  switch (liveState.status) {
    case "refreshing":
      return {
        message:
          liveState.message ?? "Live audit stream is applying new records.",
        title: "Updating audit evidence",
      };
    case "stale":
      return {
        message:
          liveState.message ??
          "Refreshing from source; current evidence remains readable.",
        title: "Audit snapshot may be stale",
      };
    case "disconnected":
      return {
        message:
          liveState.message ??
          "Manual refresh still works; this page may not update automatically.",
        title: "Live audit updates unavailable",
      };
    case "connected":
      return {
        message: "",
        title: "",
      };
  }
}

export function auditScopeLabel(snapshot: AuditPageSnapshot): string {
  if (snapshot.scope.kind === "task") {
    return "Scope: Task";
  }

  if (snapshot.scope.kind === "session") {
    return "Scope: Session";
  }

  return `Scope: ${snapshot.scope.kind}`;
}

export function auditSubjectLabel(snapshot: AuditPageSnapshot): string {
  return snapshot.selectedTask?.title ?? snapshot.session.name;
}

export function auditScopeStatusText(snapshot: AuditPageSnapshot): string {
  if (snapshot.scope.kind === "task") {
    return `Task audit · ${snapshot.session.status}`;
  }

  if (snapshot.scope.kind === "session") {
    return `Session audit · ${snapshot.session.status}`;
  }

  return `${snapshot.scope.kind} audit · ${snapshot.session.status}`;
}

export function auditBoundaryLabel(boundary: ApiUiBoundaryState): string {
  switch (boundary.kind) {
    case "backend_busy":
      return "Backend busy";
    case "empty":
      return "Empty";
    case "fatal_error":
      return "Fatal error";
    case "hidden_evidence":
      return "Hidden evidence";
    case "loading":
      return "Loading";
    case "partial":
      return "Partial evidence";
    case "permission_denied":
      return "Permission denied";
    case "ready":
      return "Ready";
    case "recoverable_error":
      return "Recoverable error";
    case "stale_resync":
      return "Stale snapshot";
  }
}

export function auditVerdictNoticeTitle(value: AuditVerdict): string {
  switch (value) {
    case "failed":
      return "Audit found a blocking issue.";
    case "inconclusive":
      return "Audit cannot establish confidence yet.";
    case "warning":
      return "Audit found a non-blocking concern.";
    case "not_available":
    case "passed":
      return "";
  }
}

export function auditVerdictClassKey(
  value: AuditVerdict,
): AuditVerdictClassKey | null {
  switch (value) {
    case "failed":
      return "failed";
    case "inconclusive":
      return "inconclusive";
    case "passed":
      return "passed";
    case "warning":
      return "warning";
    case "not_available":
      return null;
  }
}

export function auditVerdictLabel(value: AuditVerdict): string {
  switch (value) {
    case "failed":
      return "Verdict: Failed";
    case "inconclusive":
      return "Verdict: Inconclusive";
    case "not_available":
      return "Verdict: Not available";
    case "passed":
      return "Verdict: Passed";
    case "warning":
      return "Verdict: Warning";
  }
}

export function auditCompletenessLabel(value: AuditCompleteness): string {
  switch (value) {
    case "complete":
      return "Complete";
    case "failed":
      return "Failed";
    case "hidden":
      return "Hidden";
    case "not_started":
      return "Not started";
    case "partial":
      return "Partial";
    case "running":
      return "Running";
  }
}
