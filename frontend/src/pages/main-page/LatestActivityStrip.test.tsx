import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { SessionMessageView, TaskNodeCardView } from "../../shared/api/types";
import { LatestActivityStrip } from "./LatestActivityStrip";

describe("LatestActivityStrip", () => {
  it("renders only the latest activity from the projected messages", () => {
    render(
      <LatestActivityStrip
        isMessageScoped={false}
        messages={[
          message({
            body: "Plato is preparing the TaskTree.",
            id: "message-1",
            title: "Planning started",
          }),
          message({
            body: "The implementation TaskNode is running.",
            id: "message-2",
            title: "Implementation started",
          }),
        ]}
        selectedTask={undefined}
        totalMessageCount={2}
        visibleMessageCount={2}
      />,
    );

    expect(screen.getByLabelText("Latest activity")).toBeInTheDocument();
    expect(screen.getByText("Implementation started")).toBeInTheDocument();
    expect(
      screen.queryByText("The implementation TaskNode is running."),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Planning started")).not.toBeInTheDocument();
    expect(screen.getByText("Activity 2")).toBeInTheDocument();
  });

  it("shows scoped activity counts when a TaskNode is selected", () => {
    render(
      <LatestActivityStrip
        isMessageScoped
        messages={[
          message({
            id: "message-1",
            taskNodeId: "task-implementation",
          }),
        ]}
        selectedTask={taskNode}
        totalMessageCount={3}
        visibleMessageCount={1}
      />,
    );

    expect(screen.getByText("Current task")).toBeInTheDocument();
    expect(screen.getByText("Activity 1/3")).toBeInTheDocument();
  });

  it("opens the activity overlay from the one-line strip", async () => {
    const user = userEvent.setup();
    const onOpenActivity = vi.fn();

    render(
      <LatestActivityStrip
        isMessageScoped={false}
        messages={[message()]}
        onOpenActivity={onOpenActivity}
        selectedTask={undefined}
        totalMessageCount={1}
        visibleMessageCount={1}
      />,
    );

    await user.click(
      screen.getByRole("button", {
        name: "Open activity overlay (Activity 1)",
      }),
    );

    expect(onOpenActivity).toHaveBeenCalledTimes(1);
  });

  it("does not reserve an empty message surface", () => {
    const { container } = render(
      <LatestActivityStrip
        isMessageScoped={false}
        messages={[]}
        selectedTask={undefined}
        totalMessageCount={0}
        visibleMessageCount={0}
      />,
    );

    expect(container).toBeEmptyDOMElement();
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
