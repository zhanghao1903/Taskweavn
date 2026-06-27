export type ProjectId = string;
export type WorkflowId = string;
export type WorkspaceId = string;
export type SessionId = string;
export type PlanId = string;
export type TaskTreeId = string;
export type TaskNodeId = string;
export type MessageId = string;
export type ConfirmationId = string;
export type AskId = string;
export type ResultId = string;
export type CommandId = string;
export type AuditRecordId = string;
export type EvidenceId = string;
export type EventCursor = string;

export type ProductRecoveryAction =
  | "edit_input"
  | "answer_ask"
  | "retry_command"
  | "retry_task"
  | "refresh_snapshot"
  | "wait_for_events"
  | "open_audit"
  | "open_settings"
  | "open_macos_privacy_accessibility"
  | "open_macos_privacy_automation"
  | "restart_helper"
  | "rerun_helper_preflight"
  | "export_diagnostics"
  | "none";

export type TaskRef = {
  kind: "draft" | "published";
  id: string;
};

export type ObjectRef = {
  kind:
    | "raw_task"
    | "raw_task_ask"
    | "plan"
    | "draft_task"
    | "draft_tree"
    | "draft_subtree"
    | "published_task"
    | "ask"
    | "message"
    | "command";
  id: string;
};

export type AffectedObjectImpact =
  | "changed"
  | "created"
  | "deleted"
  | "may_need_update"
  | "needs_review"
  | "invalidated"
  | "replaced"
  | "superseded";

export type AffectedObjectRef = {
  ref: ObjectRef;
  impact: AffectedObjectImpact;
  reason?: string | null;
};

export type AffectedScope = {
  kind:
    | "asks"
    | "session"
    | "task_tree"
    | "task_subtree"
    | "task_detail"
    | "messages"
    | "confirmations";
  taskRef?: TaskRef | null;
  reason?: string | null;
};

export type ApiError = {
  code:
    | "bad_request"
    | "not_found"
    | "version_conflict"
    | "command_rejected"
    | "permission_denied"
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
  objectRefs: ObjectRef[];
  affectedObjects: AffectedObjectRef[];
  emittedMessageIds: MessageId[];
  publishedTaskIds: string[];
  debugRefs: Record<string, string>;
};

export type RefreshHint = {
  waitForEvents: boolean;
  suggestedQueries: string[];
  affectedTaskRefs: TaskRef[];
  affectedScopes: AffectedScope[];
};

export type CommandResponse = {
  requestId: string;
  ok: boolean;
  result: CommandResult | null;
  error: ApiError | null;
  refresh: RefreshHint;
};
