# UI ViewModel Contract

> Status: draft
> Last Updated: 2026-06-14
> Scope: Frontend-facing ViewModels for Plato Main Page and Audit Page.
> Related: `docs/engineering/audit-page-contract.md`, `docs/ux/screen-state-spec.md`, `docs/ux/ask-ui-spec.md`, `docs/ux/confirmation-ui-spec.md`, `docs/frontend/event-reducer-contract.md`, `docs/frontend/api-ui-mapping.md`, `docs/architecture/task-domain-ui-model-separation.md`, `docs/product/plato-ui-api-contract.md`

## 1. Purpose

This document defines the frontend ViewModel contract that sits between backend/domain facts and UI components.

The contract intentionally separates:

- backend facts;
- UI ViewModels returned by API/projection;
- frontend local UI state;
- presentation labels and visual styling.

The frontend must not consume raw `TaskDomain`, raw event rows, MessageStream storage rows, or SQLite/log payloads directly.

## 2. Canonical Status Model

Do not introduce a single `status` field that tries to represent planning, readiness, execution, confirmation, and audit at the same time.

```ts
type PlanningState =
  | "empty"
  | "capturing_input"
  | "assessing"
  | "awaiting_user"
  | "ready_to_plan"
  | "draft_ready"
  | "published"
  | "rejected"
  | "cancelled";

type TaskNodeReadiness =
  | "draft"
  | "accepted"
  | "published"
  | "cancelled"
  | "unknown";

type ExecutionStatus =
  | "not_started"
  | "pending"
  | "running"
  | "done"
  | "failed"
  | "cancelled"
  | "unknown";

type ConfirmationStatus =
  | "pending"
  | "resolved"
  | "expired";

type LocalConfirmationStatus =
  | "idle"
  | "resolving"
  | "resolve_failed";

type AuditVerdict =
  | "not_available"
  | "passed"
  | "warning"
  | "failed"
  | "inconclusive";
```

Presentation labels are mapped separately:

```ts
type StatusPresentation = {
  label: string;
  tone: "neutral" | "info" | "success" | "warning" | "danger";
  icon?: string;
};
```

## 3. Identity And References

```ts
type ProjectId = string;
type WorkflowId = string;
type SessionId = string;
type TaskNodeId = string;
type DraftTaskId = string;
type PublishedTaskId = string;
type ResultId = string;
type AuditRecordId = string;
type EvidenceId = string;
type EventCursor = string;

type TaskRef =
  | { kind: "draft"; id: DraftTaskId }
  | { kind: "published"; id: PublishedTaskId };

type ObjectRef = {
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

type RouteContext = {
  projectId?: ProjectId;
  workflowId?: WorkflowId;
  sessionId: SessionId;
  taskNodeId?: TaskNodeId;
  auditRecordId?: AuditRecordId;
};
```

`TaskNodeId` is a UI stable id inside the current session projection. `TaskRef` preserves backend lineage and should be used for API commands when available.

## 4. Route Model

```ts
type PlatoRoute =
  | {
      name: "main.session";
      path: "/projects/:projectId/workflows/:workflowId/sessions/:sessionId";
      params: { projectId: ProjectId; workflowId: WorkflowId; sessionId: SessionId };
      query?: { taskNodeId?: TaskNodeId; messageId?: string };
    }
  | {
      name: "main.sessionFallback";
      path: "/sessions/:sessionId";
      params: { sessionId: SessionId };
      query?: { taskNodeId?: TaskNodeId };
    }
  | {
      name: "audit.session";
      path: "/sessions/:sessionId/audit";
      params: { sessionId: SessionId };
      query?: { filter?: AuditFilterKind; recordId?: AuditRecordId };
    }
  | {
      name: "audit.task";
      path: "/sessions/:sessionId/tasks/:taskNodeId/audit";
      params: { sessionId: SessionId; taskNodeId: TaskNodeId };
      query?: { filter?: AuditFilterKind; recordId?: AuditRecordId };
    };
```

Routes must support returning from Audit Page to Main Page with the same `sessionId` and, when available, `taskNodeId`.

## 5. Main Page ViewModel

### 5.1 MainPageSnapshot

```ts
type MainPageSnapshot = {
  schemaVersion: "plato.main.v1";
  project: ProjectSummary;
  workflows: WorkflowSummary[];
  workflow: WorkflowSummary;
  sessions: SessionSummary[];
  session: SessionSummary;
  planning: PlanningView;
  activePlan: PlanView | null;
  // Deprecated compatibility field for legacy Main Page components.
  // During migration, this equals activePlan.taskTreeProjection when available.
  taskTree: TaskTreeView | null;
  messages: SessionMessageView[];
  pendingConfirmations: ConfirmationActionView[];
  result: ResultCardView | null;
  fileChangeSummary: FileChangeSummaryView | null;
  auditSummary: AuditSummaryView | null;
  auditLinks: AuditLinkView[];
  permissions: SessionPermissions;
  cursor: EventCursor | null;
  generatedAt: string;
};
```

The snapshot must not include frontend-only state:

- selected task;
- expanded task ids;
- input draft text;
- open drawer/modals;
- scroll position;
- hover/focus;
- optimistic command spinners.

The snapshot must expose only one active domain for Main Page interaction.

| Condition | Active domain | UI target |
|---|---|---|
| `taskTree === null` and planning has pending asks | Authoring | Conversation Authoring ASK card |
| `taskTree !== null` and no task is selected | Task plan | Whole plan |
| `taskTree !== null` and a task is selected | Task node | Selected TaskNode |

If backend stores contain both pending RawTask asks and a TaskTree, the gateway
must project stale authoring asks out of the active control surface. UI
components should not implement their own domain priority rules.

New Product 1.1 surfaces should treat `activePlan` as canonical. Existing
components can continue reading `taskTree` until the Main Page work area is
migrated to `PlanView`.

### 5.2 PlanningView

```ts
type PlanningView = {
  state: PlanningState;
  sourceRawTaskId?: string | null;
  title?: string | null;
  summary?: string | null;
  asks: PlanningAskView[];
  validation: ValidationSummaryView | null;
};

type PlanningAskView = {
  id: string;
  question: string;
  reason: string;
  required: boolean;
  options: ConfirmationOptionView[];
  status: "pending" | "answered" | "expired" | "superseded";
};
```

`superseded` asks are read-only Conversation history. They must not render
answer controls once `taskTree` exists, but they retain original questions,
options, and any durable answers.

### 5.3 PlanView

```ts
type PlanUiStatus =
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

type PlanView = {
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
```

`PlanView` is the canonical Product 1.1 Main Page work contract. During PTC-2
it may be synthetic and derived from the existing `TaskTreeView`; PTC-3 owns
full legacy projection and flattening.

### 5.4 TaskTreeView

```ts
type TaskTreeView = {
  id: string;
  sessionId: SessionId;
  title: string;
  readiness: "draft" | "accepted" | "published" | "mixed" | "cancelled";
  executionRollup: ExecutionRollupView;
  nodes: TaskNodeCardView[];
  version: number;
  generatedAt: string;
};
```

`TaskTreeView` is deprecated compatibility data. Do not add new Product 1.1
behavior that depends on it directly when `activePlan` is available.

### 5.5 TaskNodeCardView

```ts
type TaskNodeCardView = {
  id: TaskNodeId;
  planId?: PlanId | null;
  taskRef?: TaskRef | null;
  parentId: TaskNodeId | null;
  taskIndex?: string | null;
  title: string;
  // Card-safe short summary. Must not contain concatenated
  // "Summary:" / "Instructions:" / "Acceptance criteria:" marker text.
  summary: string;
  // Full Task intent for the Detail Panel. Cards should not render this field.
  intent?: string | null;
  // Execution guidance for the Detail Panel.
  instructions?: string | null;
  // Detail-only acceptance criteria.
  acceptanceCriteria: string[];
  depth: number;
  orderIndex: number;
  displayIndex: number;
  readiness: TaskNodeReadiness;
  execution: ExecutionStatus;
  confirmation: ConfirmationStatus | null;
  auditVerdict: AuditVerdict;
  resultRef?: string | null;
  errorRef?: string | null;
  badges: TaskNodeBadges;
  permissions: TaskNodePermissions;
  readonlyReason?: string | null;
  version: number;
};
```

`planId` and `taskIndex` are required for `activePlan.taskNodes`. They remain
optional on legacy `taskTree.nodes` until the Main Page fully migrates off the
TaskTree compatibility field.

`summary` 是列表卡片展示字段，必须保持短、可扫描。`intent`、
`instructions`、`acceptanceCriteria` 是 Detail Panel 的结构化内容，
用于展示完整任务说明。Gateway 必须把旧数据中拼接到 `intent` 的
`Summary:`、`Instructions:`、`Acceptance criteria:` 标记拆回结构化字段；
前端不应在卡片中显示这些 marker。

### 5.6 ExecutionRollupView

```ts
type ExecutionRollupView = {
  total: number;
  pending: number;
  running: number;
  done: number;
  failed: number;
  cancelled: number;
  blockedByConfirmation: number;
};
```

### 5.7 Plan Finalization, Outcome, And Permissions

```ts
type PlanFinalizationView = {
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

type PlanOutcomeView = {
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

type PlanPermissions = {
  canEdit: boolean;
  canPublish: boolean;
  canAppendGuidance: boolean;
  canCreateTaskNode: boolean;
  canDeleteTaskNode: boolean;
  canRequestExecution: boolean;
  readonlyReason?: string | null;
};
```

PTC-2 exposes these fields with conservative defaults. PTC-7 owns real Plan
finalization and outcome review behavior.

### 5.8 TaskNodePermissions

```ts
type TaskNodePermissions = {
  canEdit: boolean;
  canAppendGuidance: boolean;
  canResolveConfirmation: boolean;
  canPublish: boolean;
  canCancel: boolean;
  canRetry: boolean;
};
```

Permissions must come from projection or API mapping. The component should not infer permissions from status alone.

### 5.9 SessionMessageView

```ts
type SessionMessageView = {
  id: string;
  sessionId: SessionId;
  taskNodeId: TaskNodeId | null;
  taskRef?: TaskRef | null;
  kind: "informational" | "actionable" | "response" | "error";
  title: string;
  body: string;
  createdAt: string;
  relatedConfirmationId?: string | null;
  relatedCommandId?: string | null;
  conversationVisibility: "visible" | "activity_only";
  conversationRender?: ConversationRenderView | null;
};

type ConversationRenderView = {
  protocolVersion: "plato.conversation.render.v1";
  renderKind: "text" | "router_trace" | "question_card" | "ask_card";
  askCard?: ConversationAskCardView | null;
  // existing text/routerTrace/questionCard fields remain additive.
};

type ConversationAskCardView = {
  cardId: string;
  domain: "authoring" | "execution";
  status:
    | "pending"
    | "answered"
    | "deferred"
    | "cancelled"
    | "expired"
    | "superseded";
  title: string;
  body?: string | null;
  rawTaskId?: string | null;
  askId?: string | null;
  taskNodeId?: TaskNodeId | null;
  questions: ConversationAskQuestionView[];
  createdAt: string;
  resolvedAt?: string | null;
  canAnswer: boolean;
  canDefer: boolean;
  canCancel: boolean;
  readonlyReason?: string | null;
};

type ConversationAskQuestionView = {
  id: string;
  prompt: string;
  reason?: string | null;
  required: boolean;
  answered: boolean;
  answerType: "free_text" | "single_choice" | "multi_choice" | "boolean";
  allowFreeText: boolean;
  options: Array<{
    id: string;
    value: string;
    label: string;
    description?: string | null;
    selected: boolean;
  }>;
  answerText?: string | null;
};
```

Internal ids should not be primary message copy. They may appear in dev/debug affordances or Audit Page detail.

`activity_only` messages still participate in Activity/Audit projection but
must not render in the main Conversation. ASK-specific user-answer messages use
this visibility; ordinary Read-only Inquiry answers remain `visible`.

Conversation ASK card identity and ordering remain stable across pending and
terminal states. Frontend components must not infer selected options from
message title/body. In a partially answered Authoring group, `answered=true`
questions are authoritative and read-only; batch submission includes only
questions where `answered=false`.

### 5.10 SessionActivityTimelineResult

```ts
type SessionActivityTimelineResult = {
  sessionId: SessionId;
  items: SessionActivityItemView[];
  nextCursor?: EventCursor | null;
  totalCount: number;
  generatedAt: string;
};

type SessionActivityItemView = {
  id: string;
  sessionId: SessionId;
  kind:
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
  title: string;
  body: string;
  occurredAt: string;
  scopeKind: "session" | "plan" | "task";
  planId?: string | null;
  taskNodeId?: TaskNodeId | null;
  sideEffect:
    | "no_effect"
    | "context_effect"
    | "state_effect"
    | "authorization_effect"
    | "resume_effect"
    | "execution_request"
    | "evidence_effect";
  relatedRefs: SessionActivityRefView[];
  sourceKind:
    | "message_stream"
    | "plan_projection"
    | "task_projection"
    | "ask_projection"
    | "confirmation_projection"
    | "result_projection"
    | "file_projection"
    | "router"
    | "system";
  sourceId?: string | null;
  disclosureLevel: "public" | "partial" | "hidden";
};

type SessionActivityRefView = {
  kind:
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
  id: string;
  label: string;
  href?: string | null;
  objectRef?: ObjectRef | null;
};
```

Activity is a readonly projection for user-visible session conversation and work events. Frontend components must treat it as a display/query surface, not as command state. It must not surface raw prompts, provider payloads, tool arguments, SQLite rows, secrets, or raw absolute workspace paths.

### 5.11 ConfirmationActionView

```ts
type ConfirmationActionView = {
  id: string;
  sessionId: SessionId;
  taskNodeId: TaskNodeId;
  taskRef?: TaskRef | null;
  title: string;
  body: string;
  options: ConfirmationOptionView[];
  defaultOptionValue?: string | null;
  status: ConfirmationStatus;
  localStatus?: LocalConfirmationStatus;
  riskLabel?: string | null;
  createdAt: string;
  resolvedAt?: string | null;
};
```

`localStatus` is optional and must never be persisted as backend truth.

### 5.12 InputView

Input mode can be computed locally from snapshot plus selection, but it must be explicit before submitting a command.

```ts
type InputView = {
  mode:
    | "create_session_goal"
    | "generate_task_tree"
    | "plan_guidance"
    | "global_guidance"
    | "task_guidance"
    | "task_revision_request"
    | "clarification_answer"
    | "disabled_readonly";
  scope: "session" | "plan" | "task" | "confirmation" | "planning_ask" | "none";
  targetTaskNodeId?: TaskNodeId | null;
  targetConfirmationId?: string | null;
  disabled: boolean;
  disabledReason?: string | null;
  placeholder: string;
};
```

## 6. Audit Page ViewModel

Backend additive models for this section now exist in
`taskweavn.server.ui_contract`. The canonical engineering source for Audit
Page transport shape is `docs/engineering/audit-page-contract.md`; this section
summarizes the frontend-facing shape that should be mirrored in TypeScript
before UI implementation.

### 6.1 AuditPageSnapshot

```ts
type AuditFilterKind =
  | "all"
  | "confirmations"
  | "actions"
  | "risks"
  | "files"
  | "results"
  | "system"
  | "config"
  | "logs";

type AuditPageRequestView = {
  filter: AuditFilterKind;
  recordId?: AuditRecordId | null;
  includeDetail: boolean;
  limit: number;
  cursor?: string | null;
};

type AuditEntryContext = {
  source:
    | "from_session"
    | "from_task"
    | "from_confirmation"
    | "from_result"
    | "from_file_change";
  sessionId: SessionId;
  taskNodeId?: TaskNodeId | null;
  confirmationId?: string | null;
  resultId?: ResultId | null;
  filePath?: string | null;
};

type MainPageReturnTarget = {
  sessionId: SessionId;
  focus:
    | "session"
    | "task"
    | "confirmation"
    | "result"
    | "file_change";
  taskNodeId?: TaskNodeId | null;
  confirmationId?: string | null;
  resultId?: ResultId | null;
  filePath?: string | null;
};

type AuditPageState =
  | { kind: "loading"; message: string }
  | { kind: "ready" }
  | { kind: "empty"; reason: string }
  | { kind: "partial"; reason: string }
  | { kind: "hidden_evidence"; reason: string; hiddenCount: number }
  | { kind: "permission_denied"; reason: string }
  | { kind: "error"; code: string; message: string; retryable: boolean }
  | { kind: "stale"; reason: string };

type AuditPermissions = {
  canViewAudit: boolean;
  canViewEvidence: boolean;
  canViewHiddenEvidenceReason: boolean;
  canOpenRelatedLogs: boolean;
  readonlyReason?: string | null;
};

type AuditPageSnapshot = {
  schemaVersion: "plato.audit.v1";
  request: AuditPageRequestView;
  scope: AuditScopeView;
  entryContext: AuditEntryContext;
  returnTarget: MainPageReturnTarget;
  project: ProjectSummary | null;
  workflow: WorkflowSummary | null;
  session: SessionSummary;
  selectedTask: TaskNodeCardView | null;
  overview: AuditOverviewView;
  filters: AuditFilterView[];
  records: AuditRecordView[];
  selectedRecord: AuditRecordDetailView | null;
  effectiveConfig: EffectiveConfigSummaryView | null;
  relatedLogs: RelatedLogsLinkView[];
  permissions: AuditPermissions;
  pageState: AuditPageState;
  cursor: EventCursor | null;
  generatedAt: string;
};
```

### 6.2 AuditScopeView

```ts
type AuditScopeView =
  | { kind: "session"; sessionId: SessionId }
  | { kind: "workflow"; workflowId: WorkflowId; projectId?: ProjectId | null }
  | { kind: "task"; sessionId: SessionId; taskNodeId: TaskNodeId; taskRef?: TaskRef | null }
  | { kind: "action"; sessionId: SessionId; actionId: string; taskNodeId?: TaskNodeId | null }
  | { kind: "confirmation"; sessionId: SessionId; confirmationId: string; taskNodeId?: TaskNodeId | null }
  | { kind: "file"; sessionId: SessionId; path: string; taskNodeId?: TaskNodeId | null }
  | { kind: "result"; sessionId: SessionId; resultId: ResultId; taskNodeId?: TaskNodeId | null }
  | { kind: "config"; sessionId?: SessionId | null; workflowId?: WorkflowId | null; configKey?: string | null }
  | { kind: "log_evidence"; sessionId: SessionId; evidenceId: string; taskNodeId?: TaskNodeId | null };
```

### 6.3 AuditOverviewView

```ts
type AuditOverviewView = {
  verdict: AuditVerdict;
  completeness: "not_started" | "running" | "partial" | "complete" | "failed" | "hidden";
  summary: string;
  keyIssue: string | null;
  recordCounts: Record<AuditFilterKind, number>;
  importantRecordIds: AuditRecordId[];
  hiddenEvidenceCount: number;
  partialReason?: string | null;
  generatedBy: "audit_agent" | "projection" | "rules" | "mock";
  updatedAt: string;
};
```

### 6.4 Audit Record Types

```ts
type AuditRecordKind =
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

type AuditRecordView = {
  id: AuditRecordId;
  scope: AuditScopeView;
  kind: AuditRecordKind;
  filterKind: AuditFilterKind;
  title: string;
  summary: string;
  actor: "user" | "agent" | "tool" | "system" | "audit_agent";
  sourceLabel: string;
  confidence: "high" | "medium" | "low" | "unknown";
  severity: "info" | "success" | "warning" | "danger";
  verdict?: AuditVerdict | null;
  completeness: "not_started" | "running" | "partial" | "complete" | "failed" | "hidden";
  occurredAt: string;
  taskNodeId?: TaskNodeId | null;
  taskRef?: TaskRef | null;
  actionId?: string | null;
  confirmationId?: string | null;
  resultId?: ResultId | null;
  filePath?: string | null;
  configKey?: string | null;
  evidenceRefs: EvidenceRefView[];
  relatedRecordIds: AuditRecordId[];
  flags: {
    partial: boolean;
    hidden: boolean;
    redacted: boolean;
    stale: boolean;
    userVisible: boolean;
  };
};
```

### 6.5 AuditRecordDetailView

```ts
type AuditRecordDetailView = AuditRecordView & {
  body: string;
  whyItMatters: string;
  outcome: string | null;
  references: AuditReferenceView[];
  evidence: EvidenceSummaryView[];
  disclosure: {
    rawPayloadAvailable: boolean;
    rawPayloadShown: boolean;
    redactionReason?: string | null;
    hiddenReason?: string | null;
    partialReason?: string | null;
    permissionReason?: string | null;
  };
  relatedLogs: RelatedLogsLinkView[];
  rawPayload: SanitizedRawPayloadView | null;
};

type AuditReferenceView = {
  label: string;
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
  href?: string | null;
  ref?: ObjectRef | null;
};

type EvidenceRefView = {
  id: EvidenceId;
  kind:
    | "message"
    | "event"
    | "action"
    | "observation"
    | "file_change"
    | "result"
    | "audit_observation"
    | "config_snapshot"
    | "log_excerpt";
  label: string;
  summary: string;
  available: boolean;
  hidden: boolean;
  redacted: boolean;
};

type EvidenceSummaryView = EvidenceRefView & {
  source:
    | "event_stream"
    | "message_stream"
    | "task_projection"
    | "workspace_inspection"
    | "audit_agent"
    | "config_store"
    | "log_archive"
    | "mock";
  occurredAt?: string | null;
};

type SanitizedRawPayloadView = {
  format: "json" | "text";
  content: string;
  redactions: string[];
};
```

Audit detail may link to logs, but it must not embed full raw logs by default.

### 6.6 Effective Config And Logs

```ts
type EffectiveConfigSummaryView = {
  summary: string;
  profileLabel: string;
  effectiveAt: string;
  relevantRecordIds: AuditRecordId[];
  settingsHref?: string | null;
};

type RelatedLogsLinkView = {
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
```

## 7. Frontend Local State

```ts
type MainPageLocalState = {
  selectedTarget: "auto" | "plan" | "task";
  selectedTaskNodeId: TaskNodeId | null;
  expandedTaskNodeIds: TaskNodeId[];
  inputDraft: string;
  inputView: InputView;
  pendingCommandIds: string[];
  sync: SyncState;
};

type SyncState =
  | { kind: "fresh" }
  | { kind: "connecting" }
  | { kind: "stale"; reason: string }
  | { kind: "resyncing"; reason: string }
  | { kind: "offline"; reason: string };
```

Local state must not be sent back to the backend except through explicit commands.

When `selectedTarget` is `"plan"`, the Main Page treats the whole TaskTree as
the active interaction object even if runtime metadata contains an initial
TaskNode focus. This selection is local UI state only and must not be persisted
in the backend snapshot.

## 8. Acceptance Criteria

- Main Page and Audit Page ViewModels carry separate fields for planning, readiness, execution, confirmation, and audit verdict.
- UI labels are mapped from canonical fields and are not stored as canonical status.
- Audit Page ViewModel covers session, workflow, task, action, confirmation,
  file, result, config, and log/evidence scopes. The first route shell may ship
  session/task entries first, but components must not collapse the wider scope
  model.
- Audit Page ViewModel supports filters, selected record detail, effective config summary, and related logs links.
- Main Page ViewModel supports explicit input modes.
- Local frontend state is clearly separated from API snapshot state.
- The contract can be served by mock fixtures first and real API later without component shape changes.
