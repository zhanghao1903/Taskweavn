import { describe, expect, it } from "vitest";

import {
  deriveLegacyTaskNodeStatusDimensions,
  mapLegacyAuditLinkSeverityToVerdict,
  mapLegacySessionStatusToExecutionStatus,
  mapLegacySessionStatusToPlanningState,
  mapLegacyTaskNodeStatusToConfirmationStatus,
  mapLegacyTaskNodeStatusToExecutionStatus,
  mapLegacyTaskNodeStatusToReadiness,
  mapLegacyTaskTreeStatusToExecutionStatus,
  mapLegacyTaskTreeStatusToReadiness,
} from "./statusCompatibility";
import type { TaskNodeCardView } from "./types";

describe("legacy status compatibility mappers", () => {
  it("maps flat session status into separated planning and execution dimensions", () => {
    expect(mapLegacySessionStatusToPlanningState("new")).toBe("empty");
    expect(mapLegacySessionStatusToPlanningState("understanding")).toBe(
      "assessing",
    );
    expect(mapLegacySessionStatusToPlanningState("running")).toBe("published");
    expect(mapLegacySessionStatusToPlanningState("failed")).toBe("unknown");

    expect(mapLegacySessionStatusToExecutionStatus("draft_ready")).toBe(
      "not_started",
    );
    expect(mapLegacySessionStatusToExecutionStatus("waiting_user")).toBe(
      "pending",
    );
    expect(mapLegacySessionStatusToExecutionStatus("completed")).toBe("done");
  });

  it("maps TaskTree status without collapsing readiness and execution", () => {
    expect(mapLegacyTaskTreeStatusToReadiness("draft")).toBe("draft");
    expect(mapLegacyTaskTreeStatusToExecutionStatus("draft")).toBe(
      "not_started",
    );

    expect(mapLegacyTaskTreeStatusToReadiness("running")).toBe("published");
    expect(mapLegacyTaskTreeStatusToExecutionStatus("running")).toBe("running");

    expect(mapLegacyTaskTreeStatusToReadiness("failed")).toBe("published");
    expect(mapLegacyTaskTreeStatusToExecutionStatus("failed")).toBe("failed");
  });

  it("maps TaskNode status into readiness, execution, and confirmation dimensions", () => {
    expect(mapLegacyTaskNodeStatusToReadiness("draft")).toBe("draft");
    expect(mapLegacyTaskNodeStatusToExecutionStatus("draft")).toBe(
      "not_started",
    );

    expect(mapLegacyTaskNodeStatusToReadiness("queued")).toBe("published");
    expect(mapLegacyTaskNodeStatusToExecutionStatus("queued")).toBe("pending");

    expect(mapLegacyTaskNodeStatusToReadiness("waiting_user")).toBe("published");
    expect(mapLegacyTaskNodeStatusToExecutionStatus("waiting_user")).toBe(
      "pending",
    );
    expect(mapLegacyTaskNodeStatusToConfirmationStatus("waiting_user")).toBe(
      "pending",
    );

    expect(mapLegacyTaskNodeStatusToReadiness("cancelled")).toBe("cancelled");
    expect(mapLegacyTaskNodeStatusToExecutionStatus("cancelled")).toBe(
      "cancelled",
    );
  });

  it("derives pending confirmation from badges even when the flat status is not waiting_user", () => {
    expect(
      mapLegacyTaskNodeStatusToConfirmationStatus("running", {
        pendingConfirmationCount: 1,
      }),
    ).toBe("pending");
  });

  it("maps link-only audit severity into the canonical audit verdict fallback", () => {
    expect(mapLegacyAuditLinkSeverityToVerdict()).toBe("not_available");
    expect(mapLegacyAuditLinkSeverityToVerdict("info")).toBe("not_available");
    expect(mapLegacyAuditLinkSeverityToVerdict("warning")).toBe("warning");
    expect(mapLegacyAuditLinkSeverityToVerdict("danger")).toBe("failed");
  });

  it("derives all target dimensions from a legacy TaskNodeCardView", () => {
    const node: Pick<TaskNodeCardView, "badges" | "status"> = {
      badges: {
        directFileChangeCount: 0,
        pendingConfirmationCount: 1,
        subtreeFileChangeCount: 0,
        unreadMessageCount: 0,
      },
      status: "running",
    };

    expect(deriveLegacyTaskNodeStatusDimensions(node)).toEqual({
      auditVerdict: "not_available",
      confirmation: "pending",
      execution: "running",
      readiness: "published",
    });
  });
});
