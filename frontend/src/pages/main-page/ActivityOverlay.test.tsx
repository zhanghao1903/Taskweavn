import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { SessionMessageView, TaskNodeCardView } from "../../shared/api/types";
import { ActivityOverlay } from "./ActivityOverlay";
import styles from "./ActivityOverlay.module.css";

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

    const overlay = screen.getByLabelText("Task updates");

    expect(within(overlay).getByRole("heading", { name: "Task updates" }))
      .toBeInTheDocument();
    expect(
      within(overlay).getByText("Focused on Initial implementation."),
    ).toHaveClass(styles.headerDescription);
    expect(within(overlay).getByText("Task update")).toBeInTheDocument();
    expect(within(overlay).queryByText("Session update")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "All" }));

    expect(within(overlay).getByText("Session update")).toBeInTheDocument();
  });

  it("uses fixed-height, kind-colored message cards", () => {
    render(
      <ActivityOverlay
        allMessages={[
          message({
            id: "info-message",
            kind: "informational",
            title: "Task update",
          }),
          message({
            id: "action-message",
            kind: "actionable",
            title: "Needs confirmation",
          }),
          message({
            id: "result-message",
            kind: "response",
            title: "Task completed",
          }),
          message({
            id: "error-message",
            kind: "error",
            title: "Action needs retry",
          }),
        ]}
        currentMessages={[]}
        onClose={vi.fn()}
        selectedTask={undefined}
      />,
    );

    expect(screen.getByText("Task update").closest("li")).toHaveClass(
      styles.activityItemInformational,
    );
    expect(screen.getByText("Needs confirmation").closest("li")).toHaveClass(
      styles.activityItemActionable,
    );
    expect(screen.getByText("Task completed").closest("li")).toHaveClass(
      styles.activityItemResponse,
    );
    expect(screen.getByText("Action needs retry").closest("li")).toHaveClass(
      styles.activityItemError,
    );
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

  it("uses session activity copy when there is no selected task", async () => {
    const user = userEvent.setup();

    render(
      <ActivityOverlay
        allMessages={[message({ id: "general-update", title: "General update" })]}
        currentMessages={[]}
        onClose={vi.fn()}
        selectedTask={undefined}
      />,
    );

    const overlay = screen.getByLabelText("Session activity");
    expect(
      within(overlay).getByRole("heading", { name: "Session activity" }),
    ).toBeInTheDocument();
    expect(within(overlay).getByText("All session updates.")).toBeInTheDocument();
    expect(within(overlay).queryByText("Session-wide activity.")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Task updates")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Errors" }));

    expect(screen.getByText("No matching activity")).toBeInTheDocument();
    expect(
      screen.getByText("Try another filter or close this view."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Try another filter or return to the selected task."),
    ).not.toBeInTheDocument();
  });

  it("uses selected-task empty copy when focused activity is empty", () => {
    render(
      <ActivityOverlay
        allMessages={[message({ id: "session-update", title: "Session update" })]}
        currentMessages={[]}
        onClose={vi.fn()}
        selectedTask={taskNode}
      />,
    );

    expect(screen.getByText("No matching activity")).toBeInTheDocument();
    expect(
      screen.getByText("Try another filter or return to the selected task."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Try another filter or close this view."),
    ).not.toBeInTheDocument();
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
