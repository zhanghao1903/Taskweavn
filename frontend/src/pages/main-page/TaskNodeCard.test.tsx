import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { TaskNodeCardView } from "../../shared/api/types";
import { TaskNodeCard } from "./TaskNodeCard";

describe("TaskNodeCard", () => {
  it("renders task content and emits the selected TaskNode id", async () => {
    const user = userEvent.setup();
    const onSelectTask = vi.fn();

    render(
      <TaskNodeCard
        isSelected={false}
        node={taskNode}
        onRetryTask={vi.fn()}
        onSelectTask={onSelectTask}
        onStopTask={vi.fn()}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: /Visual direction/i }),
    );

    expect(screen.getByText("Visual direction")).toBeInTheDocument();
    expect(screen.getByText("Fonts, color, and spacing")).toBeInTheDocument();
    expect(screen.getByText("waiting user")).toBeInTheDocument();
    expect(onSelectTask).toHaveBeenCalledWith("task-visual-direction");
  });

  it("renders retry as a separate task card action when allowed", async () => {
    const user = userEvent.setup();
    const onRetryTask = vi.fn();
    const onSelectTask = vi.fn();

    render(
      <TaskNodeCard
        isSelected
        node={{
          ...taskNode,
          permissions: {
            ...taskNode.permissions,
            canRetry: true,
          },
          status: "failed",
        }}
        onRetryTask={onRetryTask}
        onSelectTask={onSelectTask}
        onStopTask={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /^Retry$/i }));

    expect(onRetryTask).toHaveBeenCalledWith("task-visual-direction");
    expect(onSelectTask).not.toHaveBeenCalled();
  });

  it("renders stop as a separate task card action when allowed", async () => {
    const user = userEvent.setup();
    const onRetryTask = vi.fn();
    const onSelectTask = vi.fn();
    const onStopTask = vi.fn();

    render(
      <TaskNodeCard
        isSelected
        node={{
          ...taskNode,
          execution: "running",
          permissions: {
            ...taskNode.permissions,
            canCancel: true,
          },
          status: "running",
        }}
        onRetryTask={onRetryTask}
        onSelectTask={onSelectTask}
        onStopTask={onStopTask}
      />,
    );

    await user.click(screen.getByRole("button", { name: /^Stop$/i }));

    expect(onStopTask).toHaveBeenCalledWith("task-visual-direction");
    expect(onRetryTask).not.toHaveBeenCalled();
    expect(onSelectTask).not.toHaveBeenCalled();
  });
});

const taskNode: TaskNodeCardView = {
  id: "task-visual-direction",
  taskRef: {
    kind: "published",
    id: "task-visual-direction",
  },
  badges: {
    directFileChangeCount: 0,
    pendingConfirmationCount: 1,
    subtreeFileChangeCount: 0,
    unreadMessageCount: 0,
  },
  depth: 1,
  orderIndex: 3,
  parentId: "task-parent",
  permissions: {
    canAppendGuidance: true,
    canCancel: false,
    canEdit: true,
    canPublish: false,
    canResolveConfirmation: true,
    canRetry: false,
  },
  status: "waiting_user",
  summary: "Fonts, color, and spacing",
  title: "Visual direction",
  version: 1,
};
