import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type {
  SessionActivityItemView,
  TaskNodeCardView,
} from "../../shared/api/types";
import { ActivityOverlay } from "./ActivityOverlay";
import styles from "./ActivityOverlay.module.css";

describe("ActivityOverlay", () => {
  it("opens on the current task filter and can switch to all activity", async () => {
    const user = userEvent.setup();

    render(
      <ActivityOverlay
        items={[
          activityItem({
            id: "session-activity",
            scopeKind: "session",
            taskNodeId: null,
            title: "Session update",
          }),
          activityItem({
            id: "task-activity",
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

  it("uses fixed-height, kind-colored activity cards", () => {
    render(
      <ActivityOverlay
        items={[
          activityItem({
            id: "info-activity",
            kind: "execution_update",
            title: "Task update",
          }),
          activityItem({
            id: "action-activity",
            kind: "confirmation_requested",
            title: "Needs confirmation",
          }),
          activityItem({
            id: "result-activity",
            kind: "answer",
            title: "Answer recorded",
          }),
          activityItem({
            id: "error-activity",
            kind: "recovery_note",
            title: "Action needs retry",
          }),
        ]}
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
    expect(screen.getByText("Answer recorded").closest("li")).toHaveClass(
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
        items={[
          activityItem({
            body: "Result summary is ready.",
            id: "result-activity",
            kind: "result_ready",
            title: "Result summary generated",
          }),
          activityItem({
            body: "The action did not complete.",
            id: "error-activity",
            kind: "recovery_note",
            title: "Action needs retry",
          }),
          activityItem({ id: "other-activity", title: "General update" }),
        ]}
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
        items={[activityItem({ id: "general-update", title: "General update" })]}
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
        items={[
          activityItem({
            id: "session-update",
            scopeKind: "session",
            taskNodeId: null,
            title: "Session update",
          }),
        ]}
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
        items={[
          activityItem({
            body:
              "The completed result includes a long summary, implementation notes, and follow-up checks for review.",
            id: "result-activity",
            kind: "result_ready",
            title: "Result summary generated",
          }),
        ]}
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

  it("exposes related ref actions for task, result, and files", async () => {
    const user = userEvent.setup();
    const onOpenFiles = vi.fn();
    const onOpenResult = vi.fn();
    const onOpenTask = vi.fn();

    render(
      <ActivityOverlay
        items={[
          activityItem({
            kind: "file_summary",
            relatedRefs: [
              relatedRef("task", "task-implementation"),
              relatedRef("result", "task-implementation"),
              relatedRef("file", "src/app.ts"),
            ],
            taskNodeId: "task-implementation",
            title: "Files changed",
          }),
        ]}
        onClose={vi.fn()}
        onOpenFiles={onOpenFiles}
        onOpenResult={onOpenResult}
        onOpenTask={onOpenTask}
        selectedTask={undefined}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Open task" }));
    await user.click(screen.getByRole("button", { name: "Open result" }));
    await user.click(screen.getByRole("button", { name: "Open files" }));

    expect(onOpenTask).toHaveBeenCalledWith("task-implementation");
    expect(onOpenResult).toHaveBeenCalledWith("task-implementation");
    expect(onOpenFiles).toHaveBeenCalledWith("task-implementation");
  });

  it("shows loading and error states with retry", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();

    const { rerender } = render(
      <ActivityOverlay
        isLoading
        items={[]}
        onClose={vi.fn()}
        selectedTask={undefined}
      />,
    );

    expect(screen.getByText("Loading activity")).toBeInTheDocument();

    rerender(
      <ActivityOverlay
        errorMessage="Network failed"
        items={[]}
        onClose={vi.fn()}
        onRetry={onRetry}
        selectedTask={undefined}
      />,
    );

    expect(screen.getByText("Network failed")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("notifies when the overlay closes", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <ActivityOverlay
        items={[activityItem()]}
        onClose={onClose}
        selectedTask={taskNode}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

function activityItem(
  overrides: Partial<SessionActivityItemView> = {},
): SessionActivityItemView {
  return {
    body: "Plato produced a first task breakdown for review.",
    disclosureLevel: "public",
    id: "activity-draft-ready",
    kind: "execution_update",
    occurredAt: "2026-05-27T09:00:00Z",
    planId: "plan-website",
    relatedRefs: [],
    scopeKind: "task",
    sessionId: "session-website-plan",
    sideEffect: "no_effect",
    sourceId: "message-draft-ready",
    sourceKind: "message_stream",
    taskNodeId: "task-implementation",
    title: "Draft task tree ready",
    ...overrides,
  };
}

function relatedRef(
  kind: SessionActivityItemView["relatedRefs"][number]["kind"],
  id: string,
): SessionActivityItemView["relatedRefs"][number] {
  return {
    id,
    kind,
    label: id,
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
  displayIndex: 1,
  orderIndex: 1,
  parentId: null,
  permissions: {
    canAppendGuidance: true,
    canCancel: false,
    canEdit: true,
    canPublish: true,
    canResolveConfirmation: false,
    canRetry: true,
  },
  status: "draft",
  summary: "Build the first backend integration.",
  title: "Initial implementation",
  version: 1,
};
