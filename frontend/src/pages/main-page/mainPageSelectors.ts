import type {
  AuditSummaryView,
  AuditVerdict,
  ConfirmationActionView,
  ConfirmationStatus,
  ExecutionStatus,
  MainPageSnapshot,
  FileChangeSummaryView,
  MessageKind,
  PlanningState,
  ResultCardView,
  SessionStatus,
  SessionMessageView,
  TaskNodeCardView,
  TaskNodeId,
  TaskNodeReadiness,
  TaskNodeStatus,
} from "../../shared/api/types";
import type { BadgeTone, ButtonVariant } from "../../shared/components";
import type { EventConnectionStatus } from "./mainPageUiTypes";
import type { MainPageStateMetadata } from "./runtime/adapter";

export type BadgePresentation = {
  label: string;
  tone: BadgeTone;
};

export function selectSessionStatusPresentation(
  status: SessionStatus,
): BadgePresentation {
  const presentations: Record<SessionStatus, BadgePresentation> = {
    completed: { label: "Completed", tone: "success" },
    draft_ready: { label: "Draft ready", tone: "blue" },
    failed: { label: "Failed", tone: "danger" },
    new: { label: "New session", tone: "neutral" },
    running: { label: "Running", tone: "blue" },
    understanding: { label: "Understanding", tone: "blue" },
    waiting_user: { label: "Waiting for user", tone: "warning" },
  };

  return presentations[status];
}

export function selectTaskNodeStatusPresentation(
  status: TaskNodeStatus,
): BadgePresentation {
  const presentations: Record<TaskNodeStatus, BadgePresentation> = {
    cancelled: { label: "cancelled", tone: "danger" },
    done: { label: "done", tone: "success" },
    draft: { label: "draft", tone: "neutral" },
    failed: { label: "failed", tone: "danger" },
    queued: { label: "queued", tone: "neutral" },
    running: { label: "running", tone: "blue" },
    waiting_user: { label: "waiting user", tone: "warning" },
  };

  return presentations[status];
}

export function selectPlanningStatePresentation(
  state: PlanningState,
): BadgePresentation {
  const presentations: Record<PlanningState, BadgePresentation> = {
    assessing: { label: "Understanding", tone: "blue" },
    awaiting_user: { label: "Waiting for user", tone: "warning" },
    cancelled: { label: "Cancelled", tone: "danger" },
    capturing_input: { label: "Capturing input", tone: "blue" },
    draft_ready: { label: "Draft ready", tone: "blue" },
    empty: { label: "New session", tone: "neutral" },
    published: { label: "Published", tone: "success" },
    ready_to_plan: { label: "Ready to plan", tone: "blue" },
    rejected: { label: "Rejected", tone: "danger" },
    unknown: { label: "Unknown", tone: "neutral" },
  };

  return presentations[state];
}

export function selectTaskReadinessPresentation(
  readiness: TaskNodeReadiness,
): BadgePresentation {
  const presentations: Record<TaskNodeReadiness, BadgePresentation> = {
    accepted: { label: "accepted", tone: "blue" },
    cancelled: { label: "cancelled", tone: "danger" },
    draft: { label: "draft", tone: "neutral" },
    published: { label: "published", tone: "blue" },
    unknown: { label: "unknown", tone: "neutral" },
  };

  return presentations[readiness];
}

export function selectExecutionStatusPresentation(
  status: ExecutionStatus,
): BadgePresentation {
  const presentations: Record<ExecutionStatus, BadgePresentation> = {
    cancelled: { label: "cancelled", tone: "danger" },
    done: { label: "done", tone: "success" },
    failed: { label: "failed", tone: "danger" },
    not_started: { label: "not started", tone: "neutral" },
    pending: { label: "queued", tone: "neutral" },
    running: { label: "running", tone: "blue" },
    unknown: { label: "unknown", tone: "neutral" },
  };

  return presentations[status];
}

export function selectConfirmationStatusPresentation(
  status: ConfirmationStatus,
): BadgePresentation {
  const presentations: Record<ConfirmationStatus, BadgePresentation> = {
    expired: { label: "expired", tone: "danger" },
    pending: { label: "waiting user", tone: "warning" },
    resolved: { label: "confirmed", tone: "success" },
  };

  return presentations[status];
}

export function selectTaskNodeDimensionPresentation(
  node: TaskNodeCardView,
): BadgePresentation {
  if (node.readiness === "draft") {
    return selectTaskReadinessPresentation(node.readiness);
  }

  if (node.confirmation) {
    return selectConfirmationStatusPresentation(node.confirmation);
  }

  if (
    node.execution &&
    node.execution !== "not_started" &&
    node.execution !== "unknown"
  ) {
    return selectExecutionStatusPresentation(node.execution);
  }

  if (node.readiness) {
    return selectTaskReadinessPresentation(node.readiness);
  }

  return selectTaskNodeStatusPresentation(node.status);
}

export function selectMessageKindPresentation(
  kind: MessageKind,
): BadgePresentation {
  if (kind === "error") {
    return { label: kind, tone: "danger" };
  }

  return {
    label: kind,
    tone: kind === "actionable" ? "warning" : "blue",
  };
}

export function selectEventConnectionStatusPresentation(
  status: EventConnectionStatus,
): BadgePresentation {
  const presentations: Record<EventConnectionStatus, BadgePresentation> = {
    connected: { label: "Events live", tone: "success" },
    disconnected: { label: "Events offline", tone: "neutral" },
    resyncing: { label: "Resyncing", tone: "warning" },
  };

  return presentations[status];
}

export function selectFileChangeTypePresentation(
  changeType: FileChangeSummaryView["changedFiles"][number]["changeType"],
): BadgePresentation {
  if (changeType === "created") {
    return { label: changeType, tone: "success" };
  }

  if (changeType === "deleted") {
    return { label: changeType, tone: "danger" };
  }

  if (changeType === "renamed") {
    return { label: changeType, tone: "blue" };
  }

  return { label: changeType, tone: "warning" };
}

export function selectAuditVerdictPresentation(
  verdict: AuditVerdict,
): BadgePresentation {
  const presentations: Record<AuditVerdict, BadgePresentation> = {
    failed: { label: "Failed", tone: "danger" },
    inconclusive: { label: "Inconclusive", tone: "warning" },
    not_available: { label: "Not available", tone: "neutral" },
    passed: { label: "Passed", tone: "success" },
    warning: { label: "Warning", tone: "warning" },
  };

  return presentations[verdict];
}

export function selectAuditSummaryPresentation(
  auditSummary: AuditSummaryView | null | undefined,
): BadgePresentation {
  return selectAuditVerdictPresentation(
    auditSummary?.verdict ?? "not_available",
  );
}

export function selectTopStatusPresentation(
  metadata: MainPageStateMetadata,
): BadgePresentation {
  return { label: metadata.topStatus, tone: metadata.topStatusTone };
}

export function selectMainPagePrimaryStatusPresentation(
  snapshot: MainPageSnapshot,
  metadata: MainPageStateMetadata,
): BadgePresentation {
  const permissions = snapshot.permissions;

  if (permissions?.readonlyReason && !permissions.canAppendGuidance) {
    return permissions.readonlyReason.toLowerCase().includes("stale")
      ? { label: "Stale", tone: "warning" }
      : { label: "Read-only", tone: "danger" };
  }

  const planningState = snapshot.planning?.state;
  const planningPresentation = planningState
    ? selectPlanningStatePresentation(planningState)
    : selectTopStatusPresentation(metadata);

  const executionRollup = snapshot.taskTree?.executionRollup;

  if (executionRollup && executionRollup.failed > 0) {
    return metadata.topStatus === "Recoverable error"
      ? selectTopStatusPresentation(metadata)
      : { label: "Failed", tone: "danger" };
  }

  if (planningState !== "published") {
    if (
      planningState === "draft_ready" &&
      (metadata.topStatus === "Task selected" ||
        metadata.topStatus === "Editing task")
    ) {
      return selectTopStatusPresentation(metadata);
    }

    return planningPresentation;
  }

  const hasPendingConfirmation =
    snapshot.pendingConfirmations.some(
      (confirmation) => confirmation.status === "pending",
    ) || (executionRollup?.blockedByConfirmation ?? 0) > 0;

  if (hasPendingConfirmation) {
    return { label: "Waiting for user", tone: "warning" };
  }

  if (metadata.topStatus === "Backend busy") {
    return selectTopStatusPresentation(metadata);
  }

  if ((executionRollup?.running ?? 0) > 0) {
    return { label: "Executing", tone: "blue" };
  }

  if (
    executionRollup &&
    executionRollup.total > 0 &&
    executionRollup.done === executionRollup.total
  ) {
    return metadata.topStatus === "Review"
      ? selectTopStatusPresentation(metadata)
      : { label: "Completed", tone: "success" };
  }

  if ((executionRollup?.pending ?? 0) > 0) {
    return { label: "Queued", tone: "neutral" };
  }

  return planningPresentation;
}

export function selectConfirmationOptionVariant(
  tone: ConfirmationActionView["options"][number]["tone"],
): ButtonVariant {
  if (tone === "primary") {
    return "primary";
  }

  if (tone === "danger") {
    return "danger";
  }

  return "secondary";
}

export type TaskScopedProjectionInput = {
  fileChangeSummary: FileChangeSummaryView | null;
  messages: SessionMessageView[];
  nodes: TaskNodeCardView[];
  result: ResultCardView | null;
  selectedTaskNodeId: TaskNodeId | null;
};

export type TaskScopedProjection = {
  fileChangeSummary: FileChangeSummaryView | null;
  isMessageScoped: boolean;
  messages: SessionMessageView[];
  result: ResultCardView | null;
  selectedTask: TaskNodeCardView | undefined;
  totalMessageCount: number;
  visibleMessageCount: number;
};

export function buildTaskScopedProjection({
  fileChangeSummary,
  messages,
  nodes,
  result,
  selectedTaskNodeId,
}: TaskScopedProjectionInput): TaskScopedProjection {
  const selectedTask = selectTaskNode(nodes, selectedTaskNodeId);
  const scopedMessages = selectMessagesInTaskScope(messages, selectedTask, nodes);
  const scopedResult = selectResultInTaskScope(result, selectedTask, nodes);
  const scopedFileChangeSummary = selectFileChangeSummaryInTaskScope(
    fileChangeSummary,
    selectedTask,
    nodes,
  );

  return {
    fileChangeSummary: scopedFileChangeSummary,
    isMessageScoped:
      selectedTask !== undefined && scopedMessages.length !== messages.length,
    messages: scopedMessages,
    result: scopedResult,
    selectedTask,
    totalMessageCount: messages.length,
    visibleMessageCount: scopedMessages.length,
  };
}

export function selectTaskNode(
  nodes: TaskNodeCardView[],
  selectedTaskNodeId: TaskNodeId | null,
): TaskNodeCardView | undefined {
  if (!selectedTaskNodeId) {
    return undefined;
  }

  return nodes.find((node) => node.id === selectedTaskNodeId);
}

export function selectMessagesInTaskScope(
  messages: SessionMessageView[],
  selectedTask: TaskNodeCardView | undefined,
  nodes: TaskNodeCardView[],
): SessionMessageView[] {
  if (!selectedTask) {
    return messages;
  }

  return messages.filter(
    (message) =>
      message.taskNodeId === null ||
      isTaskNodeInScope(selectedTask.id, message.taskNodeId, nodes),
  );
}

export function selectResultInTaskScope(
  result: ResultCardView | null,
  selectedTask: TaskNodeCardView | undefined,
  nodes: TaskNodeCardView[],
): ResultCardView | null {
  if (!result || !selectedTask || result.taskNodeId === null) {
    return result;
  }

  return isTaskNodeInScope(selectedTask.id, result.taskNodeId, nodes)
    ? result
    : null;
}

export function selectFileChangeSummaryInTaskScope(
  summary: FileChangeSummaryView | null,
  selectedTask: TaskNodeCardView | undefined,
  nodes: TaskNodeCardView[],
): FileChangeSummaryView | null {
  if (!summary || !selectedTask) {
    return summary;
  }

  if (summary.taskNodeId === selectedTask.id) {
    return summary;
  }

  const changedFiles = summary.changedFiles.filter(
    (file) =>
      file.ownerTaskNodeId !== undefined &&
      file.ownerTaskNodeId !== null &&
      isTaskNodeInScope(selectedTask.id, file.ownerTaskNodeId, nodes),
  );

  if (changedFiles.length === 0) {
    return null;
  }

  return {
    ...summary,
    changedFiles,
    recursive: true,
    summary: `Recursive summary: ${changedFiles.length} files changed in this TaskNode subtree.`,
    taskNodeId: selectedTask.id,
  };
}

export function isTaskNodeInScope(
  scopeTaskNodeId: TaskNodeId,
  candidateTaskNodeId: TaskNodeId,
  nodes: TaskNodeCardView[],
): boolean {
  if (scopeTaskNodeId === candidateTaskNodeId) {
    return true;
  }

  let cursor = nodes.find((node) => node.id === candidateTaskNodeId);
  const visited = new Set<TaskNodeId>();

  while (cursor?.parentId) {
    if (cursor.parentId === scopeTaskNodeId) {
      return true;
    }

    if (visited.has(cursor.parentId)) {
      return false;
    }

    visited.add(cursor.parentId);
    cursor = nodes.find((node) => node.id === cursor?.parentId);
  }

  return false;
}
