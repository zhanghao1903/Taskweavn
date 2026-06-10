import type { ApiUiBoundaryState } from "../../shared/api/apiUiMapping";
import type {
  AuditCompleteness,
  AuditFilterKind,
  AuditPageSnapshot,
  AuditRecordKind,
  AuditVerdict,
} from "../../shared/api/types";
import type { AuditPageRuntimeState } from "./auditRuntimeEvents";
import { enUS, type UiTextCatalog } from "../../shared/ui-text";

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

const metricFilterKinds: AuditFilterKind[] = [
  "confirmations",
  "risks",
  "files",
  "results",
];

export function auditOverviewMetricFilterItems(
  uiText: UiTextCatalog = enUS,
): Array<{ filter: AuditFilterKind; label: string }> {
  return metricFilterKinds.map((filter) => ({
    filter,
    label: auditFilterLabel(filter, undefined, uiText),
  }));
}

export function auditFilterLabel(
  filter: AuditFilterKind,
  fallback?: string,
  uiText: UiTextCatalog = enUS,
): string {
  return uiText.audit.filters[filter] ?? fallback ?? filter;
}

export function auditLiveStatusCopy(
  liveState: AuditPageRuntimeState,
  uiText: UiTextCatalog = enUS,
): { message: string; title: string } {
  switch (liveState.status) {
    case "refreshing":
      return {
        message:
          liveState.message ?? uiText.audit.liveStatus.refreshingMessage,
        title: uiText.audit.liveStatus.refreshingTitle,
      };
    case "stale":
      return {
        message:
          liveState.message ??
          uiText.audit.liveStatus.staleMessage,
        title: uiText.audit.liveStatus.staleTitle,
      };
    case "disconnected":
      return {
        message:
          liveState.message ??
          uiText.audit.liveStatus.disconnectedMessage,
        title: uiText.audit.liveStatus.disconnectedTitle,
      };
    case "connected":
      return {
        message: "",
        title: "",
      };
  }
}

export function auditScopeLabel(
  snapshot: AuditPageSnapshot,
  uiText: UiTextCatalog = enUS,
): string {
  return uiText.audit.labels.scope({
    kind: auditScopeKindLabel(snapshot.scope.kind, uiText),
  });
}

export function auditSubjectLabel(snapshot: AuditPageSnapshot): string {
  return snapshot.selectedTask?.title ?? snapshot.session.name;
}

export function auditScopeStatusText(
  snapshot: AuditPageSnapshot,
  uiText: UiTextCatalog = enUS,
): string {
  if (snapshot.scope.kind === "task") {
    return uiText.audit.scopeStatus({
      kind: auditScopeKindLabel(snapshot.scope.kind, uiText),
      status: snapshot.session.status,
    });
  }

  if (snapshot.scope.kind === "session") {
    return uiText.audit.scopeStatus({
      kind: auditScopeKindLabel(snapshot.scope.kind, uiText),
      status: snapshot.session.status,
    });
  }

  return uiText.audit.scopeStatus({
    kind: auditScopeKindLabel(snapshot.scope.kind, uiText),
    status: snapshot.session.status,
  });
}

export function auditWorkflowLabel(
  value: string | undefined,
  uiText: UiTextCatalog = enUS,
): string {
  if (value === "Task authoring") {
    return uiText.audit.labels.taskAuthoring;
  }
  if (value === "Task Planning & Execution") {
    return uiText.audit.labels.taskPlanningExecution;
  }
  return value ?? uiText.audit.labels.auditWorkflow;
}

export function auditRecordKindLabel(
  value: AuditRecordKind,
  uiText: UiTextCatalog = enUS,
): string {
  return uiText.audit.recordKinds[value] ?? value.replaceAll("_", " ");
}

export function auditSourceLabel(
  value: string,
  uiText: UiTextCatalog = enUS,
): string {
  return uiText.audit.sourceLabels[value] ?? value;
}

export function auditActorLabel(
  value: string,
  uiText: UiTextCatalog = enUS,
): string {
  return uiText.audit.actors[value] ?? value;
}

export function auditFlagLabel(
  value: string,
  uiText: UiTextCatalog = enUS,
): string {
  return uiText.audit.flags[value] ?? value;
}

export function auditConfidenceLabel(
  value: string,
  uiText: UiTextCatalog = enUS,
): string {
  return uiText.audit.confidenceLevels[value] ?? value;
}

function auditScopeKindLabel(
  value: string,
  uiText: UiTextCatalog,
): string {
  if (value === "task") {
    return uiText.audit.labels.task;
  }
  if (value === "session") {
    return uiText.audit.labels.session;
  }
  return value;
}

export function auditBoundaryLabel(
  boundary: ApiUiBoundaryState,
  uiText: UiTextCatalog = enUS,
): string {
  return uiText.audit.boundary[boundary.kind] ?? boundary.kind;
}

export function auditVerdictNoticeTitle(
  value: AuditVerdict,
  uiText: UiTextCatalog = enUS,
): string {
  return uiText.audit.verdictNotice[value] ?? "";
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

export function auditVerdictLabel(
  value: AuditVerdict,
  uiText: UiTextCatalog = enUS,
): string {
  return uiText.audit.verdict[value];
}

export function auditCompletenessLabel(
  value: AuditCompleteness,
  uiText: UiTextCatalog = enUS,
): string {
  return uiText.audit.completeness[value];
}
