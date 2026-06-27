import { useEffect, useMemo, useReducer } from "react";

import type { SessionActivityItemView } from "../../shared/api/types";
import type { LoadSessionActivity } from "./runtime/adapter";
import {
  initialMainPageOverlayState,
  mainPageOverlayReducer,
} from "./runtime/mainPageOverlayRuntime";
import type { MainPageOverlayState } from "./runtime/mainPageOverlayRuntime";

export type MainPageOverlayRuntimeActions = {
  closeOverlay: () => void;
  failDiagnosticExport: (body: string) => void;
  openActivity: (selectedActivityItemId?: string | null) => void;
  openArchivedPlan: (planId: string) => void;
  openArchivedPlans: () => void;
  retryActivity: () => void;
  selectArchivedPlanOverview: () => void;
  selectArchivedPlanTask: (taskNodeId: string) => void;
  startDiagnosticExport: (body: string) => void;
  succeedDiagnosticExport: (body: string) => void;
};

export type MainPageOverlayRuntime = {
  actions: MainPageOverlayRuntimeActions;
  state: MainPageOverlayState;
};

export function useMainPageOverlayRuntime({
  archivedPlanIds,
  loadActivityErrorMessage,
  loadSessionActivity,
  resolvedWorkspaceId,
  sessionId,
}: {
  archivedPlanIds: readonly string[];
  loadActivityErrorMessage: string;
  loadSessionActivity?: LoadSessionActivity;
  resolvedWorkspaceId: string | null;
  sessionId: string;
}): MainPageOverlayRuntime {
  const [state, dispatch] = useReducer(
    mainPageOverlayReducer,
    initialMainPageOverlayState,
  );

  useEffect(() => {
    dispatch({ type: "overlay.reset" });
  }, [sessionId]);

  useEffect(() => {
    dispatch({
      availablePlanIds: archivedPlanIds,
      type: "archived_plans.synced",
    });
  }, [archivedPlanIds]);

  useEffect(() => {
    if (state.activeOverlay !== "activity" || loadSessionActivity === undefined) {
      return;
    }

    let isCancelled = false;
    dispatch({ type: "activity.load_started" });

    void loadSessionActivity(
      {
        limit: 100,
        sessionId,
      },
      resolvedWorkspaceId,
    )
      .then((timeline) => {
        if (isCancelled) {
          return;
        }
        dispatch({
          items: timeline.items,
          type: "activity.load_succeeded",
        });
      })
      .catch((error: unknown) => {
        if (isCancelled) {
          return;
        }
        dispatch({
          error:
            error instanceof Error ? error.message : loadActivityErrorMessage,
          type: "activity.load_failed",
        });
      });

    return () => {
      isCancelled = true;
    };
  }, [
    loadActivityErrorMessage,
    loadSessionActivity,
    resolvedWorkspaceId,
    sessionId,
    state.activeOverlay,
    state.activityLoadKey,
  ]);

  const actions = useMemo(
    (): MainPageOverlayRuntimeActions => ({
      closeOverlay: () => dispatch({ type: "overlay.closed" }),
      failDiagnosticExport: (body) =>
        dispatch({ body, type: "diagnostic_export.failed" }),
      openActivity: (selectedActivityItemId = null) =>
        dispatch({
          selectedActivityItemId,
          type: "activity.opened",
        }),
      openArchivedPlan: (planId) =>
        dispatch({
          planId,
          type: "archived_plan.opened",
        }),
      openArchivedPlans: () => dispatch({ type: "archived_plans.opened" }),
      retryActivity: () => dispatch({ type: "activity.retry_requested" }),
      selectArchivedPlanOverview: () =>
        dispatch({ type: "archived_plan.overview_selected" }),
      selectArchivedPlanTask: (taskNodeId) =>
        dispatch({
          taskNodeId,
          type: "archived_plan.task_selected",
        }),
      startDiagnosticExport: (body) =>
        dispatch({ body, type: "diagnostic_export.started" }),
      succeedDiagnosticExport: (body) =>
        dispatch({ body, type: "diagnostic_export.succeeded" }),
    }),
    [],
  );

  return {
    actions,
    state,
  };
}

export function newestActivityItemId(
  items: readonly SessionActivityItemView[],
  selectedTaskNodeId: string | null,
): string | null {
  const scopedItems =
    selectedTaskNodeId === null
      ? items
      : items.filter((item) => item.taskNodeId === selectedTaskNodeId);
  const newest = scopedItems
    .slice()
    .sort(
      (left, right) =>
        Date.parse(right.occurredAt) - Date.parse(left.occurredAt),
    )[0];

  return newest?.id ?? null;
}
