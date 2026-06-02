import { describe, expect, it } from "vitest";

import type {
  AuditPageSnapshot,
  AuditRecord,
  AuditRecordDetail,
} from "../../shared/api/types";
import {
  activeAuditFilter,
  activeAuditRecordId,
  resolveSelectedAuditRecord,
} from "./auditPageSelection";

const baseRecord: AuditRecord = {
  actor: "agent",
  completeness: "complete",
  confidence: "high",
  evidenceRefs: [
    {
      available: true,
      hidden: false,
      id: "evidence-1",
      kind: "action",
      label: "Action",
      redacted: false,
      summary: "Action evidence.",
    },
  ],
  filterKind: "actions",
  flags: {
    hidden: false,
    partial: false,
    redacted: false,
    stale: false,
    userVisible: true,
  },
  id: "record-1",
  kind: "action",
  occurredAt: "2026-05-24T10:00:00Z",
  relatedRecordIds: [],
  scope: {
    kind: "task",
    sessionId: "session-1",
    taskNodeId: "task-1",
  },
  severity: "info",
  sourceLabel: "EventStream",
  summary: "Action completed.",
  title: "Action completed",
  verdict: "passed",
};

function snapshot(
  overrides: Partial<AuditPageSnapshot> = {},
): AuditPageSnapshot {
  return {
    records: [baseRecord],
    request: {
      filter: "all",
      includeDetail: false,
      limit: 50,
      recordId: null,
    },
    selectedRecord: null,
    ...overrides,
  } as AuditPageSnapshot;
}

describe("auditPageSelection", () => {
  it("uses route request fields as default active selection", () => {
    const current = snapshot({
      request: {
        filter: "confirmations",
        includeDetail: true,
        limit: 50,
        recordId: "record-route",
      },
    });

    expect(activeAuditFilter(current)).toBe("confirmations");
    expect(activeAuditRecordId(current, undefined)).toBe("record-route");
  });

  it("gives explicit selected record id priority over snapshot state", () => {
    const selectedRecord = {
      ...baseRecord,
      body: "Selected detail.",
      disclosure: {
        rawPayloadAvailable: false,
        rawPayloadShown: false,
      },
      evidence: [],
      id: "record-snapshot",
      outcome: null,
      rawPayload: null,
      references: [],
      relatedLogs: [],
      whyItMatters: "Snapshot detail exists.",
    } satisfies AuditRecordDetail;
    const current = snapshot({
      request: {
        filter: "all",
        includeDetail: true,
        limit: 50,
        recordId: "record-route",
      },
      selectedRecord,
    });

    expect(activeAuditRecordId(current, "record-explicit")).toBe("record-explicit");
    expect(resolveSelectedAuditRecord(current, "record-explicit")).toBe(selectedRecord);
  });

  it("builds the existing fallback detail when selected record is not preloaded", () => {
    const resolved = resolveSelectedAuditRecord(snapshot(), "record-1");

    expect(resolved).toMatchObject({
      body: "Record detail is not loaded yet.",
      disclosure: {
        rawPayloadAvailable: false,
        rawPayloadShown: false,
      },
      evidence: [
        {
          id: "evidence-1",
          source: "mock",
        },
      ],
      outcome: null,
      rawPayload: null,
      references: [],
      relatedLogs: [],
      whyItMatters:
        "Select a record route with detail enabled to load complete evidence.",
    });
  });

  it("returns null when no record is selected or found", () => {
    expect(activeAuditFilter(null)).toBe("all");
    expect(activeAuditRecordId(null, undefined)).toBeNull();
    expect(resolveSelectedAuditRecord(snapshot(), null)).toBeNull();
    expect(resolveSelectedAuditRecord(snapshot(), "missing-record")).toBeNull();
  });
});
