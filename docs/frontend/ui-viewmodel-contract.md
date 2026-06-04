# UI ViewModel Contract

> Status: draft
> Last Updated: 2026-06-04
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
    | "draft_task"
    | "draft_tree"
    | "draft_subtree"
    | "published_task"
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
  status: "pending" | "answered" | "expired";
};
```

### 5.3 TaskTreeView

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

### 5.4 TaskNodeCardView

```ts
type TaskNodeCardView = {
  id: TaskNodeId;
  taskRef?: TaskRef | null;
  parentId: TaskNodeId | null;
  title: string;
  summary: string;
  depth: number;
  orderIndex: number;
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

### 5.5 ExecutionRollupView

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

### 5.6 TaskNodePermissions

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

### 5.7 SessionMessageView

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
};
```

Internal ids should not be primary message copy. They may appear in dev/debug affordances or Audit Page detail.

### 5.8 ConfirmationActionView

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

### 5.9 InputView

Input mode can be computed locally from snapshot plus selection, but it must be explicit before submitting a command.

```ts
type InputView = {
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
