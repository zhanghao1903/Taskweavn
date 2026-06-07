import { describe, expect, it } from "vitest";

import type { MainPageSnapshot, TaskNodeId } from "../../shared/api/types";
import type {
  DetailOverride,
  EventConnectionStatus,
  MainPageSelectionTarget,
} from "./mainPageUiTypes";
import type { MainPageStateId } from "./mockPlatoApi";
import { getMainPageMockSnapshot } from "./mockPlatoApi";
import { buildMainPageViewModel } from "./mainPageViewModel";

describe("buildMainPageViewModel", () => {
  it("routes an empty session input to TaskTree generation", () => {
    const viewModel = buildViewModel("s1-empty");

    expect(viewModel.detail.kind).toBe("note");
    expect(viewModel.input).toMatchObject({
      mode: "generate_task_tree",
      target: "session",
      taskNodeId: null,
    });
    expect(viewModel.workspace.showPublishTaskTree).toBe(false);
    expect(viewModel.workspace.title).toBe("Start a new session");
  });

  it("marks the empty task workspace as generating while initial input is pending", () => {
    const viewModel = buildViewModel("s1-empty", {
      inputDisabled: true,
    });

    expect(viewModel.taskWorkspace.isGeneratingTaskPlan).toBe(true);
  });

  it("does not show the generation transition once a TaskTree exists", () => {
    const viewModel = buildViewModel("s3-draft-ready", {
      inputDisabled: true,
    });

    expect(viewModel.taskWorkspace.isGeneratingTaskPlan).toBe(false);
  });

  it("does not replace authoring ASK work areas with the generation transition", () => {
    const viewModel = buildViewModel("s2-understanding", {
      inputDisabled: true,
    });

    expect(viewModel.mainWorkArea.kind).toBe("authoringAsk");
    expect(viewModel.taskWorkspace.isGeneratingTaskPlan).toBe(false);
  });

  it("routes draft-ready input to plan guidance and exposes publish", () => {
    const viewModel = buildViewModel("s3-draft-ready");

    expect(viewModel.detail.kind).toBe("plan");
    expect(viewModel.input).toMatchObject({
      mode: "append_plan_input",
      scope: {
        description: null,
        label: "Writing to plan",
        placeholder: "Ask Plato to refine the overall plan.",
      },
      target: "plan",
      taskNodeId: null,
    });
    expect(viewModel.taskWorkspace.isTaskPlanSelected).toBe(true);
    expect(viewModel.topBar.statuses).toHaveLength(2);
    expect(viewModel.workspace.showPublishTaskTree).toBe(true);
    expect(viewModel.workspace.title).toBe("Plan & Progress");
  });

  it("replaces the main work area when authoring ASK is pending", () => {
    const viewModel = buildViewModel("s2-understanding");

    expect(viewModel.mainWorkArea.kind).toBe("authoringAsk");
    if (viewModel.mainWorkArea.kind !== "authoringAsk") {
      throw new Error(`Expected authoring ASK work area.`);
    }
    expect(viewModel.mainWorkArea.authoringAsk).toMatchObject({
      rawTaskId: "raw-task-website-goal",
      isSubmitting: false,
    });
    expect(viewModel.mainWorkArea.authoringAsk.asks).toHaveLength(2);
    expect(viewModel.input.disabled).toBe(true);
    expect(viewModel.input.disabledReason).toBe(
      "Answer the planning questions in the main work area.",
    );
    expect(viewModel.workspace.showPublishTaskTree).toBe(false);
  });

  it("keeps TaskTree as the active work area when authoring asks are superseded", () => {
    const { snapshot } = getMainPageMockSnapshot("s3-draft-ready");
    const dirtySnapshot: MainPageSnapshot = {
      ...snapshot,
      planning: {
        asks: [
          {
            id: "ask-stale-authoring",
            options: [],
            question: "Which deployment target?",
            reason: "Old authoring context from before the TaskTree was generated.",
            required: true,
            status: "superseded",
          },
        ],
        sourceRawTaskId: "raw-task-stale",
        state: "draft_ready",
        summary: "A TaskTree already exists.",
        title: "Planning questions",
        validation: null,
      },
    };
    const viewModel = buildViewModel("s3-draft-ready", {
      snapshot: dirtySnapshot,
    });

    expect(viewModel.mainWorkArea.kind).toBe("taskWorkspace");
    expect(viewModel.input.disabled).toBe(false);
    expect(viewModel.input.target).toBe("plan");
    expect(viewModel.workspace.showPublishTaskTree).toBe(true);
  });

  it("surfaces dirty authoring diagnostics without replacing the task workspace", () => {
    const { snapshot } = getMainPageMockSnapshot("s3-draft-ready");
    const dirtySnapshot: MainPageSnapshot = {
      ...snapshot,
      planning: {
        ...(snapshot.planning ?? {
          asks: [],
          sourceRawTaskId: null,
          state: "draft_ready",
          summary: null,
          title: "Task Tree",
          validation: null,
        }),
        diagnostics: [
          {
            code: "dirty_authoring_state",
            message:
              "A stale authoring draft was found after this TaskTree was generated.",
            severity: "warning",
          },
        ],
      },
    };
    const viewModel = buildViewModel("s3-draft-ready", {
      snapshot: dirtySnapshot,
    });

    expect(viewModel.mainWorkArea.kind).toBe("taskWorkspace");
    expect(viewModel.taskWorkspace.authoringDiagnostic).toEqual({
      code: "dirty_authoring_state",
      message:
        "A stale authoring draft was found after this TaskTree was generated.",
      severity: "warning",
    });
  });

  it("routes selected TaskNode input to task guidance", () => {
    const viewModel = buildViewModel("s3-draft-ready", {
      selectedTaskNodeId: "task-visual-direction",
    });

    expect(viewModel.detail.kind).toBe("task");
    expect(viewModel.detail.header.eyebrow).toBe("Task");
    expect(viewModel.detail.header.title).toBe("Visual direction");
    expect(viewModel.input).toMatchObject({
      mode: "append_task_input",
      scope: {
        description: null,
        label: "Writing to Task 3",
        placeholder: "Add guidance for this task.",
      },
      target: "task",
      taskNodeId: "task-visual-direction",
    });
  });

  it("lets explicit plan selection override an initial TaskNode focus", () => {
    const viewModel = buildViewModel("s4-task-selected", {
      selectionTarget: "plan",
    });

    expect(viewModel.detail.kind).toBe("plan");
    expect(viewModel.taskWorkspace.selectedTask).toBeUndefined();
    expect(viewModel.taskWorkspace.selectedTaskNodeId).toBeNull();
    expect(viewModel.input).toMatchObject({
      mode: "append_plan_input",
      target: "plan",
      taskNodeId: null,
    });
  });

  it("surfaces canonical permission reasons for disabled input", () => {
    const viewModel = buildViewModel("s10-permission-denied");

    expect(viewModel.input.disabled).toBe(true);
    expect(viewModel.input.disabledReason).toBe("This task is read-only right now.");
    expect(viewModel.topBar.statuses[0]).toEqual({
      label: "Read-only",
      tone: "danger",
    });
  });

  it("uses TaskNode permission dimensions for selected task input availability", () => {
    const viewModel = buildViewModel("s3-draft-ready", {
      selectedTaskNodeId: "task-requirements",
    });

    expect(viewModel.input).toMatchObject({
      disabled: true,
      disabledReason: "Completed tasks are read-only.",
      mode: "append_task_input",
      target: "task",
      taskNodeId: "task-requirements",
    });
  });

  it("keeps confirmation focus as an explicit detail variant", () => {
    const viewModel = buildViewModel("s7-confirmation");

    expect(viewModel.detail.kind).toBe("confirmation");
    if (viewModel.detail.kind !== "confirmation") {
      throw new Error(`Expected confirmation detail, got ${viewModel.detail.kind}`);
    }
    expect(viewModel.detail.confirmation?.id).toBe("confirmation-visual-baseline");
    expect(viewModel.input.mode).toBe("append_task_input");
  });

  it("shows execution ASK detail while preserving the task workspace", () => {
    const viewModel = buildViewModel("s14-execution-ask");

    expect(viewModel.mainWorkArea.kind).toBe("taskWorkspace");
    expect(viewModel.detail.kind).toBe("executionAsk");
    if (viewModel.detail.kind !== "executionAsk") {
      throw new Error(`Expected executionAsk detail, got ${viewModel.detail.kind}`);
    }
    expect(viewModel.detail.ask.id).toBe("ask-deployment-target");
    expect(viewModel.detail.selectedTask?.id).toBe("task-implementation");
    expect(viewModel.taskWorkspace.taskTree?.nodes).toHaveLength(4);
  });

  it("keeps file-change review as an explicit detail variant", () => {
    const viewModel = buildViewModel("s9-file-changes");

    expect(viewModel.detail.kind).toBe("fileChanges");
    if (viewModel.detail.kind !== "fileChanges") {
      throw new Error(`Expected fileChanges detail, got ${viewModel.detail.kind}`);
    }
    expect(viewModel.detail.fileChangeSummary.changedFiles).toHaveLength(3);
    expect(viewModel.taskWorkspace.fileChangeSummary?.recursive).toBe(true);
  });

  it("builds an enabled audit entry by default once the Audit Page route exists", () => {
    const viewModel = buildViewModel("s9-file-changes");

    expect(viewModel.workspace.auditEntry).toMatchObject({
      disabledReason: null,
      href: "/sessions/session-website-plan/tasks/task-implementation/audit?entry=from_file_change&filter=files&returnFocus=file_change&returnSessionId=session-website-plan&returnTaskNodeId=task-implementation",
      isEnabled: true,
      returnFocus: "file_change",
      scope: "task",
    });
  });

  it("keeps the audit entry disabled when the Audit Page route is unavailable", () => {
    const viewModel = buildViewModel("s9-file-changes", {
      auditRouteAvailable: false,
    });

    expect(viewModel.workspace.auditEntry).toMatchObject({
      disabledReason: "Audit is not available for this view yet.",
      href: "/sessions/session-website-plan/tasks/task-implementation/audit?entry=from_file_change&filter=files&returnFocus=file_change&returnSessionId=session-website-plan&returnTaskNodeId=task-implementation",
      isEnabled: false,
      returnFocus: "file_change",
      scope: "task",
    });
  });

  it("builds route-ready task audit entries with return context when enabled", () => {
    const viewModel = buildViewModel("s7-confirmation", {
      auditRouteAvailable: true,
    });

    expect(viewModel.workspace.auditEntry).toMatchObject({
      disabledReason: null,
      href: "/sessions/session-website-plan/tasks/task-visual-direction/audit?entry=from_confirmation&filter=confirmations&returnFocus=confirmation&returnSessionId=session-website-plan&returnTaskNodeId=task-visual-direction",
      isEnabled: true,
      returnFocus: "confirmation",
      scope: "task",
    });
  });

  it("builds route-ready session audit entries with return context when enabled", () => {
    const viewModel = buildViewModel("s8-completed", {
      auditRouteAvailable: true,
    });

    expect(viewModel.workspace.auditEntry).toMatchObject({
      disabledReason: null,
      href: "/sessions/session-website-plan/audit?entry=from_result&filter=results&returnFocus=result&returnSessionId=session-website-plan",
      isEnabled: true,
      returnFocus: "result",
      scope: "session",
    });
  });
});

function buildViewModel(
  stateId: MainPageStateId,
  overrides: {
    auditRouteAvailable?: boolean;
    detailOverride?: DetailOverride;
    eventConnectionStatus?: EventConnectionStatus;
    inputDisabled?: boolean;
    selectionTarget?: MainPageSelectionTarget;
    selectedTaskNodeId?: TaskNodeId | null;
    snapshot?: MainPageSnapshot;
  } = {},
) {
  const { metadata, snapshot } = getMainPageMockSnapshot(stateId);

  return buildMainPageViewModel({
    auditRouteAvailable: overrides.auditRouteAvailable,
    authoringAskError: null,
    confirmationError: null,
    detailOverride: overrides.detailOverride ?? "auto",
    eventConnectionStatus: overrides.eventConnectionStatus ?? "disconnected",
    eventError: null,
    isAnsweringAuthoringAsk: false,
    executionAskError: null,
    isAnsweringAsk: false,
    isCancellingAsk: false,
    isDeferringAsk: false,
    inputDisabled: overrides.inputDisabled ?? false,
    isPublishingTaskTree: false,
    isRetryingTask: false,
    isStoppingTask: false,
    isResolvingConfirmation: false,
    metadata,
    selectionTarget: overrides.selectionTarget,
    selectedTaskNodeId: overrides.selectedTaskNodeId ?? null,
    snapshot: overrides.snapshot ?? snapshot,
    taskTreeCommandError: null,
    uiNotice: null,
  });
}
