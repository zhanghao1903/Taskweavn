import type {
  AppendSessionMessageRequest,
  AppendTaskMessageRequest,
  CommandResult,
  ConfirmationActionView,
  ConfirmationFilters,
  ResolveConfirmationRequest,
  SessionEventSubscription,
  SessionId,
  SessionMessageFilters,
  SessionMessagePage,
  TaskFileChangeSummary,
  TaskId,
  TaskMessageScope,
  TaskNodeDetail,
  TaskTreeView,
  TaskWeavnApi,
  UpdateTaskNodeRequest,
} from "../contracts";
import {
  confirmations,
  fileChanges,
  messages,
  sessionOverview,
  taskDetails,
  taskTrees,
} from "./mockData";

const delay = <T>(value: T, ms = 120): Promise<T> =>
  new Promise((resolve) => {
    window.setTimeout(() => resolve(structuredClone(value)), ms);
  });

const command = (affectedTaskIds: TaskId[] = []): CommandResult => ({
  commandId: `cmd-${Date.now()}`,
  accepted: true,
  affectedTaskIds,
});

export const mockTaskWeavnApi: TaskWeavnApi = {
  getSessionOverview(sessionId: SessionId) {
    return delay({ ...sessionOverview, sessionId });
  },

  listTaskTrees(_sessionId: SessionId): Promise<TaskTreeView[]> {
    return delay(taskTrees);
  },

  getTaskNode(_sessionId: SessionId, taskId: TaskId): Promise<TaskNodeDetail> {
    const detail = taskDetails[taskId] ?? taskDetails["task-plan"];
    return delay(detail);
  },

  listSessionMessages(
    sessionId: SessionId,
    filters: SessionMessageFilters = {},
  ): Promise<SessionMessagePage> {
    const items = messages.filter((message) => {
      if (message.sessionId !== sessionId) return false;
      if (filters.taskId && message.taskId !== filters.taskId) return false;
      if (filters.type && message.type !== filters.type) return false;
      return true;
    });
    return delay({ items, nextCursor: null });
  },

  listTaskMessages(
    sessionId: SessionId,
    taskId: TaskId,
    scope: TaskMessageScope = "direct",
  ): Promise<SessionMessagePage> {
    const descendantIds =
      scope === "subtree"
        ? new Set(taskTrees.flatMap((tree) => tree.nodes.map((node) => node.taskId)))
        : new Set([taskId]);
    const items = messages.filter(
      (message) =>
        message.sessionId === sessionId &&
        message.taskId !== null &&
        descendantIds.has(message.taskId) &&
        (scope === "subtree" || message.taskId === taskId),
    );
    return delay({ items, nextCursor: null });
  },

  listPendingConfirmations(
    sessionId: SessionId,
    filters: ConfirmationFilters = {},
  ): Promise<ConfirmationActionView[]> {
    return delay(
      confirmations.filter(
        (confirmation) =>
          confirmation.sessionId === sessionId &&
          confirmation.status === "pending" &&
          (!filters.taskId || confirmation.taskId === filters.taskId),
      ),
    );
  },

  getTaskFileChanges(
    _sessionId: SessionId,
    taskId: TaskId,
    options: { recursive?: boolean } = {},
  ): Promise<TaskFileChangeSummary[]> {
    const items = fileChanges.filter((change) => {
      if (change.ownerTaskId === taskId) return true;
      return Boolean(options.recursive && taskId === "task-plan");
    });
    return delay(items);
  },

  appendSessionMessage(request: AppendSessionMessageRequest) {
    return delay(command(request.sessionId ? [] : []), 80);
  },

  appendTaskMessage(request: AppendTaskMessageRequest) {
    return delay(command([request.taskId]), 80);
  },

  updateTaskNode(request: UpdateTaskNodeRequest) {
    return delay(command([request.taskId]), 80);
  },

  resolveConfirmation(request: ResolveConfirmationRequest) {
    const confirmation = confirmations.find(
      (item) => item.confirmationId === request.confirmationId,
    );
    return delay(command(confirmation ? [confirmation.taskId] : []), 80);
  },

  subscribeSessionEvents(): SessionEventSubscription {
    return {
      close() {
        // No-op for the first mock adapter.
      },
    };
  },
};
