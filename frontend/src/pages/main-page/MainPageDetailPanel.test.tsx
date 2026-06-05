import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { TaskNodeCardView } from "../../shared/api/types";
import { MainPageDetailPanel } from "./MainPageDetailPanel";
import type { MainPageDetailView } from "./mainPageViewModel";

describe("MainPageDetailPanel", () => {
  it("shows the full selected task content in the detail panel", () => {
    const title =
      "Choose the right technical stack and deployment approach for the content site";
    const summary =
      "Compare framework, hosting, build, routing, and operational tradeoffs before implementation begins.";

    render(
      <MainPageDetailPanel
        detail={{
          header: {
            body: summary,
            eyebrow: "Task",
            title,
          },
          isRetryingTask: false,
          isStoppingTask: false,
          kind: "task",
          selectedTask: taskNode({ summary, title }),
        }}
        onAnswerAsk={vi.fn()}
        onCancelAsk={vi.fn()}
        onConfirmationDecision={vi.fn()}
        onDeferAsk={vi.fn()}
        onRetryTask={vi.fn()}
        onShowFileChanges={vi.fn()}
        onShowResult={vi.fn()}
        onStopTask={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    expect(screen.getByText(summary)).toBeInTheDocument();
    expect(screen.queryByText("Task details")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Task actions" })).not.toBeInTheDocument();
    expect(screen.queryByText("TaskNode")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Input now applies/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Completed TaskNodes are read-only/i),
    ).not.toBeInTheDocument();
  });

  it("hides stop for published selected tasks that are not running", () => {
    render(
      <MainPageDetailPanel
        detail={{
          header: {
            body: "The task is complete.",
            eyebrow: "Task",
            title: "Completed implementation",
          },
          isRetryingTask: false,
          isStoppingTask: false,
          kind: "task",
          selectedTask: taskNode({
            execution: "done",
            permissions: {
              canAppendGuidance: false,
              canCancel: true,
              canEdit: false,
              canPublish: false,
              canResolveConfirmation: false,
              canRetry: false,
            },
            summary: "Implementation is complete.",
            status: "done",
            taskRef: {
              id: "task-technical-stack",
              kind: "published",
            },
            title: "Completed implementation",
          }),
        }}
        onAnswerAsk={vi.fn()}
        onCancelAsk={vi.fn()}
        onConfirmationDecision={vi.fn()}
        onDeferAsk={vi.fn()}
        onRetryTask={vi.fn()}
        onShowFileChanges={vi.fn()}
        onShowResult={vi.fn()}
        onStopTask={vi.fn()}
      />,
    );

    expect(
      screen.queryByRole("button", { name: /^Stop$/i }),
    ).not.toBeInTheDocument();
  });

  it("hides raw owner TaskNode ids in file change details", () => {
    render(
      <MainPageDetailPanel
        detail={fileChangesDetail}
        onAnswerAsk={vi.fn()}
        onCancelAsk={vi.fn()}
        onConfirmationDecision={vi.fn()}
        onDeferAsk={vi.fn()}
        onRetryTask={vi.fn()}
        onShowFileChanges={vi.fn()}
        onShowResult={vi.fn()}
        onStopTask={vi.fn()}
      />,
    );

    expect(screen.getByText("1 file")).toBeInTheDocument();
    expect(screen.getByText("src/App.tsx")).toBeInTheDocument();
    expect(screen.queryByText("Updated page layout.")).not.toBeInTheDocument();
    expect(screen.queryByText("Recursive subtree summary")).not.toBeInTheDocument();
    expect(screen.queryByText(/Owner TaskNode/i)).not.toBeInTheDocument();
    expect(screen.queryByText("task-implementation")).not.toBeInTheDocument();
  });

  it("hides generic state notes instead of repeating them in the detail panel", () => {
    render(
      <MainPageDetailPanel
        detail={stateNoteDetail}
        onAnswerAsk={vi.fn()}
        onCancelAsk={vi.fn()}
        onConfirmationDecision={vi.fn()}
        onDeferAsk={vi.fn()}
        onRetryTask={vi.fn()}
        onShowFileChanges={vi.fn()}
        onShowResult={vi.fn()}
        onStopTask={vi.fn()}
      />,
    );

    expect(
      screen.queryByRole("complementary", { name: "Context inspector" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Describe the goal.")).not.toBeInTheDocument();
    expect(screen.queryByText("State note")).not.toBeInTheDocument();
  });

  it("uses task copy for resolved confirmation details", () => {
    render(
      <MainPageDetailPanel
        detail={{
          decision: "confirmed",
          header: {
            body: "The action was confirmed.",
            eyebrow: "Confirmation",
            title: "Action confirmed",
          },
          kind: "confirmationResolved",
        }}
        onAnswerAsk={vi.fn()}
        onCancelAsk={vi.fn()}
        onConfirmationDecision={vi.fn()}
        onDeferAsk={vi.fn()}
        onRetryTask={vi.fn()}
        onShowFileChanges={vi.fn()}
        onShowResult={vi.fn()}
        onStopTask={vi.fn()}
      />,
    );

    expect(
      screen.getByText("The confirmation was accepted. Plato can continue from this task."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/TaskNode/)).not.toBeInTheDocument();
  });

  it("keeps result sections out of the default result card", () => {
    render(
      <MainPageDetailPanel
        detail={resultDetail}
        onAnswerAsk={vi.fn()}
        onCancelAsk={vi.fn()}
        onConfirmationDecision={vi.fn()}
        onDeferAsk={vi.fn()}
        onRetryTask={vi.fn()}
        onShowFileChanges={vi.fn()}
        onShowResult={vi.fn()}
        onStopTask={vi.fn()}
      />,
    );

    expect(screen.getByText("Result summary")).toBeInTheDocument();
    expect(screen.getByText(resultDetail.result.summary)).toBeInTheDocument();
    expect(screen.getByText("2 sections available.")).toBeInTheDocument();
    expect(screen.queryByText("Delivered structure")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open reader" })).toBeInTheDocument();
  });

  it("opens and closes the result reader for full structured content", async () => {
    const user = userEvent.setup();

    render(
      <MainPageDetailPanel
        detail={resultDetail}
        onAnswerAsk={vi.fn()}
        onCancelAsk={vi.fn()}
        onConfirmationDecision={vi.fn()}
        onDeferAsk={vi.fn()}
        onRetryTask={vi.fn()}
        onShowFileChanges={vi.fn()}
        onShowResult={vi.fn()}
        onStopTask={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Open reader" }));

    const reader = screen.getByLabelText("Full result");
    expect(within(reader).getByText("Full result")).toBeInTheDocument();
    expect(within(reader).getByText("Delivered structure")).toBeInTheDocument();
    expect(within(reader).getByText("Implementation checklist")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Back to summary" }));

    expect(screen.queryByLabelText("Full result")).not.toBeInTheDocument();
    expect(screen.getByText("Result summary")).toBeInTheDocument();
    expect(screen.queryByText("Delivered structure")).not.toBeInTheDocument();
  });
});

const fileChangesDetail: MainPageDetailView = {
  kind: "fileChanges",
  fileChangeSummary: {
    changedFiles: [
      {
        changeType: "modified",
        ownerTaskNodeId: "task-implementation",
        path: "src/App.tsx",
        summary: "Updated page layout.",
      },
    ],
    recursive: true,
    sessionId: "session-website-plan",
    summary: "One file changed.",
    taskNodeId: "task-parent",
    updatedAt: "2026-06-05T00:00:00.000Z",
  },
  header: {
    body: "Review workspace changes.",
    eyebrow: "File Change Summary",
    title: "Files changed",
  },
  result: null,
};

const stateNoteDetail: MainPageDetailView = {
  kind: "note",
  body: "Describe the goal.",
  header: {
    body: "Describe the goal.",
    eyebrow: "Workflow",
    title: "Task authoring",
  },
};

const resultDetail: Extract<MainPageDetailView, { kind: "result" }> = {
  kind: "result",
  fileChangeSummary: null,
  header: {
    body: "Review the generated result.",
    eyebrow: "Result",
    title: "Result ready",
  },
  result: {
    id: "result-implementation",
    sessionId: "session-website-plan",
    taskNodeId: "task-implementation",
    title: "Implementation plan",
    summary:
      "The first implementation plan is ready, including page structure, styling direction, and build tasks.",
    sections: [
      {
        body: "A focused structure for the page, detail panel, and input bar.",
        kind: "text",
        title: "Delivered structure",
      },
      {
        body: "Review layout, visual direction, build, and verification tasks.",
        kind: "list",
        title: "Implementation checklist",
      },
    ],
    updatedAt: "2026-06-05T00:00:00.000Z",
  },
};

function taskNode(
  overrides: Partial<TaskNodeCardView> & Pick<TaskNodeCardView, "summary" | "title">,
): TaskNodeCardView {
  return {
    id: "task-technical-stack",
    taskRef: {
      id: "task-technical-stack",
      kind: "draft",
    },
    badges: {
      directFileChangeCount: 0,
      pendingConfirmationCount: 0,
      subtreeFileChangeCount: 0,
      unreadMessageCount: 0,
    },
    depth: 1,
    execution: "not_started",
    orderIndex: 1,
    parentId: null,
    permissions: {
      canAppendGuidance: true,
      canCancel: false,
      canEdit: true,
      canPublish: true,
      canResolveConfirmation: false,
      canRetry: false,
    },
    readiness: "draft",
    status: "draft",
    version: 1,
    ...overrides,
  };
}
