import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { MainPageSnapshot, TaskNodeId } from "../../shared/api/types";
import type { WorkspaceCatalogResult } from "../../shared/api/platoApi";
import styles from "./MainPage.module.css";
import { MainPageWorkbench } from "./MainPageWorkbench";
import type { MainPageViewModel } from "./mainPageViewModel";
import { buildMainPageViewModel } from "./mainPageViewModel";
import type { MainPageStateId } from "./mockPlatoApi";
import { getMainPageMockSnapshot } from "./mockPlatoApi";
import type { MainPageWorkspaceRuntime } from "./MainPageWorkspaceSwitcher";
import type { MainPageController } from "./useMainPageController";

describe("MainPageWorkbench layout", () => {
  it("expands the workspace when generic notes hide the detail panel", () => {
    const viewModel = buildViewModel("s1-empty");

    expect(viewModel.detail.kind).toBe("note");

    renderWorkbench(viewModel);

    expect(screen.getByRole("main")).toHaveClass(styles.pageWithoutDetail);
    expect(screen.getByLabelText("Task workspace")).toBeInTheDocument();
    expect(
      screen.queryByRole("complementary", { name: "Details" }),
    ).not.toBeInTheDocument();
  });

  it("keeps the empty-session input in the bottom input area", () => {
    const viewModel = buildViewModel("s1-empty");

    expect(viewModel.taskWorkspace.taskTree).toBeNull();

    renderWorkbench(viewModel);

    const inputForm = screen.getByLabelText("Context message").closest("form");

    expect(inputForm).not.toBeNull();
    expect(inputForm).toHaveClass(styles.contextInput);
    expect(inputForm).not.toHaveClass(styles.floatingContextInput);
  });

  it("keeps the detail column when the whole plan is selected", () => {
    const viewModel = buildViewModel("s3-draft-ready");

    expect(viewModel.detail.kind).toBe("plan");

    renderWorkbench(viewModel);

    expect(screen.getByRole("main")).not.toHaveClass(styles.pageWithoutDetail);
    expect(
      screen.getByRole("complementary", { name: "Details" }),
    ).toBeInTheDocument();
  });

  it("keeps the detail column when a selected TaskNode has detail content", () => {
    const viewModel = buildViewModel("s3-draft-ready", {
      selectedTaskNodeId: "task-visual-direction",
    });

    expect(viewModel.detail.kind).toBe("task");

    renderWorkbench(viewModel);

    expect(screen.getByRole("main")).not.toHaveClass(styles.pageWithoutDetail);
    expect(
      screen.getByRole("complementary", { name: "Details" }),
    ).toBeInTheDocument();
  });

  it("places the plan line above latest activity and the task list", () => {
    const viewModel = buildViewModel("s7-confirmation", {
      selectedTaskNodeId: "task-visual-direction",
    });

    renderWorkbench(viewModel);

    const planLine = screen.getByText("Plan overview").closest("button");
    const latestActivity = screen.getByLabelText("Latest activity");
    const firstTaskCard = screen.getByText("Requirement analysis").closest("button");

    expect(planLine).not.toBeNull();
    expect(firstTaskCard).not.toBeNull();
    expect(
      planLine!.compareDocumentPosition(latestActivity) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      latestActivity.compareDocumentPosition(firstTaskCard!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("wires dirty authoring repair from the diagnostic banner", async () => {
    const user = userEvent.setup();
    const actions = buildActions();
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

    renderWorkbench(viewModel, actions);

    await user.click(
      screen.getByRole("button", { name: "Repair authoring state" }),
    );

    expect(actions.repairAuthoringState).toHaveBeenCalledWith({
      sessionId: "session-website-plan",
    });
  });

  it("keeps the add workspace entry visible in catalog mode", async () => {
    const user = userEvent.setup();
    const chooseWorkspace = vi.fn(async (): Promise<PlatoWorkspaceSelectionResult> => ({
      state: {
        currentWorkspace: workspaceEntry("workspace-local", "Local Project"),
        error: null,
        recentWorkspaces: [],
        status: "ready",
      },
      status: "ready" as const,
    }));
    const viewModel = buildViewModel("s1-empty");

    renderWorkbench(viewModel, buildActions(), {
      activeWorkspaceId: "workspace-local",
      workspaceCatalog: {
        currentWorkspaceId: "workspace-local",
        workspaces: [
          workspaceCatalogEntry("workspace-local", "Local Project", [
            {
              createdAt: "2026-06-09T00:00:00.000Z",
              id: "session-local",
              name: "Local session",
              projectId: "project-local",
              status: "new",
              updatedAt: "2026-06-09T00:00:00.000Z",
              workflowId: "workflow-local",
              workspaceId: "workspace-local",
            },
          ]),
          workspaceCatalogEntry("workspace-other", "Other Project", []),
        ],
      },
      workspaceRuntime: {
        bridge: {
          chooseWorkspace,
          getState: vi.fn(),
          useWorkspace: vi.fn(),
        },
        currentWorkspace: workspaceEntry("workspace-local", "Local Project"),
        isRequired: true,
      },
    });

    expect(screen.getByText("Local Project")).toBeInTheDocument();
    expect(screen.getByText("Other Project")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open or add workspace" }));

    expect(chooseWorkspace).toHaveBeenCalledTimes(1);
  });
});

function renderWorkbench(
  viewModel: MainPageViewModel,
  actions: MainPageController["actions"] = buildActions(),
  options: {
    activeWorkspaceId?: MainPageController["activeWorkspaceId"];
    workspaceCatalog?: WorkspaceCatalogResult | null;
    workspaceRuntime?: MainPageWorkspaceRuntime | null;
  } = {},
) {
  render(
    <MainPageWorkbench
      actions={actions}
      activeWorkspaceId={options.activeWorkspaceId ?? null}
      inputDraft=""
      inputError={null}
      inputRecoveryActions={[]}
      isCreatingSession={false}
      isDeletingSession={false}
      isRepairingAuthoringState={false}
      isRenamingSession={false}
      sessionDialog={{ mode: "idle" }}
      viewModel={viewModel}
      workspaceCatalog={options.workspaceCatalog ?? null}
      workspaceRuntime={options.workspaceRuntime ?? null}
    />,
  );
}

function workspaceCatalogEntry(
  workspaceId: string,
  label: string,
  recentSessions: WorkspaceCatalogResult["workspaces"][number]["recentSessions"],
): WorkspaceCatalogResult["workspaces"][number] {
  return {
    isCurrent: workspaceId === "workspace-local",
    label,
    recentSessions,
    sessionCount: recentSessions.length,
    status: "available",
    updatedAt: "2026-06-09T00:00:00.000Z",
    workspaceId,
  };
}

function workspaceEntry(
  id: string,
  name: string,
): PlatoWorkspaceEntrySummary {
  return {
    id,
    isCurrent: id === "workspace-local",
    label: name,
    name,
    pathLabel: "workspace://current",
  };
}

function buildViewModel(
  stateId: MainPageStateId,
  overrides: {
    selectedTaskNodeId?: TaskNodeId | null;
    snapshot?: MainPageSnapshot;
  } = {},
) {
  const { metadata, snapshot } = getMainPageMockSnapshot(stateId);

  return buildMainPageViewModel({
    auditRouteAvailable: true,
    authoringAskError: null,
    authoringAskRecoveryActions: [],
    confirmationError: null,
    confirmationRecoveryActions: [],
    detailOverride: "auto",
    eventConnectionStatus: "disconnected",
    eventError: null,
    isAnsweringAuthoringAsk: false,
    executionAskError: null,
    executionAskRecoveryActions: [],
    isAnsweringAsk: false,
    isCancellingAsk: false,
    isDeferringAsk: false,
    inputDisabled: false,
    isPublishingTaskTree: false,
    isRetryingTask: false,
    isStoppingTask: false,
    isResolvingConfirmation: false,
    metadata,
    selectedTaskNodeId: overrides.selectedTaskNodeId ?? null,
    snapshot: overrides.snapshot ?? snapshot,
    taskTreeCommandError: null,
    taskTreeCommandRecoveryActions: [],
    uiNotice: null,
  });
}

function buildActions(): MainPageController["actions"] {
  return {
    answerAsk: vi.fn(),
    answerAuthoringAskBatch: vi.fn(),
    cancelAsk: vi.fn(),
    cancelSessionDialog: vi.fn(),
    changeInputDraft: vi.fn(),
    changeSessionDialogDraft: vi.fn(),
    changeState: vi.fn(),
    createSession: vi.fn(),
    deferAsk: vi.fn(),
    deleteSession: vi.fn(),
    publishTaskTree: vi.fn(),
    repairAuthoringState: vi.fn(),
    renameSession: vi.fn(),
    resolveConfirmation: vi.fn(),
    retryTask: vi.fn(),
    selectSession: vi.fn(),
    selectTaskPlan: vi.fn(),
    selectTask: vi.fn(),
    showFileChanges: vi.fn(),
    showResult: vi.fn(),
    stopTask: vi.fn(),
    submitInput: vi.fn(),
    submitSessionDialog: vi.fn(),
  };
}
