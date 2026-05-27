import type {
  AuditSummaryView,
  AuditVerdict,
  ConfirmationActionView,
  FileChangeSummaryView,
  MessageKind,
  ResultCardView,
  SessionStatus,
  SessionMessageView,
  TaskNodeCardView,
  TaskNodeId,
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
