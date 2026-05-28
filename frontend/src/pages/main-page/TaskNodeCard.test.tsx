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
        onSelectTask={onSelectTask}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Visual direction/i }));

    expect(screen.getByText("Visual direction")).toBeInTheDocument();
    expect(screen.getByText("Fonts, color, and spacing")).toBeInTheDocument();
    expect(screen.getByText("waiting user")).toBeInTheDocument();
    expect(onSelectTask).toHaveBeenCalledWith("task-visual-direction");
  });
});

const taskNode: TaskNodeCardView = {
  id: "task-visual-direction",
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
