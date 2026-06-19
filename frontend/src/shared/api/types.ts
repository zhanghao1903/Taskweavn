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

export type PlanningState =
  | "empty"
  | "capturing_input"
  | "assessing"
  | "awaiting_user"
  | "ready_to_plan"
  | "draft_ready"
  | "published"
  | "rejected"
  | "cancelled"
  | "unknown";

export type TaskNodeReadiness =
  | "draft"
  | "accepted"
  | "published"
  | "cancelled"
  | "unknown";

export type TaskTreeReadiness =
  | "empty"
  | "draft"
  | "accepted"
  | "published"
  | "mixed"
  | "cancelled"
  | "unknown";

export type ExecutionStatus =
  | "not_started"
  | "pending"
  | "running"
  | "waiting_for_user"
  | "done"
  | "failed"
  | "cancelled"
  | "unknown";

export type ConfirmationStatus = "pending" | "resolved" | "expired";

export type LocalConfirmationStatus =
  | "idle"
  | "resolving"
  | "resolve_failed";

export type AuditVerdict =
  | "not_available"
  | "passed"
  | "warning"
  | "failed"
  | "inconclusive";

export type StatusPresentation = {
  label: string;
  tone: "neutral" | "info" | "success" | "warning" | "danger";
  icon?: string;
};

export type ActionAvailability =
  | "enabled"
  | "disabled_permission"
  | "disabled_state"
  | "disabled_stale"
  | "pending_command"
  | "hidden"
  | "unknown";

export type ActionAvailabilityView = {
  actionId: string;
  label: string;
  availability: ActionAvailability;
  disabledReason?: string | null;
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
  workspaceId?: WorkspaceId;
  workspaceLabel?: string;
};

export type TaskTreeStatus =
  | "draft"
  | "published"
  | "running"
  | "completed"
  | "failed";

export type PlanUiStatus =
  | "draft"
  | "reviewing"
  | "ready_to_publish"
  | "published"
  | "running"
  | "finalizing"
  | "ready_for_review"
  | "accepted"
  | "follow_up_needed"
  | "failed"
  | "cancelled"
  | "unknown";

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
  planId?: PlanId | null;
  taskRef?: TaskRef;
  parentId: TaskNodeId | null;
  taskIndex?: string | null;
  title: string;
  summary: string;
  intent?: string | null;
  instructions?: string | null;
  acceptanceCriteria?: string[];
  status: TaskNodeStatus;
  readiness?: TaskNodeReadiness;
  execution?: ExecutionStatus;
  confirmation?: ConfirmationStatus | null;
  auditVerdict?: AuditVerdict;
  resultRef?: string | null;
  errorRef?: string | null;
  interruptionRequested?: boolean;
  depth: number;
  orderIndex: number;
  displayIndex: number;
  badges: TaskNodeBadges;
  permissions: TaskNodePermissions;
  readonlyReason?: string | null;
  availableActions?: ActionAvailabilityView[];
  version: number;
};

export type ExecutionRollupView = {
  total: number;
  notStarted: number;
  pending: number;
  running: number;
  done: number;
  failed: number;
  cancelled: number;
  unknown: number;
  blockedByConfirmation: number;
};

export type TaskTreeView = {
  id: TaskTreeId;
  sessionId: SessionId;
  title: string;
  summary?: string | null;
  status: TaskTreeStatus;
  readiness?: TaskTreeReadiness;
  executionRollup?: ExecutionRollupView;
  nodes: TaskNodeCardView[];
  version: number;
  generatedAt?: string;
};

export type PlanFinalizationView = {
  status:
    | "not_started"
    | "pending"
    | "running"
    | "skipped"
    | "done"
    | "failed";
  required: boolean;
  summaryRef?: string | null;
  fileRollupRef?: string | null;
  contextSummaryRef?: string | null;
  warnings: string[];
};

export type PlanOutcomeView = {
  status:
    | "succeeded"
    | "succeeded_with_warnings"
    | "partially_completed"
    | "failed"
    | "cancelled";
  summary: string;
  completedTaskCount: number;
  failedTaskCount: number;
  skippedTaskCount: number;
  resultRef?: string | null;
  fileChangeSummaryRef?: string | null;
  auditSummaryRef?: string | null;
};

export type PlanPermissions = {
  canEdit: boolean;
  canPublish: boolean;
  canAppendGuidance: boolean;
  canCreateTaskNode: boolean;
  canDeleteTaskNode: boolean;
  canRequestExecution: boolean;
  readonlyReason?: string | null;
};

export type PlanView = {
  id: PlanId;
  sessionId: SessionId;
  title: string;
  summary: string;
  objective: string;
  status: PlanUiStatus;
  taskCount: number;
  taskNodeIds: TaskNodeId[];
  taskNodes: TaskNodeCardView[];
  executionRollup: ExecutionRollupView;
  finalization: PlanFinalizationView;
  outcome: PlanOutcomeView | null;
  permissions: PlanPermissions;
  taskTreeProjection?: TaskTreeView | null;
  sourceKind:
    | "plan_store"
    | "legacy_draft_tree"
    | "legacy_published_task_tree"
    | "synthetic";
  sourceRef?: ObjectRef | null;
  version: number;
};

export type MessageKind = "informational" | "actionable" | "response" | "error";

export type ConversationRenderKind = "text" | "router_trace" | "question_card";

export type ConversationTextView = {
  title?: string | null;
  body: string;
};

export type ConversationRouterTraceView = {
  intent: RuntimeInputIntent;
  scopeKind: RuntimeInputScopeKind;
  confidence: RuntimeInputConfidence;
  sideEffect: SessionActivitySideEffect;
  dispatchTarget: RuntimeInputDispatchTarget;
  explanation: string;
  outcomeStatus: RuntimeInputOutcomeStatus;
};

export type ConversationQuestionInputView = {
  id: string;
  label: string;
  inputHint?: string | null;
  required: boolean;
};

export type ConversationQuestionOptionView = {
  id: string;
  label: string;
  description?: string | null;
};

export type ConversationQuestionCardView = {
  cardId: string;
  cardKind: "clarification" | "ask" | "confirmation";
  status: "pending" | "answered" | "cancelled" | "expired";
  title: string;
  body?: string | null;
  questions: ConversationQuestionInputView[];
  options: ConversationQuestionOptionView[];
  answerMode: "runtime_input" | "ask_command" | "confirmation_command";
  targetRef?: SessionActivityRefView | null;
};

export type ConversationRenderView = {
  protocolVersion: "plato.conversation.render.v1";
  renderKind: ConversationRenderKind;
  text?: ConversationTextView | null;
  routerTrace?: ConversationRouterTraceView | null;
  questionCard?: ConversationQuestionCardView | null;
};

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
  activityRelatedRefs?: SessionActivityRefView[];
  conversationRender?: ConversationRenderView | null;
};

export type SessionActivityItemKind =
  | "user_input"
  | "answer"
  | "guidance_recorded"
  | "plan_updated"
  | "task_created"
  | "task_changed"
  | "task_removed"
  | "ask_asked"
  | "ask_answered"
  | "confirmation_requested"
  | "confirmation_resolved"
  | "execution_update"
  | "result_ready"
  | "file_summary"
  | "recovery_note"
  | "router_interpretation";

export type SessionActivityScopeKind = "session" | "plan" | "task";

export type SessionActivitySideEffect =
  | "no_effect"
  | "context_effect"
  | "state_effect"
  | "authorization_effect"
  | "resume_effect"
  | "execution_request"
  | "evidence_effect";

export type SessionActivityRefKind =
  | "session"
  | "plan"
  | "task"
  | "ask"
  | "confirmation"
  | "message"
  | "result"
  | "file"
  | "audit"
  | "diagnostic";

export type SessionActivitySourceKind =
  | "message_stream"
  | "plan_projection"
  | "task_projection"
  | "ask_projection"
  | "confirmation_projection"
  | "result_projection"
  | "file_projection"
  | "router"
  | "system";

export type SessionActivityDisclosureLevel = "public" | "partial" | "hidden";

export type SessionActivityRefView = {
  kind: SessionActivityRefKind;
  id: string;
  label: string;
  href?: string | null;
  objectRef?: ObjectRef | null;
};

export type SessionActivityItemView = {
  id: string;
  sessionId: SessionId;
  kind: SessionActivityItemKind;
  title: string;
  body: string;
  occurredAt: string;
  scopeKind: SessionActivityScopeKind;
  planId?: PlanId | null;
  taskNodeId?: TaskNodeId | null;
  sideEffect: SessionActivitySideEffect;
  relatedRefs: SessionActivityRefView[];
  sourceKind: SessionActivitySourceKind;
  sourceId?: string | null;
  disclosureLevel: SessionActivityDisclosureLevel;
};

export type SessionActivityTimelineResult = {
  sessionId: SessionId;
  items: SessionActivityItemView[];
  nextCursor?: EventCursor | null;
  totalCount: number;
  generatedAt: string;
};

export type RuntimeInputMode = "auto" | "ask" | "guide" | "change";

export type RuntimeInputIntent =
  | "question"
  | "guidance"
  | "command"
  | "ask_answer"
  | "confirmation_response"
  | "execution_request"
  | "clarification"
  | "unsupported";

export type RuntimeInputConfidence = "high" | "medium" | "low";

export type RuntimeInputDispatchTarget =
  | "read_only_inquiry"
  | "record_guidance"
  | "resolve_ask"
  | "resolve_confirmation"
  | "existing_command"
  | "execution_handoff"
  | "clarification"
  | "unsupported";

export type RuntimeInputOutcomeStatus =
  | "dispatched"
  | "answered"
  | "needs_clarification"
  | "unsupported"
  | "rejected";

export type RuntimeInputScopeKind = "session" | "plan" | "task";

export type ReadOnlyInquiryScopeKind = RuntimeInputScopeKind;

export type ReadOnlyInquiryConfidence = RuntimeInputConfidence;

export type ReadOnlyInquiryStatus =
  | "answered"
  | "needs_clarification"
  | "unsupported"
  | "rejected";

export type ReadOnlyInquiryRefKind =
  | "task"
  | "plan"
  | "result"
  | "file"
  | "diff"
  | "audit_record"
  | "audit_evidence"
  | "diagnostic"
  | "activity";

export type ReadOnlyInquiryEvidenceKind =
  | "workspace_status"
  | "file_snapshot"
  | "diff_snapshot"
  | "result_summary"
  | "file_change_summary"
  | "audit_record"
  | "audit_evidence"
  | "diagnostic_summary"
  | "activity_item"
  | "session_status"
  | "task_status"
  | "plan_status";

export type ReadOnlyInquiryDisclosure = "public" | "partial" | "hidden";

export type ReadOnlyInquiryWarningCode =
  | "inquiry.context_empty"
  | "inquiry.context_partial"
  | "inquiry.context_truncated"
  | "inquiry.evidence_hidden"
  | "inquiry.provider_unavailable"
  | "inquiry.unsupported_question"
  | "inquiry.no_mutation_boundary";

export type ReadOnlyInquiryScope = {
  kind: ReadOnlyInquiryScopeKind;
  planId?: PlanId | null;
  taskNodeId?: TaskNodeId | null;
};

export type ReadOnlyInquiryRef = {
  kind: ReadOnlyInquiryRefKind;
  id?: string | null;
  path?: string | null;
  evidenceId?: EvidenceId | null;
  label: string;
};

export type ReadOnlyInquiryLimits = {
  maxEvidenceItems?: number | null;
  maxContextBytes?: number | null;
  maxAnswerChars?: number | null;
};

export type ReadOnlyInquiryRequest = {
  inquiryId: string;
  sessionId: SessionId;
  workspaceId?: WorkspaceId | null;
  question: string;
  scope: ReadOnlyInquiryScope;
  refs?: ReadOnlyInquiryRef[];
  limits?: ReadOnlyInquiryLimits;
};

export type ReadOnlyInquiryAnswer = {
  title?: string | null;
  body: string;
  confidence: ReadOnlyInquiryConfidence;
};

export type ReadOnlyInquiryEvidenceRef = {
  kind: ReadOnlyInquiryEvidenceKind;
  refId: string;
  parentRefId?: string | null;
  label: string;
  disclosure: ReadOnlyInquiryDisclosure;
  truncated: boolean;
};

export type ReadOnlyInquiryWarning = {
  code: ReadOnlyInquiryWarningCode;
  message: string;
  ref?: ReadOnlyInquiryRef | null;
};

export type ReadOnlyInquiryResult = {
  inquiryId: string;
  sessionId: SessionId;
  scope: ReadOnlyInquiryScope;
  status: ReadOnlyInquiryStatus;
  answer?: ReadOnlyInquiryAnswer | null;
  evidenceRefs: ReadOnlyInquiryEvidenceRef[];
  warnings: ReadOnlyInquiryWarning[];
  activity?: SessionActivityItemView | null;
  generatedAt: string;
};

export type RuntimeInputSelection = {
  scopeKind: RuntimeInputScopeKind;
  planId?: PlanId | null;
  taskNodeId?: TaskNodeId | null;
  refs?: ObjectRef[];
};

export type RuntimeInputClientState = {
  activeAskId?: AskId | null;
  activeConfirmationId?: ConfirmationId | null;
};

export type RuntimeInputRouteRequest = {
  commandId: CommandId;
  sessionId: SessionId;
  workspaceId?: WorkspaceId | null;
  content: string;
  mode?: RuntimeInputMode;
  selection: RuntimeInputSelection;
  inquiryRefs?: ReadOnlyInquiryRef[];
  clientState?: RuntimeInputClientState;
};

export type RuntimeInputDecisionScope = {
  kind: RuntimeInputScopeKind;
  planId?: PlanId | null;
  taskNodeId?: TaskNodeId | null;
};

export type RuntimeInputRouteDecision = {
  id: string;
  intent: RuntimeInputIntent;
  scope: RuntimeInputDecisionScope;
  confidence: RuntimeInputConfidence;
  sideEffect: SessionActivitySideEffect;
  dispatchTarget: RuntimeInputDispatchTarget;
  explanation: string;
  relatedRefs: SessionActivityRefView[];
};

export type RuntimeInputOutcome = {
  status: RuntimeInputOutcomeStatus;
  userMessage: string;
  recoveryActions: ProductRecoveryAction[];
};

export type RuntimeInputRouteResult = {
  sessionId: SessionId;
  decision: RuntimeInputRouteDecision;
  outcome: RuntimeInputOutcome;
  activity?: SessionActivityItemView | null;
  commandResponse?: CommandResponse | null;
  inquiryResult?: ReadOnlyInquiryResult | null;
  generatedAt: string;
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
  status: ConfirmationStatus;
  localStatus?: LocalConfirmationStatus;
  riskLabel?: string;
  createdAt: string;
  resolvedAt?: string | null;
};

export type ValidationSummaryView = {
  state: "not_started" | "running" | "passed" | "warning" | "failed";
  summary: string;
  issues: string[];
};

export type PlanningAskView = {
  id: string;
  question: string;
  reason: string;
  required: boolean;
  options: ConfirmationOptionView[];
  status: "pending" | "answered" | "expired" | "superseded";
};

export type PlanningDiagnosticView = {
  code: "dirty_authoring_state" | "authoring_state_cancelled";
  severity: "info" | "warning";
  message: string;
};

export type PlanningView = {
  state: PlanningState;
  sourceRawTaskId?: string | null;
  title?: string | null;
  summary?: string | null;
  asks: PlanningAskView[];
  diagnostics?: PlanningDiagnosticView[];
  validation: ValidationSummaryView | null;
};

export type AskAnswerType =
  | "free_text"
  | "single_choice"
  | "multi_choice"
  | "boolean";

export type AskRequestStatus =
  | "pending"
  | "answered"
  | "deferred"
  | "cancelled"
  | "expired";

export type AskOptionView = {
  id: string;
  label: string;
  description?: string | null;
};

export type AskQuestionView = {
  id: string;
  question: string;
  inputHint?: string | null;
  required: boolean;
};

export type AskRequestView = {
  id: AskId;
  sessionId: SessionId;
  taskNodeId?: TaskNodeId | null;
  taskRef?: TaskRef | null;
  question: string;
  reason: string;
  questions?: AskQuestionView[];
  suggestedOptions: AskOptionView[];
  answerType: AskAnswerType;
  allowFreeText: boolean;
  allowNoOptionWithText: boolean;
  blocking: boolean;
  attachmentsSupported: false;
  status: AskRequestStatus;
  answerId?: string | null;
  resumeHint?: string | null;
  createdAt: string;
  answeredAt?: string | null;
  deferredAt?: string | null;
  cancelledAt?: string | null;
  expiredAt?: string | null;
};

export type AskListResult = {
  sessionId: SessionId;
  asks: AskRequestView[];
  activeAsk: AskRequestView | null;
};

export type SessionPermissions = {
  canCreateTaskTree: boolean;
  canPublishTaskTree: boolean;
  canAppendGuidance: boolean;
  canOpenAudit: boolean;
  canOpenSettings: boolean;
  readonlyReason?: string | null;
};

export type InputView = {
  mode:
    | "create_session_goal"
    | "generate_task_tree"
    | "global_guidance"
    | "task_guidance"
    | "task_revision_request"
    | "clarification_answer"
    | "disabled_readonly";
  scope: "session" | "task" | "confirmation" | "planning_ask" | "none";
  targetTaskNodeId?: TaskNodeId | null;
  targetConfirmationId?: ConfirmationId | null;
  disabled: boolean;
  disabledReason?: string | null;
  placeholder: string;
};

export type MockScenarioManifest<TFixtureId extends string = string> = {
  id: string;
  page: "main" | "audit";
  title: string;
  route: string;
  fixtureId: TFixtureId;
  canonicalStates: {
    planning?: PlanningState;
    readiness?: TaskNodeReadiness | TaskTreeReadiness;
    execution?: ExecutionStatus;
    confirmation?: ConfirmationStatus | LocalConfirmationStatus;
    auditVerdict?: AuditVerdict;
    permission?: ActionAvailability;
    pageState?: string;
  };
  expectedVisibleComponents: string[];
  expectedPrimaryActions: string[];
  expectedDisabledActions: string[];
  expectedRecoveryBehavior?: string | null;
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

export type AuditFilterKind =
  | "all"
  | "confirmations"
  | "actions"
  | "risks"
  | "files"
  | "results"
  | "system"
  | "config"
  | "logs";

export type AuditScope =
  | { kind: "session"; sessionId: SessionId }
  | { kind: "workflow"; workflowId: WorkflowId; projectId?: ProjectId | null }
  | {
      kind: "task";
      sessionId: SessionId;
      taskNodeId: TaskNodeId;
      taskRef?: TaskRef | null;
    }
  | {
      kind: "action";
      sessionId: SessionId;
      actionId: string;
      taskNodeId?: TaskNodeId | null;
    }
  | {
      kind: "confirmation";
      sessionId: SessionId;
      confirmationId: ConfirmationId;
      taskNodeId?: TaskNodeId | null;
    }
  | {
      kind: "file";
      sessionId: SessionId;
      path: string;
      taskNodeId?: TaskNodeId | null;
    }
  | {
      kind: "result";
      sessionId: SessionId;
      resultId: ResultId;
      taskNodeId?: TaskNodeId | null;
    }
  | {
      kind: "config";
      sessionId?: SessionId | null;
      workflowId?: WorkflowId | null;
      configKey?: string | null;
    }
  | {
      kind: "log_evidence";
      sessionId: SessionId;
      evidenceId: EvidenceId;
      taskNodeId?: TaskNodeId | null;
    };

export type AuditEntryKind =
  | "from_session"
  | "from_task"
  | "from_confirmation"
  | "from_result"
  | "from_file_change";

export type AuditEntryContext = {
  kind: AuditEntryKind;
  sessionId: SessionId;
  taskNodeId?: TaskNodeId | null;
  taskRef?: TaskRef | null;
  confirmationId?: ConfirmationId | null;
  resultId?: ResultId | null;
  filePath?: string | null;
  sourceRoute: string;
  preferredFilter?: AuditFilterKind | null;
  preferredRecordId?: AuditRecordId | null;
};

export type MainPageReturnTarget = {
  routeName: "main.session" | "main.sessionFallback";
  sessionId: SessionId;
  projectId?: ProjectId | null;
  workflowId?: WorkflowId | null;
  taskNodeId?: TaskNodeId | null;
  focus: "session" | "task" | "confirmation" | "result" | "file_change";
  recordId?: AuditRecordId | null;
};

export type AuditPageRequestView = {
  filter: AuditFilterKind;
  recordId?: AuditRecordId | null;
  includeDetail: boolean;
  includeSanitizedPayload?: boolean;
  limit: number;
  cursor?: string | null;
};

export type AuditCompleteness =
  | "not_started"
  | "running"
  | "partial"
  | "complete"
  | "failed"
  | "hidden";

export type AuditOverview = {
  verdict: AuditVerdict;
  completeness: AuditCompleteness;
  summary: string;
  keyIssue: string | null;
  recordCounts: Record<AuditFilterKind, number>;
  importantRecordIds: AuditRecordId[];
  hiddenEvidenceCount: number;
  partialReason?: string | null;
  generatedBy: "audit_agent" | "projection" | "rules" | "mock";
  updatedAt: string;
};

export type AuditFilterView = {
  kind: AuditFilterKind;
  label: string;
  count: number;
  enabled: boolean;
  disabledReason?: string | null;
};

export type AuditPageState =
  | { kind: "loading"; message: string }
  | { kind: "ready" }
  | { kind: "empty"; reason: string }
  | { kind: "partial"; reason: string }
  | { kind: "hidden_evidence"; reason: string; hiddenCount: number }
  | { kind: "permission_denied"; reason: string }
  | { kind: "error"; code: string; message: string; retryable: boolean }
  | { kind: "stale"; reason: string };

export type AuditPermissions = {
  canViewAudit: boolean;
  canViewEvidence: boolean;
  canViewHiddenEvidenceReason: boolean;
  canOpenRelatedLogs: boolean;
  readonlyReason?: string | null;
};

export type AuditRecordKind =
  | "confirmation"
  | "action"
  | "observation"
  | "risk"
  | "file_change"
  | "result"
  | "message"
  | "config_change"
  | "audit_verdict"
  | "system"
  | "log_evidence";

export type AuditActorKind =
  | "user"
  | "agent"
  | "tool"
  | "system"
  | "audit_agent";

export type AuditSeverity = "info" | "success" | "warning" | "danger";

export type AuditConfidence = "high" | "medium" | "low" | "unknown";

export type EvidenceKind =
  | "message"
  | "event"
  | "action"
  | "observation"
  | "file_change"
  | "result"
  | "audit_observation"
  | "config_snapshot"
  | "log_excerpt";

export type EvidenceRef = {
  id: EvidenceId;
  kind: EvidenceKind;
  label: string;
  summary: string;
  available: boolean;
  hidden: boolean;
  redacted: boolean;
};

export type AuditRecordFlags = {
  partial: boolean;
  hidden: boolean;
  redacted: boolean;
  stale: boolean;
  userVisible: boolean;
};

export type AuditRecord = {
  id: AuditRecordId;
  scope: AuditScope;
  kind: AuditRecordKind;
  filterKind: AuditFilterKind;
  title: string;
  summary: string;
  actor: AuditActorKind;
  sourceLabel: string;
  occurredAt: string;
  severity: AuditSeverity;
  confidence: AuditConfidence;
  verdict?: AuditVerdict | null;
  completeness: AuditCompleteness;
  taskNodeId?: TaskNodeId | null;
  taskRef?: TaskRef | null;
  actionId?: string | null;
  confirmationId?: ConfirmationId | null;
  resultId?: ResultId | null;
  filePath?: string | null;
  configKey?: string | null;
  evidenceRefs: EvidenceRef[];
  relatedRecordIds: AuditRecordId[];
  flags: AuditRecordFlags;
};

export type AuditReference = {
  kind:
    | "task"
    | "message"
    | "confirmation"
    | "action"
    | "observation"
    | "file"
    | "result"
    | "config"
    | "log"
    | "external";
  label: string;
  href?: string | null;
  ref?: ObjectRef | null;
};

export type AuditDisclosure = {
  rawPayloadAvailable: boolean;
  rawPayloadShown: boolean;
  redactionReason?: string | null;
  hiddenReason?: string | null;
  partialReason?: string | null;
  permissionReason?: string | null;
};

export type SanitizedRawPayload = {
  format: "json" | "text";
  content: string;
  redactions: string[];
};

export type EvidenceSummary = EvidenceRef & {
  source:
    | "event_stream"
    | "message_stream"
    | "task_projection"
    | "audit_agent"
    | "config_store"
    | "log_archive"
    | "mock";
  occurredAt?: string | null;
};

export type EvidenceDetail = EvidenceSummary & {
  body: string;
  sanitizedPayload: SanitizedRawPayload | null;
  disclosure: AuditDisclosure;
};

export type RelatedLogsLink = {
  label: string;
  href: string;
  filters: {
    sessionId?: SessionId | null;
    workflowId?: WorkflowId | null;
    taskNodeId?: TaskNodeId | null;
    recordId?: AuditRecordId | null;
    category?: string | null;
  };
  enabled: boolean;
  disabledReason?: string | null;
};

export type AuditRecordDetail = AuditRecord & {
  body: string;
  whyItMatters: string;
  outcome: string | null;
  references: AuditReference[];
  evidence: EvidenceSummary[];
  disclosure: AuditDisclosure;
  relatedLogs: RelatedLogsLink[];
  rawPayload: SanitizedRawPayload | null;
};

export type EffectiveConfigSummary = {
  summary: string;
  profileLabel: string;
  effectiveAt: string;
  relevantRecordIds: AuditRecordId[];
  settingsHref?: string | null;
};

export type AuditSummaryView = {
  verdict: AuditVerdict;
  completeness: AuditCompleteness;
  summary: string;
  href: string;
  updatedAt: string;
};

export type AuditPageSnapshot = {
  schemaVersion: "plato.audit.v1";
  request: AuditPageRequestView;
  scope: AuditScope;
  entryContext: AuditEntryContext;
  returnTarget: MainPageReturnTarget;
  project: ProjectSummary | null;
  workflow: WorkflowSummary | null;
  session: SessionSummary;
  selectedTask: TaskNodeCardView | null;
  overview: AuditOverview;
  filters: AuditFilterView[];
  records: AuditRecord[];
  selectedRecord: AuditRecordDetail | null;
  effectiveConfig: EffectiveConfigSummary | null;
  relatedLogs: RelatedLogsLink[];
  permissions: AuditPermissions;
  pageState: AuditPageState;
  cursor: EventCursor | null;
  generatedAt: string;
};

export type MainPageSnapshot = {
  schemaVersion?: "plato.main.v1";
  project: ProjectSummary;
  workflows: WorkflowSummary[];
  workflow: WorkflowSummary;
  sessions: SessionSummary[];
  session: SessionSummary;
  planning?: PlanningView;
  activePlan?: PlanView | null;
  taskTree: TaskTreeView | null;
  messages: SessionMessageView[];
  pendingConfirmations: ConfirmationActionView[];
  pendingAsks?: AskRequestView[];
  activeAsk?: AskRequestView | null;
  result: ResultCardView | null;
  fileChangeSummary: FileChangeSummaryView | null;
  auditSummary?: AuditSummaryView | null;
  auditLinks: AuditLinkView[];
  permissions?: SessionPermissions;
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
  | "audit.records_changed"
  | "audit.record_updated"
  | "audit.evidence_hidden"
  | "audit.snapshot_stale"
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
