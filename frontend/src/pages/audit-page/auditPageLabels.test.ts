import { describe, expect, it } from "vitest";

import type { ApiUiBoundaryState } from "../../shared/api/apiUiMapping";
import type { AuditPageSnapshot } from "../../shared/api/types";
import {
  auditBoundaryLabel,
  auditCompletenessLabel,
  auditFilterLabel,
  auditLiveStatusCopy,
  auditOverviewMetricFilters,
  auditScopeLabel,
  auditScopeStatusText,
  auditSubjectLabel,
  auditVerdictClassKey,
  auditVerdictLabel,
  auditVerdictNoticeTitle,
} from "./auditPageLabels";

describe("auditPageLabels", () => {
  it("keeps audit filter and overview metric labels stable", () => {
    expect(auditFilterLabel("all")).toBe("All records");
    expect(auditFilterLabel("confirmations")).toBe("Confirmations");
    expect(auditFilterLabel("logs")).toBe("Logs");
    expect(auditOverviewMetricFilters).toEqual([
      { filter: "confirmations", label: "Confirmations" },
      { filter: "risks", label: "Risks" },
      { filter: "files", label: "Files" },
      { filter: "results", label: "Results" },
    ]);
  });

  it("keeps scope labels and subject text stable", () => {
    const snapshot = {
      scope: {
        kind: "task",
        sessionId: "session-1",
        taskNodeId: "task-1",
      },
      selectedTask: {
        title: "Implement homepage",
      },
      session: {
        name: "Website plan",
        status: "running",
      },
    } as AuditPageSnapshot;

    expect(auditScopeLabel(snapshot)).toBe("Scope: Task");
    expect(auditSubjectLabel(snapshot)).toBe("Implement homepage");
    expect(auditScopeStatusText(snapshot)).toBe("Task audit · running");
  });

  it("keeps boundary labels stable", () => {
    expect(
      auditBoundaryLabel({
        disableMutations: true,
        kind: "stale_resync",
        message: "Refresh needed.",
        retryable: true,
        shouldResync: true,
      } satisfies ApiUiBoundaryState),
    ).toBe("Stale snapshot");
    expect(
      auditBoundaryLabel({
        disableMutations: true,
        kind: "permission_denied",
        message: "Permission denied.",
        retryable: false,
        shouldResync: false,
      } satisfies ApiUiBoundaryState),
    ).toBe("Permission denied");
  });

  it("keeps verdict labels, notice titles, and class keys stable", () => {
    expect(auditVerdictLabel("warning")).toBe("Verdict: Warning");
    expect(auditVerdictNoticeTitle("warning")).toBe(
      "Audit found a non-blocking concern.",
    );
    expect(auditVerdictClassKey("warning")).toBe("warning");
    expect(auditVerdictClassKey("not_available")).toBeNull();
  });

  it("keeps completeness and live status labels stable", () => {
    expect(auditCompletenessLabel("not_started")).toBe("Not started");
    expect(
      auditLiveStatusCopy({
        eventCursor: "cursor-1",
        message: null,
        status: "stale",
      }),
    ).toEqual({
      message: "Refreshing from source; current evidence remains readable.",
      title: "Audit snapshot may be stale",
    });
  });
});
