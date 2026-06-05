import { render, screen, within } from "@testing-library/react";
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
            eyebrow: "TaskNode",
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

    const detailPanel = screen.getByRole("region", {
      name: "Selected task details",
    });

    expect(within(detailPanel).getByText("Task details")).toBeInTheDocument();
    expect(within(detailPanel).getByText(title)).toBeInTheDocument();
    expect(within(detailPanel).getByText(summary)).toBeInTheDocument();
  });

  it("hides stop for published selected tasks that are not running", () => {
    render(
      <MainPageDetailPanel
        detail={{
          header: {
            body: "The task is complete.",
            eyebrow: "TaskNode",
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

    expect(screen.getByText("src/App.tsx")).toBeInTheDocument();
    expect(screen.getByText("Updated page layout.")).toBeInTheDocument();
    expect(screen.queryByText(/Owner TaskNode/i)).not.toBeInTheDocument();
    expect(screen.queryByText("task-implementation")).not.toBeInTheDocument();
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
