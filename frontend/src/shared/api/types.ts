export type ProjectId = string;
export type WorkflowId = string;
export type SessionId = string;
export type TaskTreeId = string;
export type TaskNodeId = string;
export type MessageId = string;
export type ConfirmationId = string;
export type ResultId = string;
export type CommandId = string;
export type EventCursor = string;

export type TaskRef = {
  kind: "draft" | "published";
  id: string;
};

export type ApiError = {
  code:
    | "bad_request"
    | "not_found"
    | "version_conflict"
    | "command_rejected"
    | "backend_busy"
    | "resync_required"
    | "internal_error";
  message: string;
  retryable: boolean;
  details: Record<string, unknown>;
};

export type QueryResponse<T> = {
  requestId: string;
  ok: boolean;
  data: T | null;
  error: ApiError | null;
  cursor?: EventCursor | null;
  generatedAt: string;
};

export type CommandRequest<TPayload> = {
  commandId: CommandId;
  sessionId: SessionId;
  idempotencyKey?: string | null;
  expectedVersion?: number | null;
  payload: TPayload;
};

export type CommandResult = {
  commandId: CommandId;
  status: "accepted" | "rejected";
  message: string;
  affectedTaskRefs: TaskRef[];
  emittedMessageIds: MessageId[];
  publishedTaskIds: string[];
};

export type RefreshHint = {
  waitForEvents: boolean;
  suggestedQueries: string[];
  affectedTaskRefs: TaskRef[];
};

export type CommandResponse = {
  requestId: string;
  ok: boolean;
  result: CommandResult | null;
  error: ApiError | null;
  refresh: RefreshHint;
};

export type ProjectSummary = {
  id: ProjectId;
  name: string;
};

export type WorkflowSummary = {
  id: WorkflowId;
  name: string;
  description: string;
  inputHint?: string;
  deliveryKind?: "task_tree" | "execution_result" | "result_card" | "audit_review";
};

export type SessionStatus =
  | "new"
  | "understanding"
  | "draft_ready"
  | "running"
  | "waiting_user"
  | "completed"
  | "failed";

export type SessionSummary = {
  id: SessionId;
  projectId: ProjectId;
  workflowId: WorkflowId;
  name: string;
  status: SessionStatus;
  createdAt: string;
  updatedAt: string;
  workspaceLabel?: string;
};

export type TaskTreeStatus =
  | "draft"
  | "published"
  | "running"
  | "completed"
  | "failed";

export type TaskNodeStatus =
  | "draft"
  | "queued"
  | "running"
  | "waiting_user"
  | "done"
  | "failed"
  | "cancelled";

export type TaskNodeBadges = {
  pendingConfirmationCount: number;
  unreadMessageCount: number;
  directFileChangeCount: number;
  subtreeFileChangeCount: number;
};

export type TaskNodePermissions = {
  canEdit: boolean;
  canAppendGuidance: boolean;
  canResolveConfirmation: boolean;
  canPublish: boolean;
  canCancel: boolean;
  canRetry: boolean;
};

export type TaskNodeCardView = {
  id: TaskNodeId;
  taskRef?: TaskRef;
  parentId: TaskNodeId | null;
  title: string;
  summary: string;
  status: TaskNodeStatus;
  depth: number;
  orderIndex: number;
  badges: TaskNodeBadges;
  permissions: TaskNodePermissions;
  version: number;
};

export type TaskTreeView = {
  id: TaskTreeId;
  sessionId: SessionId;
  title: string;
  status: TaskTreeStatus;
  nodes: TaskNodeCardView[];
  version: number;
};

export type MessageKind = "informational" | "actionable" | "response" | "error";

export type SessionMessageView = {
  id: MessageId;
  sessionId: SessionId;
  taskNodeId: TaskNodeId | null;
  taskRef?: TaskRef | null;
  kind: MessageKind;
  title: string;
  body: string;
  createdAt: string;
  relatedConfirmationId?: ConfirmationId | null;
  relatedCommandId?: CommandId | null;
};

export type ConfirmationOptionView = {
  value: string;
  label: string;
  tone?: "primary" | "secondary" | "danger";
};

export type ConfirmationActionView = {
  id: ConfirmationId;
  sessionId: SessionId;
  taskNodeId: TaskNodeId;
  taskRef?: TaskRef | null;
  title: string;
  body: string;
  options: ConfirmationOptionView[];
  defaultOptionValue?: string | null;
  status: "pending" | "resolved" | "expired";
  riskLabel?: string;
  createdAt: string;
  resolvedAt?: string | null;
};

export type ResultSectionView = {
  title: string;
  body: string;
  kind?: "text" | "list" | "metric" | "link";
};

export type ResultCardView = {
  id: ResultId;
  sessionId: SessionId;
  taskNodeId: TaskNodeId | null;
  title: string;
  summary: string;
  sections?: ResultSectionView[];
  updatedAt: string;
};

export type FileChangeItemView = {
  path: string;
  changeType: "created" | "modified" | "deleted" | "renamed";
  summary?: string;
  ownerTaskNodeId?: TaskNodeId | null;
};

export type FileChangeSummaryView = {
  sessionId: SessionId;
  taskNodeId: TaskNodeId | null;
  recursive: boolean;
  changedFiles: FileChangeItemView[];
  summary: string;
  updatedAt: string;
};

export type AuditLinkView = {
  label: string;
  href: string;
  severity?: "info" | "warning" | "danger";
};

export type MainPageSnapshot = {
  project: ProjectSummary;
  workflows: WorkflowSummary[];
  workflow: WorkflowSummary;
  sessions: SessionSummary[];
  session: SessionSummary;
  taskTree: TaskTreeView | null;
  messages: SessionMessageView[];
  pendingConfirmations: ConfirmationActionView[];
  result: ResultCardView | null;
  fileChangeSummary: FileChangeSummaryView | null;
  auditLinks: AuditLinkView[];
  cursor: EventCursor | null;
  generatedAt: string;
};

export type UiEventType =
  | "session.status_changed"
  | "session.resync_required"
  | "task.tree.changed"
  | "task.node.changed"
  | "message.appended"
  | "confirmation.created"
  | "confirmation.resolved"
  | "result.updated"
  | "file_changes.updated"
  | "audit.summary_updated"
  | "command.completed"
  | "command.failed";

export type UiEvent = {
  eventId: string;
  sessionId: SessionId;
  eventType: UiEventType;
  cursor: EventCursor;
  taskNodeIds: TaskNodeId[];
  taskRefs?: TaskRef[];
  messageIds: MessageId[];
  commandId?: CommandId | null;
  payload: Record<string, unknown>;
  createdAt: string;
};
