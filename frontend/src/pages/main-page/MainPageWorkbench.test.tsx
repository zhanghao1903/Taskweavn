import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  MainPageSnapshot,
  PlanView,
  SessionActivityItemView,
  TaskNodeId,
} from "../../shared/api/types";
import type {
  DiagnosticBundleExportResult,
  ProductRecoveryAction,
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
import type { MainPageRouteFocusTarget } from "./runtime/mainPageFocusScrollRuntime";
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

  it("renders and answers Authoring ASK questions inside Conversation", async () => {
    const user = userEvent.setup();
    const actions = buildActions();
    const viewModel = buildViewModel("s2-understanding");

    expect(viewModel.mainWorkArea.kind).toBe("authoringAsk");

    renderWorkbench(viewModel, actions);

    expect(screen.getByLabelText("Conversation")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "What kind of website should Plato plan first?",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Submit all answers" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Portfolio" }));
    await user.click(screen.getByRole("button", { name: "Quiet editorial" }));
    await user.click(
      screen.getByRole("button", { name: "Submit all answers" }),
    );

    expect(actions.answerAuthoringAskBatch).toHaveBeenCalledWith({
      answers: [
        {
          askId: "authoring-ask-site-type",
          value: "portfolio",
        },
        {
          askId: "authoring-ask-style",
          value: "quiet_editorial",
        },
      ],
      rawTaskId: "raw-task-website-goal",
      sessionId: viewModel.sessionId,
    });
  });

  it("completes a partially answered Authoring ASK group without resubmitting its completed question", async () => {
    const user = userEvent.setup();
    const actions = buildActions();
    const runtime = getMainPageMockSnapshot("s2-understanding");
    const snapshot: MainPageSnapshot = {
      ...runtime.snapshot,
      planning: runtime.snapshot.planning
        ? {
            ...runtime.snapshot.planning,
            asks: runtime.snapshot.planning.asks.map((ask, index) => ({
              ...ask,
              status: index === 0 ? "answered" : ask.status,
            })),
          }
        : undefined,
      messages: runtime.snapshot.messages.map((message) => {
        const card = message.conversationRender?.askCard;
        if (
          message.conversationRender?.renderKind !== "ask_card" ||
          card?.domain !== "authoring"
        ) {
          return message;
        }
        return {
          ...message,
          conversationRender: {
            ...message.conversationRender,
            askCard: {
              ...card,
              questions: card.questions.map((question, index) => ({
                ...question,
                answered: index === 0,
                options: question.options.map((option) => ({
                  ...option,
                  selected: index === 0 && option.value === "portfolio",
                })),
              })),
            },
          },
        };
      }),
    };
    const viewModel = buildViewModel("s2-understanding", { snapshot });

    renderWorkbench(viewModel, actions);

    expect(
      screen.getByRole("button", { name: /Portfolio.*Selected/ }),
    ).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Quiet editorial" }));
    await user.click(
      screen.getByRole("button", { name: "Submit all answers" }),
    );

    expect(actions.answerAuthoringAskBatch).toHaveBeenCalledWith({
      answers: [
        {
          askId: "authoring-ask-style",
          value: "quiet_editorial",
        },
      ],
      rawTaskId: "raw-task-website-goal",
      sessionId: viewModel.sessionId,
    });
  });

  it("restores a pending ASK draft after switching sessions and returning", async () => {
    const user = userEvent.setup();
    const actions = buildActions();
    const authoringViewModel = buildViewModel("s2-understanding");
    const otherBase = buildViewModel("s1-empty");
    const otherViewModel: MainPageViewModel = {
      ...otherBase,
      sessionId: "session-other",
      sidebar: {
        ...otherBase.sidebar,
        activeSession: {
          ...otherBase.sidebar.activeSession,
          id: "session-other",
          name: "Other session",
        },
      },
    };
    const rendered = renderWorkbench(authoringViewModel, actions);

    await user.click(screen.getByRole("button", { name: "Portfolio" }));
    expect(
      screen.getByRole("button", { name: /Portfolio.*Selected/ }),
    ).toHaveAttribute("aria-pressed", "true");

    rendered.rerender(workbenchElement(otherViewModel, actions));
    expect(
      screen.queryByRole("heading", {
        name: "What kind of website should Plato plan first?",
      }),
    ).not.toBeInTheDocument();

    rendered.rerender(workbenchElement(authoringViewModel, actions));
    expect(
      screen.getByRole("button", { name: /Portfolio.*Selected/ }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("keeps Activity-only ASK events out of Conversation", () => {
    const runtime = getMainPageMockSnapshot("s1-empty");
    const snapshot: MainPageSnapshot = {
      ...runtime.snapshot,
      messages: [
        {
          id: "visible-message",
          sessionId: runtime.snapshot.session.id,
          taskNodeId: null,
          kind: "informational",
          title: "Visible update",
          body: "Visible in Conversation.",
          createdAt: "2026-07-24T10:00:00Z",
          conversationVisibility: "visible",
        },
        {
          id: "ask-answer-event",
          sessionId: runtime.snapshot.session.id,
          taskNodeId: null,
          kind: "informational",
          title: "ASK answered",
          body: "Retained only in Activity.",
          createdAt: "2026-07-24T10:01:00Z",
          conversationVisibility: "activity_only",
        },
      ],
    };

    renderWorkbench(buildViewModel("s1-empty", { snapshot }));

    expect(screen.getByText("Visible in Conversation.")).toBeInTheDocument();
    expect(
      screen.queryByText("Retained only in Activity."),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Activity 2" }),
    ).toBeInTheDocument();
  });

  it("routes helper recovery actions from the input error to Settings", async () => {
    const user = userEvent.setup();
    const viewModel = buildViewModel("s1-empty");

    renderWorkbench(viewModel, buildActions(), {
      inputError: "Computer-use helper needs Accessibility permission.",
      inputRecoveryActions: ["open_macos_privacy_accessibility", "edit_input"],
    });

    expect(
      screen.getByText("Computer-use helper needs Accessibility permission."),
    ).toBeInTheDocument();
    expect(screen.getByText("Edit input")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit input" }),
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Open Accessibility settings" }),
    );

    expect(globalThis.location.pathname).toBe("/settings");
  });

  it("returns focus to the composer after submitting runtime input", async () => {
    const user = userEvent.setup();
    const actions = buildActions();
    const viewModel = buildViewModel("s1-empty");

    renderWorkbench(viewModel, actions, {
      inputDraft: "Check whether this is finished.",
    });

    const input = screen.getByLabelText("Context message");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(actions.submitInput).toHaveBeenCalledWith({
      mode: viewModel.input.mode,
      sessionId: viewModel.sessionId,
      target: viewModel.input.target,
      taskNodeId: viewModel.input.taskNodeId,
    });
    expect(input).toHaveFocus();
  });

  it("focuses the selected task when returning from a route with task context", async () => {
    const viewModel = buildViewModel("s3-draft-ready", {
      selectedTaskNodeId: "task-visual-direction",
    });

    renderWorkbench(viewModel, buildActions(), {
      routeFocusTarget: "selected_task",
    });

    const selectedTaskButton = screen
      .getAllByText("Visual direction")
      .map((element) => element.closest("button"))
      .find((element): element is HTMLButtonElement => element !== null);

    expect(selectedTaskButton).not.toBeNull();
    await waitFor(() => expect(selectedTaskButton).toHaveFocus());
  });

  it("focuses the conversation when returning from a session-scoped route", async () => {
    const viewModel = buildViewModel("s8-completed");

    renderWorkbench(viewModel, buildActions(), {
      routeFocusTarget: "conversation",
    });

    await waitFor(() =>
      expect(screen.getByLabelText("Conversation")).toHaveFocus(),
    );
  });

  it("does not let consumed route-return focus steal composer focus after submit", async () => {
    const user = userEvent.setup();
    const actions = buildActions();
    const viewModel = buildViewModel("s1-empty");

    renderWorkbench(viewModel, actions, {
      inputDraft: "Follow up after route return.",
      routeFocusTarget: "conversation",
    });

    await waitFor(() =>
      expect(screen.getByLabelText("Conversation")).toHaveFocus(),
    );

    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(actions.submitInput).toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByLabelText("Context message")).toHaveFocus(),
    );
  });

  it("focuses file changes when returning from file or diff inspection", async () => {
    const actions = buildActions();
    const viewModel = buildViewModel("s9-file-changes");

    renderWorkbench(viewModel, actions, {
      routeFocusTarget: "file_changes",
    });

    expect(actions.showFileChanges).toHaveBeenCalled();

    const fileChangesPanel = screen.getByText("Changed files").closest("section");
    expect(fileChangesPanel).not.toBeNull();
    await waitFor(() => expect(fileChangesPanel).toHaveFocus());
  });

  it("moves focus into the execution ASK card when it is presented", async () => {
    const viewModel = buildViewModel("s14-execution-ask", {
      selectedTaskNodeId: "task-implementation",
    });

    renderWorkbench(viewModel);

    const askCard = document.querySelector<HTMLElement>(
      "[data-conversation-ask-id='ask-deployment-target']",
    );

    expect(askCard).not.toBeNull();
    await waitFor(() => {
      const activeElement = document.activeElement;
      expect(activeElement).toBeInstanceOf(HTMLElement);
      expect(askCard).toContainElement(activeElement as HTMLElement);
    });
  });

  it("answers an Execution ASK from its Conversation card", async () => {
    const user = userEvent.setup();
    const actions = buildActions();
    const viewModel = buildViewModel("s14-execution-ask", {
      selectedTaskNodeId: "task-implementation",
    });

    renderWorkbench(viewModel, actions);

    expect(
      screen.queryByLabelText("Plan & progress workspace"),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Vercel/ }));
    await user.click(screen.getByRole("button", { name: "Answer" }));

    expect(actions.answerAsk).toHaveBeenCalledWith({
      askId: "ask-deployment-target",
      selectedOptionIds: ["vercel"],
      sessionId: viewModel.sessionId,
      text: null,
    });
  });

  it("renders pending confirmations above the context input", async () => {
    const user = userEvent.setup();
    const actions = buildActions();
    const viewModel = buildViewModel("s7-confirmation", {
      selectedTaskNodeId: "task-visual-direction",
    });

    renderWorkbench(viewModel, actions);

    const dock = screen.getByRole("region", { name: "Pending confirmations" });
    const inputForm = screen.getByLabelText("Context message").closest("form");
    const firstOption = viewModel.pendingConfirmations[0]?.options[0];

    expect(inputForm).not.toBeNull();
    if (firstOption === undefined) {
      throw new Error("Expected pending confirmation option.");
    }
    expect(
      dock.compareDocumentPosition(inputForm!) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    await user.click(
      within(dock).getByRole("button", {
        name: `Quick decision: ${firstOption.label}`,
      }),
    );

    expect(actions.resolveConfirmation).toHaveBeenCalledWith({
      confirmation: viewModel.pendingConfirmations[0],
      decision: firstOption.value,
      sessionId: viewModel.sessionId,
    });
  });

  it("keeps dock confirmation actions disabled while a confirmation command is pending", () => {
    const viewModel = buildViewModel("s7-confirmation", {
      confirmationError: "Confirmation failed. Please retry.",
      isResolvingConfirmation: true,
      selectedTaskNodeId: null,
    });

    renderWorkbench(viewModel);

    const dock = screen.getByRole("region", { name: "Pending confirmations" });

    expect(
      within(dock).getByText("Confirmation failed. Please retry."),
    ).toBeInTheDocument();
    for (const option of viewModel.pendingConfirmations[0]?.options ?? []) {
      expect(
        within(dock).getByRole("button", {
          name: `Quick decision: ${option.label}`,
        }),
      ).toBeDisabled();
    }
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
    expect(
      screen.queryByRole("button", {
        name: "Open archived plan from Conversation",
      }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("No conversation yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View audit" })).toBeInTheDocument();
  });

  it("exposes archived plan and Audit entries from Conversation-only state", async () => {
    const user = userEvent.setup();
    const { snapshot } = getMainPageMockSnapshot("s15-read-only-answer");
    const archivedPlan = archivedPlanView(snapshot.session.id);
    const viewModel = buildViewModel("s15-read-only-answer", {
      snapshot: {
        ...snapshot,
        archivedPlans: [archivedPlan],
      },
    });

    renderWorkbench(viewModel);

    expect(screen.queryByLabelText("Plan & Progress workspace"))
      .not.toBeInTheDocument();

    const auditLink = screen.getByRole("link", { name: "View audit" });
    expect(auditLink).toHaveAttribute(
      "href",
      "/sessions/session-website-plan/audit?entry=from_session&returnFocus=session&returnSessionId=session-website-plan",
    );

    const planTrigger = screen.getByRole("button", {
      name: "Open archived plan from Conversation",
    });

    await user.click(planTrigger);

    const archivedPlansPanel = screen.getByLabelText("Archived Plans");
    expect(archivedPlansPanel).toBeInTheDocument();
    expect(screen.queryByLabelText("Session activity"))
      .not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Open plan" })).toHaveLength(1);
    expect(archivedPlansPanel.querySelector("time")).toHaveAttribute(
      "datetime",
      "2026-05-17T10:24:00+08:00",
    );

    await user.click(
      within(archivedPlansPanel).getByRole("button", { name: "Close" }),
    );

    await waitFor(() => expect(planTrigger).toHaveFocus());

    await user.click(planTrigger);

    await user.click(screen.getByRole("button", { name: "Open plan" }));

    const archivedWorkspace = screen.getByLabelText(
      "Archived Plan & Progress workspace",
    );
    expect(within(archivedWorkspace).getByText("Stored plan"))
      .toBeInTheDocument();
    expect(
      within(archivedWorkspace).getByText(/Stored durable plan summary/),
    ).toBeInTheDocument();
    expect(within(archivedWorkspace).getByText("Stored task"))
      .toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Details" }))
      .toBeInTheDocument();
    expect(
      within(screen.getByRole("complementary", { name: "Details" }))
        .getByRole("heading", { name: "Stored plan" }),
    ).toBeInTheDocument();

    const storedTaskButton = within(archivedWorkspace)
      .getByText("Stored task")
      .closest("button");
    if (storedTaskButton === null) {
      throw new Error("Expected archived task button.");
    }

    await user.click(storedTaskButton);

    const detailPanel = screen.getByRole("complementary", { name: "Details" });
    expect(
      within(detailPanel).getByRole("heading", { name: "Stored task" }),
    ).toBeInTheDocument();
    expect(
      within(detailPanel).getAllByText("Use stored PlanTaskNode."),
    ).toHaveLength(2);
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

  it("focuses selected activity and returns focus to the overlay trigger", async () => {
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

    renderWorkbench(viewModel, buildActions(), { loadSessionActivity });

    const activityTrigger = screen.getByRole("button", {
      name: /Open task updates/i,
    });

    await user.click(activityTrigger);

    await screen.findByLabelText("Task updates");
    await waitFor(() => {
      expect(document.activeElement).toHaveAttribute(
        "data-activity-item-id",
        "activity-plan-updated",
      );
    });

    await user.click(
      within(screen.getByRole("dialog", { name: "Task updates" })).getByRole(
        "button",
        { name: "Close" },
      ),
    );

    await waitFor(() => expect(activityTrigger).toHaveFocus());
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
    inputError?: string | null;
    inputRecoveryActions?: ProductRecoveryAction[];
    loadSessionActivity?: LoadSessionActivity;
    inputDraft?: string;
    isInputSubmitting?: boolean;
    runtimeActivityItems?: readonly SessionActivityItemView[];
    workspaceCatalog?: WorkspaceCatalogResult | null;
    workspaceRuntime?: MainPageWorkspaceRuntime | null;
    routeFocusTarget?: MainPageRouteFocusTarget | null;
  } = {},
) {
  return render(workbenchElement(viewModel, actions, options));
}

function workbenchElement(
  viewModel: MainPageViewModel,
  actions: MainPageController["actions"] = buildActions(),
  options: {
    activeWorkspaceId?: MainPageController["activeWorkspaceId"];
    exportDiagnosticBundle?: ExportDiagnosticBundle;
    inputError?: string | null;
    inputRecoveryActions?: ProductRecoveryAction[];
    loadSessionActivity?: LoadSessionActivity;
    inputDraft?: string;
    isInputSubmitting?: boolean;
    runtimeActivityItems?: readonly SessionActivityItemView[];
    workspaceCatalog?: WorkspaceCatalogResult | null;
    workspaceRuntime?: MainPageWorkspaceRuntime | null;
    routeFocusTarget?: MainPageRouteFocusTarget | null;
  } = {},
) {
  return (
    <MainPageWorkbench
      actions={actions}
      activeWorkspaceId={options.activeWorkspaceId ?? null}
      inputDraft={options.inputDraft ?? ""}
      inputError={options.inputError ?? null}
      inputRecoveryActions={options.inputRecoveryActions ?? []}
      isArchivingPlan={false}
      isCreatingSession={false}
      isDeletingSession={false}
      isInputSubmitting={options.isInputSubmitting ?? false}
      isRepairingAuthoringState={false}
      isRenamingSession={false}
      sessionDialog={{ mode: "idle" }}
      viewModel={viewModel}
      runtimeActivityItems={options.runtimeActivityItems}
      exportDiagnosticBundle={options.exportDiagnosticBundle}
      loadSessionActivity={options.loadSessionActivity}
      routeFocusTarget={options.routeFocusTarget}
      workspaceCatalog={options.workspaceCatalog ?? null}
      workspaceRuntime={options.workspaceRuntime ?? null}
    />
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

function archivedPlanView(sessionId: string): PlanView {
  const taskNode = {
    acceptanceCriteria: [],
    badges: {
      directFileChangeCount: 0,
      pendingConfirmationCount: 0,
      subtreeFileChangeCount: 0,
      unreadMessageCount: 0,
    },
    depth: 0,
    displayIndex: 1,
    execution: "done" as const,
    id: "node-stored",
    instructions: "Use stored PlanTaskNode.",
    intent: "Use stored PlanTaskNode.",
    interruptionRequested: false,
    orderIndex: 0,
    parentId: null,
    permissions: {
      canAppendGuidance: false,
      canCancel: false,
      canEdit: false,
      canPublish: false,
      canResolveConfirmation: false,
      canRetry: false,
    },
    planId: "plan-stored",
    resultRef: null,
    status: "done" as const,
    summary: "Stored task summary.",
    taskIndex: "1",
    taskRef: { id: "draft-stored", kind: "draft" as const },
    title: "Stored task",
    version: 1,
  };

  return {
    archivedAt: "2026-05-17T10:24:00+08:00",
    executionRollup: {
      blockedByConfirmation: 0,
      cancelled: 0,
      done: 1,
      failed: 0,
      notStarted: 0,
      pending: 0,
      running: 0,
      total: 1,
      unknown: 0,
    },
    finalization: {
      required: false,
      status: "done",
      warnings: [],
    },
    id: "plan-stored",
    objective: "Use durable plan facts.",
    outcome: null,
    permissions: {
      canAppendGuidance: false,
      canCreateTaskNode: false,
      canDeleteTaskNode: false,
      canEdit: false,
      canPublish: false,
      canRequestExecution: false,
    },
    sessionId,
    sourceKind: "plan_store",
    sourceRef: { id: "plan-stored", kind: "plan" },
    status: "cancelled",
    summary: "Stored durable plan summary.",
    taskCount: 1,
    taskNodeIds: ["node-stored"],
    taskNodes: [taskNode],
    taskTreeProjection: {
      id: "plan-stored",
      nodes: [taskNode],
      sessionId,
      status: "completed",
      summary: "Stored durable plan summary.",
      title: "Stored plan",
      version: 1,
    },
    title: "Stored plan",
    version: 1,
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
    confirmationError?: string | null;
    isResolvingConfirmation?: boolean;
    selectedTaskNodeId?: TaskNodeId | null;
    snapshot?: MainPageSnapshot;
  } = {},
) {
  const { metadata, snapshot } = getMainPageMockSnapshot(stateId);

  return buildMainPageViewModel({
    auditRouteAvailable: true,
    authoringAskError: null,
    authoringAskRecoveryActions: [],
    confirmationError: overrides.confirmationError ?? null,
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
    isResolvingConfirmation: overrides.isResolvingConfirmation ?? false,
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
