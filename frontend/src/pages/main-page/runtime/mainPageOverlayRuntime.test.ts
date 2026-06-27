import { describe, expect, it } from "vitest";

import type { SessionActivityItemView } from "../../../shared/api/types";
import {
  initialMainPageOverlayState,
  mainPageOverlayReducer,
} from "./mainPageOverlayRuntime";

describe("mainPageOverlayRuntime", () => {
  it("opens Activity with a selected item and tracks load lifecycle", () => {
    const opened = mainPageOverlayReducer(initialMainPageOverlayState, {
      selectedActivityItemId: "activity-1",
      type: "activity.opened",
    });

    expect(opened.activeOverlay).toBe("activity");
    expect(opened.selectedActivityItemId).toBe("activity-1");

    const loading = mainPageOverlayReducer(opened, {
      type: "activity.load_started",
    });

    expect(loading.isActivityLoading).toBe(true);
    expect(loading.activityError).toBeNull();

    const loaded = mainPageOverlayReducer(loading, {
      items: [activityItem("activity-1")],
      type: "activity.load_succeeded",
    });

    expect(loaded.isActivityLoading).toBe(false);
    expect(loaded.activityItems).toHaveLength(1);
  });

  it("moves archived plan selection through archive list and detail states", () => {
    const listOpen = mainPageOverlayReducer(initialMainPageOverlayState, {
      type: "archived_plans.opened",
    });
    const planOpen = mainPageOverlayReducer(listOpen, {
      planId: "plan-1",
      type: "archived_plan.opened",
    });
    const taskSelected = mainPageOverlayReducer(planOpen, {
      taskNodeId: "task-1",
      type: "archived_plan.task_selected",
    });

    expect(taskSelected.activeOverlay).toBe("archived_plan_detail");
    expect(taskSelected.selectedArchivedPlanId).toBe("plan-1");
    expect(taskSelected.selectedArchivedPlanTaskNodeId).toBe("task-1");

    expect(
      mainPageOverlayReducer(taskSelected, {
        type: "archived_plan.overview_selected",
      }).selectedArchivedPlanTaskNodeId,
    ).toBeNull();
  });

  it("clears unavailable archived plan selection on archive sync", () => {
    const planOpen = mainPageOverlayReducer(initialMainPageOverlayState, {
      planId: "plan-1",
      type: "archived_plan.opened",
    });

    const synced = mainPageOverlayReducer(planOpen, {
      availablePlanIds: ["plan-2"],
      type: "archived_plans.synced",
    });

    expect(synced.activeOverlay).toBe("none");
    expect(synced.selectedArchivedPlanId).toBeNull();
  });

  it("tracks diagnostic export status inside overlay state", () => {
    const exporting = mainPageOverlayReducer(initialMainPageOverlayState, {
      body: "Exporting diagnostics",
      type: "diagnostic_export.started",
    });

    expect(exporting.isExportingActivityDiagnostic).toBe(true);
    expect(exporting.activityStatusMessage).toEqual({
      body: "Exporting diagnostics",
      tone: "info",
    });

    const failed = mainPageOverlayReducer(exporting, {
      body: "Export failed",
      type: "diagnostic_export.failed",
    });

    expect(failed.isExportingActivityDiagnostic).toBe(false);
    expect(failed.activityStatusMessage).toEqual({
      body: "Export failed",
      tone: "danger",
    });
  });
});

function activityItem(id: string): SessionActivityItemView {
  return {
    body: "Activity body",
    disclosureLevel: "public",
    id,
    kind: "execution_update",
    occurredAt: "2026-06-27T00:00:00.000Z",
    planId: null,
    relatedRefs: [],
    scopeKind: "session",
    sessionId: "session-1",
    sideEffect: "no_effect",
    sourceId: id,
    sourceKind: "message_stream",
    taskNodeId: null,
    title: "Activity title",
  };
}
