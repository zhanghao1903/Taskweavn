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
import type { UiTextCatalog } from "../../shared/ui-text";
import type { EventConnectionStatus } from "./mainPageUiTypes";
import type { MainPageStateMetadata } from "./runtime/adapter";

export type BadgePresentation = {
  label: string;
  tone: BadgeTone;
};

type MainPageUiText = UiTextCatalog["main"];

export function selectSessionStatusPresentation(
  status: SessionStatus,
  uiText?: MainPageUiText,
): BadgePresentation {
  const presentations: Record<SessionStatus, BadgePresentation> = {
    completed: {
      label: uiText?.detail.status.session.completed ?? "Completed",
      tone: "success",
    },
    draft_ready: {
      label: uiText?.detail.status.session.draft_ready ?? "Draft ready",
      tone: "blue",
    },
    failed: {
      label: uiText?.detail.status.session.failed ?? "Failed",
      tone: "danger",
    },
    new: {
      label: uiText?.detail.status.session.new ?? "New session",
      tone: "neutral",
    },
    running: {
      label: uiText?.detail.status.session.running ?? "Running",
      tone: "blue",
    },
    understanding: {
      label: uiText?.detail.status.session.understanding ?? "Understanding",
      tone: "blue",
    },
    waiting_user: {
      label: uiText?.detail.status.session.waiting_user ?? "Waiting for user",
      tone: "warning",
    },
  };

  return presentations[status];
}

export function selectTaskNodeStatusPresentation(
  status: TaskNodeStatus,
  uiText?: MainPageUiText,
): BadgePresentation {
  const presentations: Record<TaskNodeStatus, BadgePresentation> = {
    cancelled: {
      label: uiText?.detail.status.taskNode.cancelled ?? "Cancelled",
      tone: "danger",
    },
    done: {
      label: uiText?.detail.status.taskNode.done ?? "Done",
      tone: "success",
    },
    draft: {
      label: uiText?.detail.status.taskNode.draft ?? "Draft",
      tone: "neutral",
    },
    failed: {
      label: uiText?.detail.status.taskNode.failed ?? "Failed",
      tone: "danger",
    },
    queued: {
      label: uiText?.detail.status.taskNode.queued ?? "Queued",
      tone: "neutral",
    },
    running: {
      label: uiText?.detail.status.taskNode.running ?? "Running",
      tone: "blue",
    },
    waiting_user: {
      label: uiText?.detail.status.taskNode.waiting_user ?? "Waiting",
      tone: "warning",
    },
  };

  return presentations[status];
}

export function selectPlanningStatePresentation(
  state: PlanningState,
  uiText?: MainPageUiText,
): BadgePresentation {
  const presentations: Record<PlanningState, BadgePresentation> = {
    assessing: {
      label: uiText?.detail.status.planning.assessing ?? "Understanding",
      tone: "blue",
    },
    awaiting_user: {
      label: uiText?.detail.status.planning.awaiting_user ?? "Waiting for user",
      tone: "warning",
    },
    cancelled: {
      label: uiText?.detail.status.planning.cancelled ?? "Cancelled",
      tone: "danger",
    },
    capturing_input: {
      label: uiText?.detail.status.planning.capturing_input ?? "Capturing input",
      tone: "blue",
    },
    draft_ready: {
      label: uiText?.detail.status.planning.draft_ready ?? "Draft ready",
      tone: "blue",
    },
    empty: {
      label: uiText?.detail.status.planning.empty ?? "New session",
      tone: "neutral",
    },
    published: {
      label: uiText?.detail.status.planning.published ?? "Published",
      tone: "success",
    },
    ready_to_plan: {
      label: uiText?.detail.status.planning.ready_to_plan ?? "Ready to plan",
      tone: "blue",
    },
    rejected: {
      label: uiText?.detail.status.planning.rejected ?? "Rejected",
      tone: "danger",
    },
    unknown: {
      label: uiText?.detail.status.planning.unknown ?? "Unknown",
      tone: "neutral",
    },
  };

  return presentations[state];
}

export function selectTaskReadinessPresentation(
  readiness: TaskNodeReadiness,
  uiText?: MainPageUiText,
): BadgePresentation {
  const presentations: Record<TaskNodeReadiness, BadgePresentation> = {
    accepted: {
      label: uiText?.detail.status.readiness.accepted ?? "Accepted",
      tone: "blue",
    },
    cancelled: {
      label: uiText?.detail.status.readiness.cancelled ?? "Cancelled",
      tone: "danger",
    },
    draft: {
      label: uiText?.detail.status.readiness.draft ?? "Draft",
      tone: "neutral",
    },
    published: {
      label: uiText?.detail.status.readiness.published ?? "Published",
      tone: "blue",
    },
    unknown: {
      label: uiText?.detail.status.readiness.unknown ?? "Unknown",
      tone: "neutral",
    },
  };

  return presentations[readiness];
}

export function selectExecutionStatusPresentation(
  status: ExecutionStatus,
  uiText?: MainPageUiText,
): BadgePresentation {
  const presentations: Record<ExecutionStatus, BadgePresentation> = {
    cancelled: {
      label: uiText?.detail.status.execution.cancelled ?? "Cancelled",
      tone: "danger",
    },
    done: {
      label: uiText?.detail.status.execution.done ?? "Done",
      tone: "success",
    },
    failed: {
      label: uiText?.detail.status.execution.failed ?? "Failed",
      tone: "danger",
    },
    not_started: {
      label: uiText?.detail.status.execution.not_started ?? "Not started",
      tone: "neutral",
    },
    pending: {
      label: uiText?.detail.status.execution.pending ?? "Queued",
      tone: "neutral",
    },
    running: {
      label: uiText?.detail.status.execution.running ?? "Running",
      tone: "blue",
    },
    waiting_for_user: {
      label: uiText?.detail.status.execution.waiting_for_user ?? "Waiting",
      tone: "warning",
    },
    unknown: {
      label: uiText?.detail.status.execution.unknown ?? "Unknown",
      tone: "neutral",
    },
  };

  return presentations[status];
}

export function selectConfirmationStatusPresentation(
  status: ConfirmationStatus,
  uiText?: MainPageUiText,
): BadgePresentation {
  const presentations: Record<ConfirmationStatus, BadgePresentation> = {
    expired: {
      label: uiText?.detail.status.confirmation.expired ?? "Expired",
      tone: "danger",
    },
    pending: {
      label: uiText?.detail.status.confirmation.pending ?? "Waiting",
      tone: "warning",
    },
    resolved: {
      label: uiText?.detail.status.confirmation.resolved ?? "Confirmed",
      tone: "success",
    },
  };

  return presentations[status];
}

export function selectTaskNodeDimensionPresentation(
  node: TaskNodeCardView,
  uiText?: MainPageUiText,
): BadgePresentation {
  if (
    node.interruptionRequested &&
    (node.execution === "running" || node.status === "running")
  ) {
    return {
      label: uiText?.detail.status.stopping ?? "stopping",
      tone: "warning",
    };
  }

  if (node.readiness === "draft") {
    return selectTaskReadinessPresentation(node.readiness, uiText);
  }

  if (node.confirmation) {
    return selectConfirmationStatusPresentation(node.confirmation, uiText);
  }

  if (
    node.execution &&
    node.execution !== "not_started" &&
    node.execution !== "unknown"
  ) {
    return selectExecutionStatusPresentation(node.execution, uiText);
  }

  if (node.readiness) {
    return selectTaskReadinessPresentation(node.readiness, uiText);
  }

  return selectTaskNodeStatusPresentation(node.status, uiText);
}

export function selectMessageKindPresentation(
  kind: MessageKind,
  uiText?: MainPageUiText,
): BadgePresentation {
  const presentations: Record<MessageKind, BadgePresentation> = {
    actionable: {
      label: uiText?.detail.status.messageKind.actionable ?? "Needs reply",
      tone: "warning",
    },
    error: {
      label: uiText?.detail.status.messageKind.error ?? "Error",
      tone: "danger",
    },
    informational: {
      label: uiText?.detail.status.messageKind.informational ?? "Update",
      tone: "blue",
    },
    response: {
      label: uiText?.detail.status.messageKind.response ?? "Result",
      tone: "blue",
    },
  };

  return presentations[kind];
}

export function selectEventConnectionStatusPresentation(
  status: EventConnectionStatus,
  uiText?: MainPageUiText,
): BadgePresentation {
  const presentations: Record<EventConnectionStatus, BadgePresentation> = {
    connected: {
      label: uiText?.detail.status.eventConnection.connected ?? "Events live",
      tone: "success",
    },
    disconnected: {
      label:
        uiText?.detail.status.eventConnection.disconnected ?? "Events offline",
      tone: "neutral",
    },
    resyncing: {
      label: uiText?.detail.status.eventConnection.resyncing ?? "Resyncing",
      tone: "warning",
    },
  };

  return presentations[status];
}

export function selectFileChangeTypePresentation(
  changeType: FileChangeSummaryView["changedFiles"][number]["changeType"],
  uiText?: MainPageUiText,
): BadgePresentation {
  if (changeType === "created") {
    return {
      label: uiText?.detail.fileChangeTypes.created ?? "Created",
      tone: "success",
    };
  }

  if (changeType === "deleted") {
    return {
      label: uiText?.detail.fileChangeTypes.deleted ?? "Deleted",
      tone: "danger",
    };
  }

  if (changeType === "renamed") {
    return {
      label: uiText?.detail.fileChangeTypes.renamed ?? "Renamed",
      tone: "blue",
    };
  }

  return {
    label: uiText?.detail.fileChangeTypes.modified ?? "Modified",
    tone: "warning",
  };
}

export function selectAuditVerdictPresentation(
  verdict: AuditVerdict,
  uiText?: MainPageUiText,
): BadgePresentation {
  const presentations: Record<AuditVerdict, BadgePresentation> = {
    failed: {
      label: uiText?.detail.status.auditVerdict.failed ?? "Failed",
      tone: "danger",
    },
    inconclusive: {
      label:
        uiText?.detail.status.auditVerdict.inconclusive ?? "Inconclusive",
      tone: "warning",
    },
    not_available: {
      label:
        uiText?.detail.status.auditVerdict.not_available ?? "Not available",
      tone: "neutral",
    },
    passed: {
      label: uiText?.detail.status.auditVerdict.passed ?? "Passed",
      tone: "success",
    },
    warning: {
      label: uiText?.detail.status.auditVerdict.warning ?? "Warning",
      tone: "warning",
    },
  };

  return presentations[verdict];
}

export function selectAuditSummaryPresentation(
  auditSummary: AuditSummaryView | null | undefined,
  uiText?: MainPageUiText,
): BadgePresentation {
  return selectAuditVerdictPresentation(
    auditSummary?.verdict ?? "not_available",
    uiText,
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
  uiText?: MainPageUiText,
): BadgePresentation {
  const permissions = snapshot.permissions;

  if (permissions?.readonlyReason && !permissions.canAppendGuidance) {
    return permissions.readonlyReason.toLowerCase().includes("stale")
      ? { label: uiText?.detail.status.stale ?? "Stale", tone: "warning" }
      : {
          label: uiText?.detail.status.readOnly ?? "Read-only",
          tone: "danger",
        };
  }

  const planningState = snapshot.planning?.state;
  const planningPresentation = planningState
    ? selectPlanningStatePresentation(planningState, uiText)
    : selectSessionStatusPresentation(snapshot.session.status, uiText);

  const executionRollup = snapshot.taskTree?.executionRollup;
  const hasStoppingTask =
    snapshot.taskTree?.nodes.some(
      (node) =>
        node.interruptionRequested &&
        (node.execution === "running" || node.status === "running"),
    ) ?? false;

  if (hasStoppingTask) {
    return {
      label: uiText?.detail.status.stopping ?? "Stopping",
      tone: "warning",
    };
  }

  if (executionRollup && executionRollup.failed > 0) {
    return metadata.topStatus === "Recoverable error"
      ? selectTopStatusPresentation(metadata)
      : {
          label: uiText?.detail.status.session.failed ?? "Failed",
          tone: "danger",
        };
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
    return {
      label: uiText?.detail.status.session.waiting_user ?? "Waiting for user",
      tone: "warning",
    };
  }

  if (metadata.topStatus === "Syncing") {
    return selectTopStatusPresentation(metadata);
  }

  if ((executionRollup?.running ?? 0) > 0) {
    return {
      label: uiText?.detail.status.primaryExecutionRunning ?? "Executing",
      tone: "blue",
    };
  }

  if (
    executionRollup &&
    executionRollup.total > 0 &&
    executionRollup.done === executionRollup.total
  ) {
    return metadata.topStatus === "Review"
      ? selectTopStatusPresentation(metadata)
      : {
          label: uiText?.detail.status.session.completed ?? "Completed",
          tone: "success",
        };
  }

  if ((executionRollup?.pending ?? 0) > 0) {
    return {
      label: uiText?.detail.status.execution.pending ?? "Queued",
      tone: "neutral",
    };
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
    summary: `Recursive summary: ${changedFiles.length} files changed in the selected task and its children.`,
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
