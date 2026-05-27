import { describe, expect, it } from "vitest";

import type {
  AuditPageSnapshot,
  EvidenceDetail,
  QueryResponse,
  UiEvent,
} from "./types";

describe("Audit Page frontend contract types", () => {
  it("accepts a mock AuditPageSnapshot fixture matching the P6.1 contract", () => {
    const snapshot = auditSnapshotFixture();
    const response: QueryResponse<AuditPageSnapshot> = {
      cursor: snapshot.cursor,
      data: snapshot,
      error: null,
      generatedAt: snapshot.generatedAt,
      ok: true,
      requestId: "request-audit-1",
    };

    expect(response.data?.schemaVersion).toBe("plato.audit.v1");
    expect(response.data?.overview.verdict).toBe("warning");
    expect(response.data?.records[0]?.flags.partial).toBe(false);
    expect(response.data?.selectedRecord?.evidence[0]?.source).toBe(
      "task_projection",
    );
  });

  it("accepts evidence detail with sanitized payload disclosure", () => {
    const detail: EvidenceDetail = {
      available: true,
      body: "User approved the file edit scope before execution.",
      disclosure: {
        rawPayloadAvailable: true,
        rawPayloadShown: true,
      },
      hidden: false,
      id: "evidence-confirmation-1",
      kind: "message",
      label: "Confirmation message",
      occurredAt: "2026-05-24T10:01:00Z",
      redacted: false,
      sanitizedPayload: {
        content: "{\"decision\":\"confirm\"}",
        format: "json",
        redactions: [],
      },
      source: "message_stream",
      summary: "Confirmation decision summary.",
    };

    expect(detail.sanitizedPayload?.format).toBe("json");
  });

  it("accepts additive audit event literals", () => {
    const event: UiEvent = {
      createdAt: "2026-05-24T10:03:00Z",
      cursor: "cursor-audit-1",
      eventId: "event-audit-1",
      eventType: "audit.snapshot_stale",
      messageIds: [],
      payload: {
        reason: "records changed after the snapshot was generated",
        scope: { kind: "task", sessionId: "session-1", taskNodeId: "task-1" },
      },
      sessionId: "session-1",
      taskNodeIds: ["task-1"],
    };

    expect(event.eventType).toBe("audit.snapshot_stale");
  });
});

function auditSnapshotFixture(): AuditPageSnapshot {
  return {
    cursor: "cursor-audit-1",
    effectiveConfig: {
      effectiveAt: "2026-05-24T10:00:00Z",
      profileLabel: "Balanced autonomy",
      relevantRecordIds: ["record-risk-1"],
      settingsHref: "/settings",
      summary: "User-readable audit profile is active.",
    },
    entryContext: {
      kind: "from_task",
      preferredFilter: "risks",
      preferredRecordId: "record-risk-1",
      sessionId: "session-1",
      sourceRoute: "/sessions/session-1?taskNodeId=task-1",
      taskNodeId: "task-1",
    },
    filters: [
      filter("all", 1),
      filter("confirmations", 0),
      filter("actions", 0),
      filter("risks", 1),
      filter("files", 0),
      filter("results", 0),
      filter("system", 0),
      filter("config", 0),
      filter("logs", 0),
    ],
    generatedAt: "2026-05-24T10:02:00Z",
    overview: {
      completeness: "complete",
      generatedBy: "mock",
      hiddenEvidenceCount: 0,
      importantRecordIds: ["record-risk-1"],
      keyIssue: "One validation step was not verified.",
      recordCounts: {
        actions: 0,
        all: 1,
        config: 0,
        confirmations: 0,
        files: 0,
        logs: 0,
        results: 0,
        risks: 1,
        system: 0,
      },
      summary: "Audit found a non-blocking validation gap.",
      updatedAt: "2026-05-24T10:02:00Z",
      verdict: "warning",
    },
    pageState: { kind: "ready" },
    permissions: {
      canOpenRelatedLogs: true,
      canViewAudit: true,
      canViewEvidence: true,
      canViewHiddenEvidenceReason: false,
    },
    project: {
      id: "project-local",
      name: "Personal Website",
    },
    records: [auditRecord()],
    relatedLogs: [
      {
        enabled: true,
        filters: {
          category: "audit",
          recordId: "record-risk-1",
          sessionId: "session-1",
          taskNodeId: "task-1",
        },
        href: "/sessions/session-1/diagnostics/logs?recordId=record-risk-1",
        label: "View related logs",
      },
    ],
    request: {
      filter: "risks",
      includeDetail: true,
      limit: 50,
      recordId: "record-risk-1",
    },
    returnTarget: {
      focus: "task",
      projectId: "project-local",
      routeName: "main.sessionFallback",
      sessionId: "session-1",
      taskNodeId: "task-1",
      workflowId: "workflow-main",
    },
    schemaVersion: "plato.audit.v1",
    scope: {
      kind: "task",
      sessionId: "session-1",
      taskNodeId: "task-1",
    },
    selectedRecord: {
      ...auditRecord(),
      body: "The task completed, but one validation step was not verified.",
      disclosure: {
        partialReason: "Validation evidence is missing.",
        rawPayloadAvailable: false,
        rawPayloadShown: false,
      },
      evidence: [
        {
          available: true,
          hidden: false,
          id: "evidence-task-1",
          kind: "observation",
          label: "Task projection",
          occurredAt: "2026-05-24T10:01:00Z",
          redacted: false,
          source: "task_projection",
          summary: "Task reached done state with a validation warning.",
        },
      ],
      outcome: "Review recommended.",
      rawPayload: null,
      references: [
        {
          kind: "task",
          label: "Task task-1",
          ref: { id: "task-1", kind: "draft_task" },
        },
      ],
      relatedLogs: [],
      whyItMatters: "The user needs to know whether the result is trustworthy.",
    },
    selectedTask: null,
    session: {
      createdAt: "2026-05-24T10:00:00Z",
      id: "session-1",
      name: "个人网站项目规划",
      projectId: "project-local",
      status: "completed",
      updatedAt: "2026-05-24T10:02:00Z",
      workflowId: "workflow-main",
    },
    workflow: {
      description: "Task planning and execution",
      id: "workflow-main",
      name: "Task Planning & Execution",
    },
  };
}

function auditRecord() {
  return {
    actor: "audit_agent",
    completeness: "complete",
    confidence: "medium",
    evidenceRefs: [
      {
        available: true,
        hidden: false,
        id: "evidence-task-1",
        kind: "observation",
        label: "Task projection",
        redacted: false,
        summary: "Task reached done state with a validation warning.",
      },
    ],
    filterKind: "risks",
    flags: {
      hidden: false,
      partial: false,
      redacted: false,
      stale: false,
      userVisible: true,
    },
    id: "record-risk-1",
    kind: "risk",
    occurredAt: "2026-05-24T10:01:00Z",
    relatedRecordIds: [],
    scope: {
      kind: "task",
      sessionId: "session-1",
      taskNodeId: "task-1",
    },
    severity: "warning",
    sourceLabel: "AuditAgent",
    summary: "Validation evidence is incomplete.",
    taskNodeId: "task-1",
    title: "Post-edit validation was not verified",
    verdict: "warning",
  } satisfies AuditPageSnapshot["records"][number];
}

function filter(kind: AuditPageSnapshot["request"]["filter"], count: number) {
  return {
    count,
    enabled: true,
    kind,
    label: kind,
  };
}
