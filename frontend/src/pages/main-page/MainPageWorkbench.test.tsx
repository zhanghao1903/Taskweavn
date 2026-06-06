import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { TaskNodeId } from "../../shared/api/types";
import styles from "./MainPage.module.css";
import { MainPageWorkbench } from "./MainPageWorkbench";
import type { MainPageViewModel } from "./mainPageViewModel";
import { buildMainPageViewModel } from "./mainPageViewModel";
import type { MainPageStateId } from "./mockPlatoApi";
import { getMainPageMockSnapshot } from "./mockPlatoApi";
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
});

function renderWorkbench(viewModel: MainPageViewModel) {
  render(
    <MainPageWorkbench
      actions={buildActions()}
      inputDraft=""
      inputError={null}
      isCreatingSession={false}
      isDeletingSession={false}
      isRenamingSession={false}
      sessionDialog={{ mode: "idle" }}
      viewModel={viewModel}
    />,
  );
}

function buildViewModel(
  stateId: MainPageStateId,
  overrides: {
    selectedTaskNodeId?: TaskNodeId | null;
  } = {},
) {
  const { metadata, snapshot } = getMainPageMockSnapshot(stateId);

  return buildMainPageViewModel({
    auditRouteAvailable: true,
    authoringAskError: null,
    confirmationError: null,
    detailOverride: "auto",
    eventConnectionStatus: "disconnected",
    eventError: null,
    isAnsweringAuthoringAsk: false,
    executionAskError: null,
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
    snapshot,
    taskTreeCommandError: null,
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
