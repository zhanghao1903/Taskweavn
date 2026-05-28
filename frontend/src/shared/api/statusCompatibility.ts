import type {
  AuditLinkView,
  AuditVerdict,
  ConfirmationStatus,
  ExecutionStatus,
  PlanningState,
  SessionStatus,
  TaskNodeBadges,
  TaskNodeCardView,
  TaskNodeReadiness,
  TaskNodeStatus,
  TaskTreeReadiness,
  TaskTreeStatus,
} from "./types";

export type LegacyTaskNodeStatusDimensions = {
  readiness: TaskNodeReadiness;
  execution: ExecutionStatus;
  confirmation: ConfirmationStatus | null;
  auditVerdict: AuditVerdict;
};

export function mapLegacySessionStatusToPlanningState(
  status: SessionStatus,
): PlanningState {
  switch (status) {
    case "new":
      return "empty";
    case "understanding":
      return "assessing";
    case "draft_ready":
      return "draft_ready";
    case "running":
    case "waiting_user":
    case "completed":
      return "published";
    case "failed":
      return "unknown";
  }
}

export function mapLegacySessionStatusToExecutionStatus(
  status: SessionStatus,
): ExecutionStatus {
  switch (status) {
    case "new":
    case "understanding":
    case "draft_ready":
      return "not_started";
    case "running":
      return "running";
    case "waiting_user":
      return "pending";
    case "completed":
      return "done";
    case "failed":
      return "failed";
  }
}

export function mapLegacyTaskTreeStatusToReadiness(
  status: TaskTreeStatus,
): TaskTreeReadiness {
  switch (status) {
    case "draft":
      return "draft";
    case "published":
    case "running":
    case "completed":
    case "failed":
      return "published";
  }
}

export function mapLegacyTaskTreeStatusToExecutionStatus(
  status: TaskTreeStatus,
): ExecutionStatus {
  switch (status) {
    case "draft":
      return "not_started";
    case "published":
      return "pending";
    case "running":
      return "running";
    case "completed":
      return "done";
    case "failed":
      return "failed";
  }
}

export function mapLegacyTaskNodeStatusToReadiness(
  status: TaskNodeStatus,
): TaskNodeReadiness {
  switch (status) {
    case "draft":
      return "draft";
    case "queued":
    case "running":
    case "waiting_user":
    case "done":
    case "failed":
      return "published";
    case "cancelled":
      return "cancelled";
  }
}

export function mapLegacyTaskNodeStatusToExecutionStatus(
  status: TaskNodeStatus,
): ExecutionStatus {
  switch (status) {
    case "draft":
      return "not_started";
    case "queued":
      return "pending";
    case "running":
      return "running";
    case "waiting_user":
      return "pending";
    case "done":
      return "done";
    case "failed":
      return "failed";
    case "cancelled":
      return "cancelled";
  }
}

export function mapLegacyTaskNodeStatusToConfirmationStatus(
  status: TaskNodeStatus,
  badges?: Pick<TaskNodeBadges, "pendingConfirmationCount">,
): ConfirmationStatus | null {
  if (status === "waiting_user") {
    return "pending";
  }

  if (badges !== undefined && badges.pendingConfirmationCount > 0) {
    return "pending";
  }

  return null;
}

export function mapLegacyAuditLinkSeverityToVerdict(
  severity?: AuditLinkView["severity"],
): AuditVerdict {
  switch (severity) {
    case "warning":
      return "warning";
    case "danger":
      return "failed";
    case "info":
    case undefined:
      return "not_available";
  }
}

export function deriveLegacyTaskNodeStatusDimensions(
  node: Pick<TaskNodeCardView, "badges" | "status"> & {
    auditLinkSeverity?: AuditLinkView["severity"];
  },
): LegacyTaskNodeStatusDimensions {
  return {
    auditVerdict: mapLegacyAuditLinkSeverityToVerdict(node.auditLinkSeverity),
    confirmation: mapLegacyTaskNodeStatusToConfirmationStatus(
      node.status,
      node.badges,
    ),
    execution: mapLegacyTaskNodeStatusToExecutionStatus(node.status),
    readiness: mapLegacyTaskNodeStatusToReadiness(node.status),
  };
}
