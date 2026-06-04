import { describe, expect, it } from "vitest";

import type { TaskNodeId } from "../../shared/api/types";
import type { DetailOverride, EventConnectionStatus } from "./mainPageUiTypes";
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

  it("routes draft-ready session input to session guidance and exposes publish", () => {
    const viewModel = buildViewModel("s3-draft-ready");

    expect(viewModel.detail.kind).toBe("note");
    expect(viewModel.input).toMatchObject({
      mode: "append_session_input",
      target: "session",
      taskNodeId: null,
    });
    expect(viewModel.topBar.statuses).toHaveLength(2);
    expect(viewModel.workspace.showPublishTaskTree).toBe(true);
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

  it("routes selected TaskNode input to task guidance", () => {
    const viewModel = buildViewModel("s3-draft-ready", {
      selectedTaskNodeId: "task-visual-direction",
    });

    expect(viewModel.detail.kind).toBe("task");
    expect(viewModel.detail.header.title).toBe("Visual direction");
    expect(viewModel.input).toMatchObject({
      mode: "append_task_input",
      target: "task",
      taskNodeId: "task-visual-direction",
    });
  });

  it("surfaces canonical permission reasons for disabled input", () => {
    const viewModel = buildViewModel("s10-permission-denied");

    expect(viewModel.input.disabled).toBe(true);
    expect(viewModel.input.disabledReason).toBe(
      "Current permission context is read-only.",
    );
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
      disabledReason:
        "Audit entry is reserved until the Audit Page UI is implemented.",
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
    selectedTaskNodeId?: TaskNodeId | null;
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
    inputDisabled: overrides.inputDisabled ?? false,
    isPublishingTaskTree: false,
    isRetryingTask: false,
    isStoppingTask: false,
    isResolvingConfirmation: false,
    metadata,
    selectedTaskNodeId: overrides.selectedTaskNodeId ?? null,
    snapshot,
    taskTreeCommandError: null,
    uiNotice: null,
  });
}
