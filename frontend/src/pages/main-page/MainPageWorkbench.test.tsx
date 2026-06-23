import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  MainPageSnapshot,
  SessionActivityItemView,
  TaskNodeId,
} from "../../shared/api/types";
import type {
  DiagnosticBundleExportResult,
  WorkspaceCatalogResult,
} from "../../shared/api/platoApi";
import { writeWorkspaceGitInitializeOnOpenPreference } from "../../shared/workspace/workspaceGitPreference";
import styles from "./MainPage.module.css";
import { MainPageWorkbench } from "./MainPageWorkbench";
import type { MainPageViewModel } from "./mainPageViewModel";
import { buildMainPageViewModel } from "./mainPageViewModel";
import type { MainPageStateId } from "./mockPlatoApi";
import { getMainPageMockSnapshot } from "./mockPlatoApi";
import type { MainPageWorkspaceRuntime } from "./MainPageWorkspaceSwitcher";
import type {
  ExportDiagnosticBundle,
  LoadSessionActivity,
} from "./runtime/adapter";
import type { MainPageController } from "./useMainPageController";

describe("MainPageWorkbench layout", () => {
  beforeEach(() => {
    installTestLocalStorage();
  });

  afterEach(() => {
    globalThis.history.pushState(null, "", "/");
    globalThis.localStorage?.clear();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("expands the workspace when generic notes hide the detail panel", () => {
    const viewModel = buildViewModel("s1-empty");

    expect(viewModel.detail.kind).toBe("note");

    renderWorkbench(viewModel);

    expect(screen.getByRole("main")).toHaveClass(styles.pageWithoutDetail);
    expect(screen.getByLabelText("Conversation")).toBeInTheDocument();
    expect(
      screen.queryByRole("complementary", { name: "Details" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("separator", { name: "Resize details panel" }),
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
    expect(
      screen.getByRole("separator", { name: "Resize details panel" }),
    ).toBeInTheDocument();
  });

  it("resizes the detail pane with keyboard controls", () => {
    const viewModel = buildViewModel("s3-draft-ready");

    renderWorkbench(viewModel);

    const main = screen.getByRole("main");
    const splitter = screen.getByRole("separator", {
      name: "Resize details panel",
    });

    expect(splitter).toHaveAttribute("aria-valuenow", "380");
    expect(main).toHaveStyle({ "--plato-detail-width": "380px" });

    fireEvent.keyDown(splitter, { key: "ArrowLeft" });

    expect(splitter).toHaveAttribute("aria-valuenow", "404");
    expect(main).toHaveStyle({ "--plato-detail-width": "404px" });

    fireEvent.keyDown(splitter, { key: "Home" });

    expect(splitter).toHaveAttribute("aria-valuenow", "320");
    expect(main).toHaveStyle({ "--plato-detail-width": "320px" });
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

  it("expands the Plan & Progress layer when a task tree exists", () => {
    const viewModel = buildViewModel("s3-draft-ready");

    renderWorkbench(viewModel);

    expect(screen.getByLabelText("Plan & Progress workspace")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Collapse" })).toBeInTheDocument();
    expect(screen.getByLabelText("Conversation")).toBeInTheDocument();
    expect(screen.getByText("Requirement analysis")).toBeInTheDocument();
  });

  it("shows archive action for completed legacy plans", async () => {
    const user = userEvent.setup();
    const runtime = getMainPageMockSnapshot("s8-completed");
    const taskTree = runtime.snapshot.taskTree;

    expect(taskTree).not.toBeNull();

    const snapshot: MainPageSnapshot = {
      ...runtime.snapshot,
      activePlan: {
        id: `plan:legacy:${runtime.snapshot.session.id}`,
        sessionId: runtime.snapshot.session.id,
        title: taskTree!.title,
        summary: taskTree!.summary ?? taskTree!.title,
        objective: taskTree!.summary ?? taskTree!.title,
        status: "ready_for_review",
        taskCount: taskTree!.nodes.length,
        taskNodeIds: taskTree!.nodes.map((node) => node.id),
        taskNodes: taskTree!.nodes,
        executionRollup: taskTree!.executionRollup ?? {
          total: taskTree!.nodes.length,
          notStarted: 0,
          pending: 0,
          running: 0,
          done: taskTree!.nodes.length,
          failed: 0,
          cancelled: 0,
          unknown: 0,
          blockedByConfirmation: 0,
        },
        finalization: {
          status: "skipped",
          required: false,
          summaryRef: null,
          fileRollupRef: null,
          contextSummaryRef: null,
          warnings: [],
        },
        outcome: null,
        permissions: {
          canEdit: false,
          canPublish: false,
          canAppendGuidance: false,
          canCreateTaskNode: false,
          canDeleteTaskNode: false,
          canRequestExecution: false,
          readonlyReason: "Completed legacy plan.",
        },
        taskTreeProjection: taskTree,
        sourceKind: "legacy_published_task_tree",
        sourceRef: null,
        version: taskTree!.version,
      },
    };
    const actions = buildActions();
    const viewModel = buildViewModel("s8-completed", { snapshot });

    renderWorkbench(viewModel, actions);

    const archiveButton = screen.getByRole("button", { name: "Archive plan" });
    const auditLink = screen.getByRole("link", { name: "View audit" });

    expect(archiveButton.closest(`.${styles.actionRow}`)).toBe(
      auditLink.closest(`.${styles.actionRow}`),
    );

    await user.click(archiveButton);

    expect(actions.archivePlan).toHaveBeenCalledWith({
      expectedVersion: taskTree!.version,
      planId: `plan:legacy:${runtime.snapshot.session.id}`,
      sessionId: runtime.snapshot.session.id,
    });
  });

  it("collapses to Conversation and can reopen Plan & Progress", async () => {
    const user = userEvent.setup();
    const readOnlyAnswerActivity = activityItem({
      body: "The selected task is still a draft. No state changed.",
      id: "activity:inquiry:route-read-only-answer",
      kind: "answer",
      sourceKind: "router",
      taskNodeId: "task-visual-direction",
      title: "Read-only answer",
    });
    const viewModel = buildViewModel("s3-draft-ready", {
      selectedTaskNodeId: "task-visual-direction",
    });

    renderWorkbench(viewModel, buildActions(), {
      runtimeActivityItems: [readOnlyAnswerActivity],
    });

    await user.click(screen.getByRole("button", { name: "Collapse" }));

    const collapsedPlanButton = screen.getByRole("button", {
      name: "Open Plan & Progress: Personal website project plan",
    });

    expect(
      screen.queryByLabelText("Collapsed Plan & Progress"),
    ).not.toBeInTheDocument();
    expect(collapsedPlanButton).toBeInTheDocument();
    expect(screen.getByText("Personal website project plan")).toBeInTheDocument();
    expect(screen.getByLabelText("Conversation")).toBeInTheDocument();
    expect(screen.getAllByText("Read-only answer").length).toBeGreaterThan(0);
    expect(
      screen.getByText("The selected task is still a draft. No state changed."),
    ).toBeInTheDocument();

    await user.click(collapsedPlanButton);

    expect(screen.getByLabelText("Plan & Progress workspace")).toBeInTheDocument();
    expect(screen.getByText("Requirement analysis")).toBeInTheDocument();
  });

  it("shows Conversation without a Plan control for an empty session", () => {
    const viewModel = buildViewModel("s1-empty");

    renderWorkbench(viewModel);

    expect(screen.getByLabelText("Conversation")).toBeInTheDocument();
    expect(
      screen.queryByLabelText("Collapsed Plan & Progress"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("No conversation yet")).toBeInTheDocument();
  });

  it("opens session activity in the detail column when detail is otherwise hidden", async () => {
    const user = userEvent.setup();
    const loadSessionActivity = vi.fn<LoadSessionActivity>(async () => ({
      generatedAt: "2026-06-14T00:00:00.000Z",
      items: [
        activityItem({
          id: "activity-archived-plan",
          kind: "plan_updated",
          scopeKind: "plan",
          taskNodeId: null,
          title: "Plan archived",
        }),
      ],
      sessionId: "session-empty",
      totalCount: 1,
    }));
    const viewModel = buildViewModel("s1-empty");

    renderWorkbench(viewModel, buildActions(), { loadSessionActivity });

    const page = screen.getByRole("main");
    expect(page).toHaveClass(styles.pageWithoutDetail);

    await user.click(screen.getByRole("button", { name: "Activity 0" }));

    expect(page).not.toHaveClass(styles.pageWithoutDetail);
    expect(screen.getByRole("separator", { name: "Resize details panel" }))
      .toBeInTheDocument();
    expect(screen.getByLabelText("Session activity")).toBeInTheDocument();
    expect(screen.getByLabelText("Conversation")).toBeInTheDocument();
    expect(loadSessionActivity).toHaveBeenCalledWith(
      {
        limit: 100,
        sessionId: "session-website-plan",
      },
      null,
    );
  });

  it("shows read-only answer state in Conversation without adding task rows", () => {
    const viewModel = buildViewModel("s15-read-only-answer");

    renderWorkbench(viewModel);

    expect(screen.getByLabelText("Conversation")).toBeInTheDocument();
    expect(screen.getByText("Answer provided")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Run npm install once, then npm run dev from the frontend directory.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Update README startup commands"),
    ).not.toBeInTheDocument();
  });

  it("deduplicates transient runtime input after durable read-only messages arrive", () => {
    const { snapshot: baseSnapshot } = getMainPageMockSnapshot(
      "s15-read-only-answer",
    );
    const snapshot: MainPageSnapshot = {
      ...baseSnapshot,
      messages: baseSnapshot.messages.map((message) => ({
        ...message,
        kind:
          message.id === "message-read-only-answer"
            ? "informational"
            : message.kind,
        relatedCommandId: "route-input-1",
        title:
          message.id === "message-read-only-answer"
            ? "Read-only question answered"
            : "User input",
      })),
    };
    const transientUserInput = activityItem({
      body: "Which command starts the frontend locally?",
      id: "activity:runtime-input:route-input-1:user_input",
      kind: "user_input",
      occurredAt: "2026-05-17T10:23:00+08:00",
      planId: null,
      scopeKind: "session",
      sourceId: "route-input-1",
      sourceKind: "router",
      taskNodeId: null,
      title: "User input",
    });
    const transientAnswer = activityItem({
      body: "Run npm install once, then npm run dev from the frontend directory.",
      id: "activity:inquiry:route-input-1",
      kind: "answer",
      occurredAt: "2026-05-17T10:23:10+08:00",
      planId: null,
      scopeKind: "session",
      sourceId: "route-input-1",
      sourceKind: "router",
      taskNodeId: null,
      title: "Read-only answer",
    });
    const viewModel = buildViewModel("s15-read-only-answer", { snapshot });

    renderWorkbench(viewModel, buildActions(), {
      runtimeActivityItems: [transientUserInput, transientAnswer],
    });

    expect(
      screen.getAllByText("Which command starts the frontend locally?"),
    ).toHaveLength(1);
    expect(
      screen.getAllByText(
        "Run npm install once, then npm run dev from the frontend directory.",
      ),
    ).toHaveLength(1);
  });

  it("shows direct task state as a single runnable task", () => {
    const viewModel = buildViewModel("s16-direct-task");

    renderWorkbench(viewModel);

    expect(screen.getByLabelText("Plan & Progress workspace")).toBeInTheDocument();
    expect(screen.getAllByText("Update README startup commands").length).toBeGreaterThan(0);
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.queryByText("Requirement analysis")).not.toBeInTheDocument();
  });

  it("loads typed activity when the activity overlay opens", async () => {
    const user = userEvent.setup();
    const loadSessionActivity = vi.fn<LoadSessionActivity>(async () => ({
      generatedAt: "2026-06-14T00:00:00.000Z",
      items: [
        activityItem({
          id: "activity-plan-updated",
          kind: "plan_updated",
          taskNodeId: "task-visual-direction",
          title: "Plan updated",
        }),
      ],
      sessionId: "session-website-plan",
      totalCount: 1,
    }));
    const viewModel = buildViewModel("s3-draft-ready", {
      selectedTaskNodeId: "task-visual-direction",
    });

    renderWorkbench(viewModel, buildActions(), {
      loadSessionActivity,
    });

    await user.click(
      screen.getByRole("button", { name: /Open task updates/i }),
    );

    expect(loadSessionActivity.mock.calls[0]?.[0]).toEqual({
      limit: 100,
      sessionId: "session-website-plan",
    });
    expect(await screen.findAllByText("Plan updated")).toHaveLength(2);
  });

  it("shows transient read-only answer activity in the activity strip and overlay", async () => {
    const user = userEvent.setup();
    const readOnlyAnswerActivity = activityItem({
      body: "The selected task is still a draft. No state changed.",
      id: "activity:inquiry:route-read-only-answer",
      kind: "answer",
      sourceKind: "router",
      taskNodeId: "task-visual-direction",
      title: "Read-only answer",
    });
    const loadSessionActivity = vi.fn<LoadSessionActivity>(async () => ({
      generatedAt: "2026-06-14T00:00:00.000Z",
      items: [readOnlyAnswerActivity],
      sessionId: "session-website-plan",
      totalCount: 1,
    }));
    const viewModel = buildViewModel("s3-draft-ready", {
      selectedTaskNodeId: "task-visual-direction",
    });

    renderWorkbench(viewModel, buildActions(), {
      loadSessionActivity,
      runtimeActivityItems: [readOnlyAnswerActivity],
    });

    expect(screen.getAllByText("Read-only answer").length).toBeGreaterThan(0);

    await user.click(
      screen.getByRole("button", { name: /Open task updates/i }),
    );

    expect(loadSessionActivity).toHaveBeenCalledTimes(1);
    expect((await screen.findAllByText("Read-only answer")).length).toBeGreaterThanOrEqual(2);
    expect(
      screen.getAllByText("The selected task is still a draft. No state changed.")
        .length,
    ).toBeGreaterThan(0);
  });

  it("exports a redacted diagnostic bundle from diagnostic activity refs", async () => {
    const user = userEvent.setup();
    const diagnosticActivity = activityItem({
      body: "Diagnostic bundle export is available for this session.",
      id: "activity:inquiry:diagnostic",
      kind: "answer",
      relatedRefs: [
        {
          href: null,
          id: "diagnostic:bundle_export",
          kind: "diagnostic",
          label: "Diagnostic bundle export",
        },
      ],
      sourceKind: "router",
      taskNodeId: "task-visual-direction",
      title: "Diagnostic support",
    });
    const exportDiagnosticBundle = vi.fn<ExportDiagnosticBundle>(
      async () => diagnosticExport(),
    );
    const loadSessionActivity = vi.fn<LoadSessionActivity>(async () => ({
      generatedAt: "2026-06-14T00:00:00.000Z",
      items: [diagnosticActivity],
      sessionId: "session-website-plan",
      totalCount: 1,
    }));
    const viewModel = buildViewModel("s3-draft-ready", {
      selectedTaskNodeId: "task-visual-direction",
    });

    renderWorkbench(viewModel, buildActions(), {
      activeWorkspaceId: "workspace-local",
      exportDiagnosticBundle,
      loadSessionActivity,
      runtimeActivityItems: [diagnosticActivity],
    });

    await user.click(
      screen.getByRole("button", { name: /Open task updates/i }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Export diagnostics" }),
    );

    expect(exportDiagnosticBundle).toHaveBeenCalledWith(
      "session-website-plan",
      "workspace-local",
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Bundle ready: diagnostic-bundle-session-website-plan",
    );
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
    writeWorkspaceGitInitializeOnOpenPreference(true);
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
          getGitStatus: vi.fn(),
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

    expect(chooseWorkspace).toHaveBeenCalledWith({
      initializeGitOnOpen: true,
    });
  });

  it("opens workspace management from the sidebar first-level entry", async () => {
    const user = userEvent.setup();
    const viewModel = buildViewModel("s1-empty");

    renderWorkbench(viewModel, buildActions(), {
      activeWorkspaceId: "workspace-local",
      workspaceCatalog: {
        currentWorkspaceId: "workspace-local",
        workspaces: [
          workspaceCatalogEntry("workspace-local", "Local Project", []),
          workspaceCatalogEntry("workspace-other", "Other Project", []),
        ],
      },
      workspaceRuntime: {
        bridge: workspaceBridge(),
        currentWorkspace: workspaceEntry("workspace-local", "Local Project"),
        isRequired: true,
      },
    });

    await user.click(
      screen.getByRole("button", { name: "Workspace Management" }),
    );

    expect(globalThis.location.pathname).toBe("/settings");
    expect(globalThis.location.search).toContain("tab=data");
  });

  it("opens workspace archive and delete actions from a workspace line", async () => {
    const user = userEvent.setup();
    const archiveWorkspace = vi.fn(async () => workspaceLifecycleResult());
    const deleteWorkspaceData = vi.fn(async () => workspaceLifecycleResult());
    vi.stubGlobal("confirm", vi.fn(() => true));
    const viewModel = buildViewModel("s1-empty");

    renderWorkbench(viewModel, buildActions(), {
      activeWorkspaceId: "workspace-local",
      workspaceCatalog: {
        currentWorkspaceId: "workspace-local",
        workspaces: [
          workspaceCatalogEntry("workspace-local", "Local Project", []),
          workspaceCatalogEntry("workspace-other", "Other Project", []),
        ],
      },
      workspaceRuntime: {
        bridge: workspaceBridge({
          archiveWorkspace,
          deleteWorkspaceData,
        }),
        currentWorkspace: workspaceEntry("workspace-local", "Local Project"),
        isRequired: true,
      },
    });

    expect(
      screen.queryByRole("button", { name: "Open workspace actions" }),
    ).not.toBeInTheDocument();

    const otherWorkspaceLine = screen.getByText("Other Project").closest("div")!;
    fireEvent.contextMenu(otherWorkspaceLine);
    await user.click(screen.getByRole("menuitem", { name: "Archive workspace" }));
    expect(archiveWorkspace).toHaveBeenCalledWith("workspace-other");
    expect(screen.queryByText("Other Project")).not.toBeInTheDocument();

    const localWorkspaceLine = screen.getByText("Local Project").closest("div")!;
    fireEvent.contextMenu(localWorkspaceLine);
    await user.click(screen.getByRole("menuitem", { name: "Delete Plato data" }));

    expect(globalThis.confirm).toHaveBeenCalledWith(
      "Delete Plato data for Local Project? Project files and the workspace folder are kept.",
    );
    expect(deleteWorkspaceData).toHaveBeenCalledWith("workspace-local");
  });
});

function renderWorkbench(
  viewModel: MainPageViewModel,
  actions: MainPageController["actions"] = buildActions(),
  options: {
    activeWorkspaceId?: MainPageController["activeWorkspaceId"];
    exportDiagnosticBundle?: ExportDiagnosticBundle;
    loadSessionActivity?: LoadSessionActivity;
    runtimeActivityItems?: readonly SessionActivityItemView[];
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
      isArchivingPlan={false}
      isCreatingSession={false}
      isDeletingSession={false}
      isInputSubmitting={false}
      isRepairingAuthoringState={false}
      isRenamingSession={false}
      sessionDialog={{ mode: "idle" }}
      viewModel={viewModel}
      runtimeActivityItems={options.runtimeActivityItems}
      exportDiagnosticBundle={options.exportDiagnosticBundle}
      loadSessionActivity={options.loadSessionActivity}
      workspaceCatalog={options.workspaceCatalog ?? null}
      workspaceRuntime={options.workspaceRuntime ?? null}
    />,
  );
}

function activityItem(
  overrides: Partial<SessionActivityItemView> = {},
): SessionActivityItemView {
  return {
    body: "Typed activity loaded from the session activity projection.",
    disclosureLevel: "public",
    id: "activity-1",
    kind: "execution_update",
    occurredAt: "2026-06-14T00:00:00.000Z",
    planId: "plan-website",
    relatedRefs: [],
    scopeKind: "task",
    sessionId: "session-website-plan",
    sideEffect: "no_effect",
    sourceId: "source-1",
    sourceKind: "task_projection",
    taskNodeId: "task-visual-direction",
    title: "Activity loaded",
    ...overrides,
  };
}

function diagnosticExport(): DiagnosticBundleExportResult {
  return {
    bundleDir: "workspace://current/.plato/diagnostics/bundle",
    bundleDirLabel: "workspace://current/.plato/diagnostics/bundle",
    bundleId: "diagnostic-bundle-session-website-plan",
    createdAt: "2026-06-14T00:00:00.000Z",
    fileCount: 3,
    includedSections: ["manifest", "logs"],
    manifestPath: "workspace://current/.plato/diagnostics/manifest.json",
    manifestPathLabel: "workspace://current/.plato/diagnostics/manifest.json",
    redactionProfile: "product-default",
    schemaVersion: "plato.diagnostics_export.v1",
    sections: [],
    warnings: [],
    zipPath: "workspace://current/.plato/diagnostics/bundle.zip",
    zipPathLabel: "workspace://current/.plato/diagnostics/bundle.zip",
  };
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

function workspaceBridge(
  overrides: Partial<PlatoElectronWorkspaceBridge> = {},
): PlatoElectronWorkspaceBridge {
  return {
    chooseWorkspace: vi.fn(),
    getGitStatus: vi.fn(),
    getState: vi.fn(),
    useWorkspace: vi.fn(),
    ...overrides,
  };
}

function workspaceLifecycleResult(): PlatoWorkspaceLifecycleResult {
  return {
    state: {
      archivedWorkspaces: [],
      currentWorkspace: workspaceEntry("workspace-local", "Local Project"),
      error: null,
      recentWorkspaces: [],
      status: "ready",
    },
    status: "ok",
  };
}

function installTestLocalStorage(): void {
  const storage = new Map<string, string>();
  const storageLike = {
    clear: () => storage.clear(),
    getItem: (key: string) => storage.get(key) ?? null,
    key: (index: number) => Array.from(storage.keys())[index] ?? null,
    get length() {
      return storage.size;
    },
    removeItem: (key: string) => storage.delete(key),
    setItem: (key: string, value: string) => storage.set(key, value),
  };
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storageLike,
  });
  Object.defineProperty(globalThis.window, "localStorage", {
    configurable: true,
    value: storageLike,
  });
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
    archivePlan: vi.fn(),
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
