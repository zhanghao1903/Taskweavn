import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { SessionMessageView, TaskNodeCardView } from "../../shared/api/types";
import { ActivityOverlay } from "./ActivityOverlay";

describe("ActivityOverlay", () => {
  it("opens on the current task filter and can switch to all activity", async () => {
    const user = userEvent.setup();

    render(
      <ActivityOverlay
        allMessages={[
          message({ id: "session-message", title: "Session update", taskNodeId: null }),
          message({
            id: "task-message",
            taskNodeId: "task-implementation",
            title: "Task update",
          }),
        ]}
        currentMessages={[
          message({
            id: "task-message",
            taskNodeId: "task-implementation",
            title: "Task update",
          }),
        ]}
        onClose={vi.fn()}
        selectedTask={taskNode}
      />,
    );

    const overlay = screen.getByLabelText("Activity overlay");

    expect(within(overlay).getByText("Task update")).toBeInTheDocument();
    expect(within(overlay).queryByText("Session update")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "All" }));

    expect(within(overlay).getByText("Session update")).toBeInTheDocument();
  });

  it("filters result and error activity", async () => {
    const user = userEvent.setup();

    render(
      <ActivityOverlay
        allMessages={[
          message({
            body: "Result summary is ready.",
            id: "result-message",
            title: "Result summary generated",
          }),
          message({
            body: "The action did not complete.",
            id: "error-message",
            kind: "error",
            title: "Action needs retry",
          }),
          message({ id: "other-message", title: "General update" }),
        ]}
        currentMessages={[]}
        onClose={vi.fn()}
        selectedTask={undefined}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Results" }));

    expect(screen.getByText("Result summary generated")).toBeInTheDocument();
    expect(screen.queryByText("Action needs retry")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Errors" }));

    expect(screen.getByText("Action needs retry")).toBeInTheDocument();
    expect(screen.queryByText("Result summary generated")).not.toBeInTheDocument();
  });

  it("opens result activity in a reader and returns to the timeline", async () => {
    const user = userEvent.setup();

    render(
      <ActivityOverlay
        allMessages={[
          message({
            body:
              "The completed result includes a long summary, implementation notes, and follow-up checks for review.",
            id: "result-message",
            title: "Result summary generated",
          }),
        ]}
        currentMessages={[]}
        onClose={vi.fn()}
        selectedTask={undefined}
      />,
    );

    await user.click(screen.getByRole("button", { name: "View full result" }));

    const reader = screen.getByLabelText("Full result");
    expect(within(reader).getByText("Full result")).toBeInTheDocument();
    expect(within(reader).getByText("Result summary generated")).toBeInTheDocument();
    expect(
      within(reader).getByText(/implementation notes, and follow-up checks/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Back to activity" }));

    expect(screen.queryByLabelText("Full result")).not.toBeInTheDocument();
    expect(screen.getByText("Result summary generated")).toBeInTheDocument();
  });

  it("notifies when the overlay closes", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <ActivityOverlay
        allMessages={[message()]}
        currentMessages={[message()]}
        onClose={onClose}
        selectedTask={taskNode}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

function message(
  overrides: Partial<SessionMessageView> = {},
): SessionMessageView {
  return {
    body: "Plato produced a first task breakdown for review.",
    createdAt: "2026-05-27T09:00:00Z",
    id: "message-draft-ready",
    kind: "informational",
    sessionId: "session-website-plan",
    taskNodeId: null,
    title: "Draft task tree ready",
    ...overrides,
  };
}

const taskNode: TaskNodeCardView = {
  id: "task-implementation",
  taskRef: {
    id: "task-implementation",
    kind: "published",
  },
  badges: {
    directFileChangeCount: 0,
    pendingConfirmationCount: 0,
    subtreeFileChangeCount: 0,
    unreadMessageCount: 0,
  },
  depth: 0,
  execution: "running",
  orderIndex: 1,
  parentId: null,
  permissions: {
    canAppendGuidance: true,
    canCancel: true,
    canEdit: false,
    canPublish: false,
    canResolveConfirmation: false,
    canRetry: false,
  },
  readiness: "published",
  status: "running",
  summary: "Build the first app shell.",
  title: "Initial implementation",
  version: 1,
};
