import {
  buildAuditTaskRoute,
  buildDiagnosticsLogsRoute,
  buildMainSessionFallbackRoute,
} from "../../app/routes";
import type {
  ApiError,
  AuditCompleteness,
  AuditFilterKind,
  AuditPageSnapshot,
  AuditPageState,
  AuditRecord,
  AuditRecordDetail,
  AuditRecordId,
  AuditRecordKind,
  AuditSeverity,
  AuditVerdict,
  EvidenceDetail,
  MockScenarioManifest,
  QueryResponse,
} from "../../shared/api/types";

export type AuditMockScenarioId =
  | "a1-audit-empty"
  | "a2-audit-loading"
  | "a3-records-ready"
  | "a4-record-selected"
  | "a5-partial-evidence"
  | "a6-hidden-evidence"
  | "a7-warning-verdict"
  | "a8-failed-verdict"
  | "a9-inconclusive-verdict"
  | "a10-not-available"
  | "a11-permission-denied"
  | "a12-stale-snapshot"
  | "a13-query-error"
  | "a14-evidence-load-error";

export type AuditMockScenario = MockScenarioManifest<AuditMockScenarioId>;

type AuditScenarioDefinition = {
  id: AuditMockScenarioId;
  title: string;
  route: string;
  filter: AuditFilterKind;
  verdict: AuditVerdict;
  completeness: AuditCompleteness;
  pageState: AuditPageState;
  records: AuditRecord[];
  selectedRecordId?: AuditRecordId | null;
  canViewAudit?: boolean;
  canViewEvidence?: boolean;
  hiddenEvidenceCount?: number;
  expectedVisibleComponents: string[];
  expectedPrimaryActions: string[];
  expectedDisabledActions: string[];
  expectedRecoveryBehavior?: string | null;
};

const sessionId = "session-website-plan";
const taskNodeId = "task-implementation";

const definitions: readonly AuditScenarioDefinition[] = [
  scenario({
    id: "a1-audit-empty",
    title: "Audit empty",
    filter: "all",
    verdict: "not_available",
    completeness: "not_started",
    pageState: { kind: "empty", reason: "No audit records exist for this scope." },
    records: [],
    visible: ["EmptyState", "Audit filters", "Return action"],
    primary: ["Return to Main"],
    disabled: ["Open evidence"],
  }),
  scenario({
    id: "a2-audit-loading",
    title: "Audit loading",
    filter: "all",
    verdict: "not_available",
    completeness: "running",
    pageState: { kind: "loading", message: "Loading audit records." },
    records: [],
    visible: ["Skeleton", "Audit filters", "Audit detail placeholder"],
    primary: [],
    disabled: ["Open evidence", "Open related logs"],
  }),
  scenario({
    id: "a3-records-ready",
    title: "Audit records ready",
    filter: "all",
    verdict: "passed",
    completeness: "complete",
    pageState: { kind: "ready" },
    records: [
      record("record-action-1", "action", "actions", "Action completed", "success", "passed"),
      record(
        "record-confirmation-1",
        "confirmation",
        "confirmations",
        "User approved limited edits",
        "success",
        "passed",
      ),
    ],
    visible: ["AuditEntryCard list", "Audit overview", "Filters"],
    primary: ["Select record"],
    disabled: [],
  }),
  scenario({
    id: "a4-record-selected",
    title: "Audit record selected",
    filter: "all",
    verdict: "passed",
    completeness: "complete",
    pageState: { kind: "ready" },
    records: [
      record("record-file-1", "file_change", "files", "File change linked", "success", "passed"),
    ],
    selectedRecordId: "record-file-1",
    visible: ["Selected AuditEntryCard", "Audit detail", "Evidence summary"],
    primary: ["Return to Main"],
    disabled: [],
  }),
  scenario({
    id: "a5-partial-evidence",
    title: "Partial evidence",
    filter: "all",
    verdict: "inconclusive",
    completeness: "partial",
    pageState: { kind: "partial", reason: "Some evidence is still loading." },
    records: [
      record("record-partial-1", "observation", "system", "Evidence still partial", "warning", "inconclusive", {
        partial: true,
      }),
    ],
    selectedRecordId: "record-partial-1",
    visible: ["Partial evidence banner", "Available evidence", "Missing evidence note"],
    primary: ["Refresh evidence"],
    disabled: ["Treat as passed"],
    recovery: "Refresh snapshot or return to Main while audit continues.",
  }),
  scenario({
    id: "a6-hidden-evidence",
    title: "Hidden evidence / permission limited",
    filter: "all",
    verdict: "warning",
    completeness: "hidden",
    hiddenEvidenceCount: 2,
    pageState: {
      hiddenCount: 2,
      kind: "hidden_evidence",
      reason: "Some evidence exists but is permission-limited.",
    },
    records: [
      record("record-hidden-1", "log_evidence", "logs", "Evidence hidden by policy", "warning", "warning", {
        hidden: true,
      }),
    ],
    selectedRecordId: "record-hidden-1",
    visible: ["Hidden evidence block", "Permission reason", "Audit detail"],
    primary: ["Return to Main"],
    disabled: ["Open raw payload"],
  }),
  scenario({
    id: "a7-warning-verdict",
    title: "Warning verdict",
    filter: "risks",
    verdict: "warning",
    completeness: "complete",
    pageState: { kind: "ready" },
    records: [
      record("record-warning-1", "risk", "risks", "Validation gap remains", "warning", "warning"),
    ],
    selectedRecordId: "record-warning-1",
    visible: ["Warning verdict", "Risk record", "Evidence summary"],
    primary: ["Review evidence"],
    disabled: [],
  }),
  scenario({
    id: "a8-failed-verdict",
    title: "Failed verdict",
    filter: "risks",
    verdict: "failed",
    completeness: "failed",
    pageState: { kind: "ready" },
    records: [
      record("record-failed-1", "audit_verdict", "risks", "Audit failed", "danger", "failed"),
    ],
    selectedRecordId: "record-failed-1",
    visible: ["Failed verdict", "Blocking evidence", "Return action"],
    primary: ["Return to Main"],
    disabled: ["Accept result"],
  }),
  scenario({
    id: "a9-inconclusive-verdict",
    title: "Inconclusive verdict",
    filter: "all",
    verdict: "inconclusive",
    completeness: "partial",
    pageState: { kind: "partial", reason: "Audit cannot establish confidence." },
    records: [
      record("record-inconclusive-1", "audit_verdict", "system", "Audit inconclusive", "warning", "inconclusive", {
        partial: true,
      }),
    ],
    selectedRecordId: "record-inconclusive-1",
    visible: ["Inconclusive verdict", "Missing evidence reason"],
    primary: ["Refresh audit"],
    disabled: ["Treat as passed"],
  }),
  scenario({
    id: "a10-not-available",
    title: "Not available verdict",
    filter: "all",
    verdict: "not_available",
    completeness: "not_started",
    pageState: { kind: "empty", reason: "Audit is not available for this draft task." },
    records: [],
    visible: ["Not available verdict", "EmptyState"],
    primary: ["Return to Main"],
    disabled: ["Open evidence"],
  }),
  scenario({
    id: "a11-permission-denied",
    title: "Audit permission denied",
    filter: "all",
    verdict: "not_available",
    completeness: "hidden",
    pageState: { kind: "permission_denied", reason: "User cannot view this audit scope." },
    records: [],
    canViewAudit: false,
    canViewEvidence: false,
    visible: ["ErrorState", "Return action"],
    primary: ["Return to Main"],
    disabled: ["Open evidence", "Open related logs"],
    recovery: "Return to originating Main Page context.",
  }),
  scenario({
    id: "a12-stale-snapshot",
    title: "Stale snapshot / records changed",
    filter: "all",
    verdict: "warning",
    completeness: "partial",
    pageState: { kind: "stale", reason: "Audit records changed after this snapshot." },
    records: [
      record("record-stale-1", "system", "system", "Audit snapshot stale", "warning", "warning", {
        stale: true,
      }),
    ],
    visible: ["Stale banner", "Record list", "Refresh action"],
    primary: ["Refresh audit"],
    disabled: ["Open evidence"],
    recovery: "Refetch AuditPageSnapshot before trusting evidence.",
  }),
  scenario({
    id: "a13-query-error",
    title: "Audit query error",
    filter: "all",
    verdict: "not_available",
    completeness: "failed",
    pageState: {
      code: "internal_error",
      kind: "error",
      message: "Audit query failed.",
      retryable: true,
    },
    records: [],
    visible: ["ErrorState", "Retry action", "Return action"],
    primary: ["Retry"],
    disabled: ["Open evidence"],
    recovery: "Retry query or return to Main.",
  }),
  scenario({
    id: "a14-evidence-load-error",
    title: "Evidence load error",
    filter: "files",
    verdict: "warning",
    completeness: "partial",
    pageState: { kind: "ready" },
    records: [
      record("record-evidence-error-1", "file_change", "files", "Evidence detail failed", "warning", "warning", {
        partial: true,
      }),
    ],
    selectedRecordId: "record-evidence-error-1",
    visible: ["Record list", "Evidence ErrorState", "Retry evidence action"],
    primary: ["Retry evidence"],
    disabled: ["Open raw payload"],
    recovery: "Keep record list visible and retry evidence detail only.",
  }),
];

export const auditMockScenarios: readonly AuditMockScenario[] = definitions.map(
  (definition) => ({
    canonicalStates: {
      auditVerdict: definition.verdict,
      pageState: definition.pageState.kind,
      permission: definition.canViewAudit === false ? "disabled_permission" : "enabled",
    },
    expectedDisabledActions: definition.expectedDisabledActions,
    expectedPrimaryActions: definition.expectedPrimaryActions,
    expectedRecoveryBehavior: definition.expectedRecoveryBehavior ?? null,
    expectedVisibleComponents: definition.expectedVisibleComponents,
    fixtureId: definition.id,
    id: definition.id,
    page: "audit",
    route: definition.route,
    title: definition.title,
  }),
);

export function listAuditMockScenarios(): readonly AuditMockScenario[] {
  return auditMockScenarios;
}

export function getAuditMockScenario(
  scenarioId: string,
): AuditMockScenario {
  return (
    auditMockScenarios.find((scenario) => scenario.id === scenarioId) ??
    auditMockScenarios[0]
  );
}

export function getAuditMockSnapshot(
  scenarioId: string,
): AuditPageSnapshot {
  const definition = getDefinition(scenarioId);
  const selectedRecord =
    definition.selectedRecordId === undefined || definition.selectedRecordId === null
      ? null
      : definition.records.find((item) => item.id === definition.selectedRecordId) ??
        null;

  return {
    cursor: `cursor-${definition.id}`,
    effectiveConfig: {
      effectiveAt: "2026-05-24T10:00:00Z",
      profileLabel: "Balanced autonomy",
      relevantRecordIds: definition.records.map((item) => item.id),
      settingsHref: "/settings",
      summary: "User-readable audit profile is active.",
    },
    entryContext: {
      kind: "from_task",
      preferredFilter: definition.filter,
      preferredRecordId: definition.selectedRecordId ?? null,
      sessionId,
      sourceRoute: buildMainSessionFallbackRoute({ sessionId, taskNodeId }),
      taskNodeId,
    },
    filters: filterViews(definition.records),
    generatedAt: "2026-05-24T10:02:00Z",
    overview: {
      completeness: definition.completeness,
      generatedBy: "mock",
      hiddenEvidenceCount: definition.hiddenEvidenceCount ?? 0,
      importantRecordIds: definition.records.slice(0, 2).map((item) => item.id),
      keyIssue: selectedRecord?.summary ?? null,
      partialReason:
        definition.completeness === "partial"
          ? "Some audit evidence is incomplete."
          : null,
      recordCounts: recordCounts(definition.records),
      summary: definition.title,
      updatedAt: "2026-05-24T10:02:00Z",
      verdict: definition.verdict,
    },
    pageState: definition.pageState,
    permissions: {
      canOpenRelatedLogs: definition.canViewAudit !== false,
      canViewAudit: definition.canViewAudit ?? true,
      canViewEvidence: definition.canViewEvidence ?? true,
      canViewHiddenEvidenceReason: definition.hiddenEvidenceCount !== undefined,
      readonlyReason:
        definition.canViewAudit === false ? "Audit permission denied." : null,
    },
    project: {
      id: "project-personal-site",
      name: "Personal Website",
    },
    records: definition.records,
    relatedLogs: [
      {
        enabled: definition.canViewAudit !== false,
        filters: {
          category: "audit",
          recordId: definition.selectedRecordId ?? null,
          sessionId,
          taskNodeId,
        },
        href: buildDiagnosticsLogsRoute({
          category: "audit",
          recordId: definition.selectedRecordId ?? undefined,
          sessionId,
          taskNodeId,
        }),
        label: "View related logs",
      },
    ],
    request: {
      filter: definition.filter,
      includeDetail: definition.selectedRecordId !== undefined,
      limit: 50,
      recordId: definition.selectedRecordId ?? null,
    },
    returnTarget: {
      focus: "task",
      projectId: "project-personal-site",
      routeName: "main.sessionFallback",
      sessionId,
      taskNodeId,
      workflowId: "workflow-planning-execution",
    },
    schemaVersion: "plato.audit.v1",
    scope: {
      kind: "task",
      sessionId,
      taskNodeId,
    },
    selectedRecord: selectedRecord === null ? null : recordDetail(selectedRecord),
    selectedTask: null,
    session: {
      createdAt: "2026-05-24T10:00:00Z",
      id: sessionId,
      name: "Personal website plan",
      projectId: "project-personal-site",
      status: "completed",
      updatedAt: "2026-05-24T10:02:00Z",
      workflowId: "workflow-planning-execution",
    },
    workflow: {
      description: "Turn a natural language goal into a visible task plan.",
      id: "workflow-planning-execution",
      name: "Task Planning & Execution",
    },
  };
}

export function getAuditMockSnapshotResponse(
  scenarioId: string,
): QueryResponse<AuditPageSnapshot> {
  const snapshot = getAuditMockSnapshot(scenarioId);

  return {
    cursor: snapshot.cursor,
    data: snapshot,
    error: null,
    generatedAt: snapshot.generatedAt,
    ok: true,
    requestId: `request-${scenarioId}`,
  };
}

export function getAuditMockEvidenceDetailResponse(
  scenarioId: string,
  evidenceId: string,
): QueryResponse<EvidenceDetail> {
  if (scenarioId === "a14-evidence-load-error") {
    return errorResponse("evidence_load_failed", "Evidence detail failed.");
  }

  return {
    data: {
      available: true,
      body: "Evidence detail is summarized and sanitized for user-readable audit.",
      disclosure: {
        rawPayloadAvailable: false,
        rawPayloadShown: false,
      },
      hidden: false,
      id: evidenceId,
      kind: "observation",
      label: "Evidence detail",
      occurredAt: "2026-05-24T10:01:00Z",
      redacted: false,
      sanitizedPayload: null,
      source: "mock",
      summary: "Mock evidence detail.",
    },
    error: null,
    generatedAt: "2026-05-24T10:02:00Z",
    ok: true,
    requestId: `request-evidence-${evidenceId}`,
  };
}

function scenario({
  canViewAudit,
  canViewEvidence,
  completeness,
  disabled,
  filter,
  hiddenEvidenceCount,
  id,
  pageState,
  primary,
  records,
  recovery = null,
  selectedRecordId = null,
  title,
  verdict,
  visible,
}: Omit<AuditScenarioDefinition, "route" | "expectedVisibleComponents" | "expectedPrimaryActions" | "expectedDisabledActions" | "expectedRecoveryBehavior"> & {
  disabled: string[];
  primary: string[];
  recovery?: string | null;
  visible: string[];
}): AuditScenarioDefinition {
  return {
    canViewAudit,
    canViewEvidence,
    completeness,
    expectedDisabledActions: disabled,
    expectedPrimaryActions: primary,
    expectedRecoveryBehavior: recovery,
    expectedVisibleComponents: visible,
    filter,
    hiddenEvidenceCount,
    id,
    pageState,
    records,
    route:
      filter === "all"
        ? buildAuditTaskRoute(sessionId, taskNodeId)
        : buildAuditTaskRoute(sessionId, taskNodeId, { filter }),
    selectedRecordId,
    title,
    verdict,
  };
}

function getDefinition(scenarioId: string): AuditScenarioDefinition {
  return definitions.find((definition) => definition.id === scenarioId) ??
    definitions[0];
}

function record(
  id: AuditRecordId,
  kind: AuditRecordKind,
  filterKind: AuditFilterKind,
  title: string,
  severity: AuditSeverity,
  verdict: AuditVerdict,
  flags: Partial<AuditRecord["flags"]> = {},
): AuditRecord {
  return {
    actor: kind === "confirmation" ? "user" : "audit_agent",
    completeness: flags.partial ? "partial" : flags.hidden ? "hidden" : "complete",
    confidence: flags.partial ? "low" : "medium",
    evidenceRefs: [
      {
        available: !flags.hidden,
        hidden: flags.hidden ?? false,
        id: `evidence-${id}`,
        kind: kind === "file_change" ? "file_change" : "observation",
        label: "Evidence summary",
        redacted: false,
        summary: "Evidence is represented as a safe user-readable summary.",
      },
    ],
    filterKind,
    flags: {
      hidden: false,
      partial: false,
      redacted: false,
      stale: false,
      userVisible: true,
      ...flags,
    },
    id,
    kind,
    occurredAt: "2026-05-24T10:01:00Z",
    relatedRecordIds: [],
    scope: {
      kind: "task",
      sessionId,
      taskNodeId,
    },
    severity,
    sourceLabel: "AuditAgent",
    summary: `${title} summary.`,
    taskNodeId,
    title,
    verdict,
  };
}

function recordDetail(recordView: AuditRecord): AuditRecordDetail {
  return {
    ...recordView,
    body: `${recordView.title} detail body.`,
    disclosure: {
      hiddenReason: recordView.flags.hidden ? "Evidence is permission-limited." : null,
      partialReason: recordView.flags.partial ? "Evidence is incomplete." : null,
      rawPayloadAvailable: false,
      rawPayloadShown: false,
    },
    evidence: recordView.evidenceRefs.map((item) => ({
      ...item,
      occurredAt: "2026-05-24T10:01:00Z",
      source: "mock",
    })),
    outcome: recordView.verdict === "failed" ? "Blocking issue." : "Review available.",
    rawPayload: null,
    references: [
      {
        kind: "task",
        label: "Task implementation",
        ref: { id: taskNodeId, kind: "draft_task" },
      },
    ],
    relatedLogs: [],
    whyItMatters: "Audit detail explains trust, evidence, and gaps.",
  };
}

function filterViews(records: AuditRecord[]): AuditPageSnapshot["filters"] {
  const counts = recordCounts(records);
  return filterKinds.map((kind) => ({
    count: counts[kind],
    enabled: true,
    kind,
    label: kind,
  }));
}

function recordCounts(records: AuditRecord[]): Record<AuditFilterKind, number> {
  const counts: Record<AuditFilterKind, number> = {
    actions: 0,
    all: records.length,
    config: 0,
    confirmations: 0,
    files: 0,
    logs: 0,
    results: 0,
    risks: 0,
    system: 0,
  };

  for (const item of records) {
    counts[item.filterKind] += 1;
  }

  return counts;
}

function errorResponse<T>(code: string, message: string): QueryResponse<T> {
  const error: ApiError = {
    code: "internal_error",
    details: { code },
    message,
    retryable: true,
  };

  return {
    data: null,
    error,
    generatedAt: "2026-05-24T10:02:00Z",
    ok: false,
    requestId: `request-error-${code}`,
  };
}

const filterKinds: readonly AuditFilterKind[] = [
  "all",
  "confirmations",
  "actions",
  "risks",
  "files",
  "results",
  "system",
  "config",
  "logs",
];
