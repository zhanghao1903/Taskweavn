export type SessionId = string;
export type TaskId = string;
export type MessageId = string;
export type ConfirmationId = string;
export type FileChangeId = string;
export type Cursor = string;

export type TaskStatus =
  | "draft"
  | "pending"
  | "running"
  | "done"
  | "failed"
  | "cancelled";

export type TaskEditMode = "global" | "task_scoped";
export type MessageType = "user" | "agent" | "system" | "confirmation" | "result";
export type TaskMessageScope = "direct" | "subtree";

export type SessionStatus = "active" | "awaiting_user" | "finished" | "archived";

export type TaskBadge = {
  label: string;
  tone: "neutral" | "info" | "success" | "warning" | "danger";
};

export type TaskNodeSummary = {
  taskId: TaskId;
  parentId: TaskId | null;
  title: string;
  intentPreview: string;
  status: TaskStatus;
  orderIndex: number;
  depth: number;
  badges: TaskBadge[];
  childIds: TaskId[];
  hasPendingConfirmation: boolean;
  unreadMessageCount: number;
  fileChangeCount: number;
};

export type TaskTreeView = {
  rootTaskId: TaskId;
  nodes: TaskNodeSummary[];
};

export type TaskPermissions = {
  canEdit: boolean;
  canAppendGuidance: boolean;
  canResolveConfirmation: boolean;
  canPublish: boolean;
  canCancel: boolean;
  canRetry: boolean;
};

export type TaskSummaryView = {
  result: string | null;
  failureReason: string | null;
  nextSteps: string[];
};

export type TaskNodeDetail = {
  summary: TaskNodeSummary;
  intent: string;
  constraints: string[];
  permissions: TaskPermissions;
  resultSummary: TaskSummaryView;
};

export type SessionOverview = {
  sessionId: SessionId;
  name: string;
  status: SessionStatus;
  activeTaskId: TaskId | null;
  rootTasks: TaskNodeSummary[];
  pendingConfirmationCount: number;
};

export type SessionMessageView = {
  messageId: MessageId;
  sessionId: SessionId;
  taskId: TaskId | null;
  type: MessageType;
  author: "user" | "agent" | "system";
  content: string;
  createdAt: string;
  relatedConfirmationId?: ConfirmationId;
};

export type ConfirmationOption = {
  value: string;
  label: string;
  tone?: "primary" | "neutral" | "danger";
};

export type ConfirmationActionView = {
  confirmationId: ConfirmationId;
  sessionId: SessionId;
  taskId: TaskId;
  title: string;
  description: string;
  riskLabel: string;
  options: ConfirmationOption[];
  defaultValue: string | null;
  status: "pending" | "resolved";
};

export type TaskFileChangeSummary = {
  fileChangeId: FileChangeId;
  ownerTaskId: TaskId;
  path: string;
  changeType: "created" | "modified" | "deleted";
  summary: string;
  fromDescendant: boolean;
};

export type SessionMessageFilters = {
  taskId?: TaskId;
  type?: MessageType;
  cursor?: Cursor;
};

export type ConfirmationFilters = {
  taskId?: TaskId;
};

export type SessionMessagePage = {
  items: SessionMessageView[];
  nextCursor: Cursor | null;
};

export type CommandResult = {
  commandId: string;
  accepted: boolean;
  affectedTaskIds: TaskId[];
};

export type AppendSessionMessageRequest = {
  sessionId: SessionId;
  content: string;
  mode: TaskEditMode;
};

export type AppendTaskMessageRequest = {
  sessionId: SessionId;
  taskId: TaskId;
  content: string;
  mode: "task_scoped";
};

export type UpdateTaskNodeRequest = {
  sessionId: SessionId;
  taskId: TaskId;
  patch: {
    title?: string;
    intent?: string;
    constraintsAdd?: string[];
  };
};

export type ResolveConfirmationRequest = {
  sessionId: SessionId;
  confirmationId: ConfirmationId;
  value: string;
  note?: string;
};

export type SessionEvent = {
  eventId: string;
  sessionId: SessionId;
  taskId?: TaskId;
  type:
    | "task.created"
    | "task.updated"
    | "task.status_changed"
    | "message.appended"
    | "confirmation.created"
    | "confirmation.resolved"
    | "file_change.recorded"
    | "task.summary_updated";
  createdAt: string;
  payload: unknown;
  cursor: Cursor;
};

export type SessionEventSubscription = {
  close(): void;
};

export interface TaskWeavnApi {
  getSessionOverview(sessionId: SessionId): Promise<SessionOverview>;
  listTaskTrees(sessionId: SessionId): Promise<TaskTreeView[]>;
  getTaskNode(sessionId: SessionId, taskId: TaskId): Promise<TaskNodeDetail>;
  listSessionMessages(
    sessionId: SessionId,
    filters?: SessionMessageFilters,
  ): Promise<SessionMessagePage>;
  listTaskMessages(
    sessionId: SessionId,
    taskId: TaskId,
    scope?: TaskMessageScope,
  ): Promise<SessionMessagePage>;
  listPendingConfirmations(
    sessionId: SessionId,
    filters?: ConfirmationFilters,
  ): Promise<ConfirmationActionView[]>;
  getTaskFileChanges(
    sessionId: SessionId,
    taskId: TaskId,
    options?: { recursive?: boolean },
  ): Promise<TaskFileChangeSummary[]>;
  appendSessionMessage(request: AppendSessionMessageRequest): Promise<CommandResult>;
  appendTaskMessage(request: AppendTaskMessageRequest): Promise<CommandResult>;
  updateTaskNode(request: UpdateTaskNodeRequest): Promise<CommandResult>;
  resolveConfirmation(request: ResolveConfirmationRequest): Promise<CommandResult>;
  subscribeSessionEvents(
    sessionId: SessionId,
    cursor?: Cursor,
    onEvent?: (event: SessionEvent) => void,
  ): SessionEventSubscription;
}
