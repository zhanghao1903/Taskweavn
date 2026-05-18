import type {
  FileChangeSummaryView,
  ResultCardView,
  SessionMessageView,
  TaskNodeCardView,
  TaskNodeId,
} from "../../shared/api/types";

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
