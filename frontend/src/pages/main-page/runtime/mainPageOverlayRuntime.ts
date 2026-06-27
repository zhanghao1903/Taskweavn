import type { SessionActivityItemView, TaskNodeId } from "../../../shared/api/types";

export type MainPageOverlayKind =
  | "activity"
  | "archived_plan_detail"
  | "archived_plans"
  | "none";

export type MainPageOverlayStatusMessage = {
  body: string;
  tone: "danger" | "info";
};

export type MainPageOverlayState = {
  activeOverlay: MainPageOverlayKind;
  activityError: string | null;
  activityItems: readonly SessionActivityItemView[];
  activityLoadKey: number;
  activityStatusMessage: MainPageOverlayStatusMessage | null;
  isActivityLoading: boolean;
  isExportingActivityDiagnostic: boolean;
  selectedActivityItemId: string | null;
  selectedArchivedPlanId: string | null;
  selectedArchivedPlanTaskNodeId: TaskNodeId | null;
};

export type MainPageOverlayAction =
  | {
      selectedActivityItemId?: string | null;
      type: "activity.opened";
    }
  | { type: "activity.closed" }
  | { type: "activity.load_started" }
  | {
      error: string;
      type: "activity.load_failed";
    }
  | {
      items: readonly SessionActivityItemView[];
      type: "activity.load_succeeded";
    }
  | { type: "activity.retry_requested" }
  | {
      body: string;
      type: "diagnostic_export.started";
    }
  | {
      body: string;
      type: "diagnostic_export.failed";
    }
  | {
      body: string;
      type: "diagnostic_export.succeeded";
    }
  | { type: "overlay.closed" }
  | { type: "overlay.reset" }
  | { type: "archived_plans.opened" }
  | {
      planId: string;
      type: "archived_plan.opened";
    }
  | { type: "archived_plan.overview_selected" }
  | {
      taskNodeId: TaskNodeId;
      type: "archived_plan.task_selected";
    }
  | {
      availablePlanIds: readonly string[];
      type: "archived_plans.synced";
    };

export const initialMainPageOverlayState: MainPageOverlayState = {
  activeOverlay: "none",
  activityError: null,
  activityItems: [],
  activityLoadKey: 0,
  activityStatusMessage: null,
  isActivityLoading: false,
  isExportingActivityDiagnostic: false,
  selectedActivityItemId: null,
  selectedArchivedPlanId: null,
  selectedArchivedPlanTaskNodeId: null,
};

export function mainPageOverlayReducer(
  state: MainPageOverlayState,
  action: MainPageOverlayAction,
): MainPageOverlayState {
  switch (action.type) {
    case "activity.opened":
      return {
        ...state,
        activeOverlay: "activity",
        selectedActivityItemId: action.selectedActivityItemId ?? null,
        selectedArchivedPlanId: null,
        selectedArchivedPlanTaskNodeId: null,
      };

    case "activity.closed":
    case "overlay.closed":
      return {
        ...state,
        activeOverlay: "none",
        selectedActivityItemId: null,
      };

    case "activity.load_started":
      return {
        ...state,
        activityError: null,
        isActivityLoading: true,
      };

    case "activity.load_failed":
      return {
        ...state,
        activityError: action.error,
        isActivityLoading: false,
      };

    case "activity.load_succeeded":
      return {
        ...state,
        activityItems: action.items,
        isActivityLoading: false,
      };

    case "activity.retry_requested":
      return {
        ...state,
        activityLoadKey: state.activityLoadKey + 1,
      };

    case "diagnostic_export.started":
      return {
        ...state,
        activityStatusMessage: {
          body: action.body,
          tone: "info",
        },
        isExportingActivityDiagnostic: true,
      };

    case "diagnostic_export.failed":
      return {
        ...state,
        activityStatusMessage: {
          body: action.body,
          tone: "danger",
        },
        isExportingActivityDiagnostic: false,
      };

    case "diagnostic_export.succeeded":
      return {
        ...state,
        activityStatusMessage: {
          body: action.body,
          tone: "info",
        },
        isExportingActivityDiagnostic: false,
      };

    case "archived_plans.opened":
      return {
        ...state,
        activeOverlay: "archived_plans",
        selectedActivityItemId: null,
        selectedArchivedPlanId: null,
        selectedArchivedPlanTaskNodeId: null,
      };

    case "archived_plan.opened":
      return {
        ...state,
        activeOverlay: "archived_plan_detail",
        selectedArchivedPlanId: action.planId,
        selectedArchivedPlanTaskNodeId: null,
      };

    case "archived_plan.overview_selected":
      return {
        ...state,
        selectedArchivedPlanTaskNodeId: null,
      };

    case "archived_plan.task_selected":
      return {
        ...state,
        selectedArchivedPlanTaskNodeId: action.taskNodeId,
      };

    case "archived_plans.synced":
      if (
        state.selectedArchivedPlanId === null ||
        action.availablePlanIds.includes(state.selectedArchivedPlanId)
      ) {
        return state;
      }
      return {
        ...state,
        activeOverlay:
          state.activeOverlay === "archived_plan_detail"
            ? "none"
            : state.activeOverlay,
        selectedArchivedPlanId: null,
        selectedArchivedPlanTaskNodeId: null,
      };

    case "overlay.reset":
      return initialMainPageOverlayState;
  }
}
