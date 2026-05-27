import { describe, expect, it } from "vitest";

import { createAuditMockApi } from "./mockAuditApi";
import {
  getAuditMockSnapshot,
  getAuditMockSnapshotResponse,
  listAuditMockScenarios,
} from "./mockAuditScenarios";

describe("Audit Page mock scenarios", () => {
  it("declares the required Audit Page state scenarios", () => {
    expect(listAuditMockScenarios().map((scenario) => scenario.id)).toEqual([
      "a1-audit-empty",
      "a2-audit-loading",
      "a3-records-ready",
      "a4-record-selected",
      "a5-partial-evidence",
      "a6-hidden-evidence",
      "a7-warning-verdict",
      "a8-failed-verdict",
      "a9-inconclusive-verdict",
      "a10-not-available",
      "a11-permission-denied",
      "a12-stale-snapshot",
      "a13-query-error",
      "a14-evidence-load-error",
    ]);
  });

  it("loads a valid AuditPageSnapshot for every manifest", () => {
    for (const scenario of listAuditMockScenarios()) {
      const response = getAuditMockSnapshotResponse(scenario.id);

      expect(response.ok).toBe(true);
      expect(response.data?.schemaVersion).toBe("plato.audit.v1");
      expect(response.data?.overview.verdict).toBe(
        scenario.canonicalStates.auditVerdict,
      );
      expect(response.data?.pageState.kind).toBe(
        scenario.canonicalStates.pageState,
      );
      expect(scenario.expectedVisibleComponents.length).toBeGreaterThan(0);
    }
  });

  it("keeps permission denied, stale, and hidden evidence states distinct", () => {
    expect(getAuditMockSnapshot("a6-hidden-evidence")).toMatchObject({
      overview: {
        hiddenEvidenceCount: 2,
        verdict: "warning",
      },
      pageState: {
        kind: "hidden_evidence",
      },
      permissions: {
        canViewAudit: true,
      },
    });

    expect(getAuditMockSnapshot("a11-permission-denied")).toMatchObject({
      pageState: {
        kind: "permission_denied",
      },
      permissions: {
        canViewAudit: false,
      },
    });

    expect(getAuditMockSnapshot("a12-stale-snapshot")).toMatchObject({
      pageState: {
        kind: "stale",
      },
    });
  });

  it("provides a mock Audit API shell over scenario fixtures", async () => {
    const api = createAuditMockApi("a4-record-selected");

    await expect(
      api.getAuditSnapshot({ sessionId: "session-website-plan" }),
    ).resolves.toMatchObject({
      data: {
        selectedRecord: {
          id: "record-file-1",
        },
      },
      ok: true,
    });

    await expect(
      api.listAuditRecords({ sessionId: "session-website-plan" }),
    ).resolves.toMatchObject({
      data: {
        records: [expect.objectContaining({ id: "record-file-1" })],
      },
      ok: true,
    });

    await expect(
      api.getAuditRecordDetail({
        recordId: "record-file-1",
        sessionId: "session-website-plan",
      }),
    ).resolves.toMatchObject({
      data: {
        body: expect.stringContaining("detail body"),
      },
      ok: true,
    });
  });

  it("keeps evidence load errors scoped to evidence detail", async () => {
    const api = createAuditMockApi("a14-evidence-load-error");

    await expect(
      api.getAuditSnapshot({ sessionId: "session-website-plan" }),
    ).resolves.toMatchObject({
      data: {
        records: [expect.objectContaining({ id: "record-evidence-error-1" })],
      },
      ok: true,
    });

    await expect(
      api.getEvidenceDetail({
        evidenceId: "evidence-record-evidence-error-1",
        sessionId: "session-website-plan",
      }),
    ).resolves.toMatchObject({
      error: {
        code: "internal_error",
      },
      ok: false,
    });
  });
});
