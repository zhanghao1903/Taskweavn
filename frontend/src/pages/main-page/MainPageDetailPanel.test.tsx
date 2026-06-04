import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { TaskNodeCardView } from "../../shared/api/types";
import { MainPageDetailPanel } from "./MainPageDetailPanel";

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
});

function taskNode(
  overrides: Pick<TaskNodeCardView, "summary" | "title">,
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
