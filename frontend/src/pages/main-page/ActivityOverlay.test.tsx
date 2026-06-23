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

  it("keeps long activity content inside planned card slots", () => {
    render(
      <ActivityOverlay
        items={[
          activityItem({
            body:
              "A long activity body should use the body slot instead of adding arbitrary rows inside the fixed-height activity card. It may contain several sentences from execution output.",
            relatedRefs: [
              relatedRef("task", "task-implementation"),
              relatedRef("file", "chapter1_outline.md", {
                href: "/workspaces/ws-1/inspection?path=chapter1_outline.md&view=file",
              }),
            ],
            title:
              "A long task activity title should be constrained by the title slot and not push the footer out of the card",
          }),
        ]}
        onClose={vi.fn()}
        onOpenTask={vi.fn()}
        selectedTask={undefined}
      />,
    );

    const item = screen.getByRole("listitem");
    expect(within(item).getByText(/A long task activity title/)).toHaveClass(
      styles.itemTitle,
    );
    expect(within(item).getByText(/A long activity body/).closest("div"))
      .toHaveClass(styles.itemBody);
    const footer = item.querySelector(`.${styles.itemFooter}`);
    expect(footer).not.toBeNull();
    expect(within(footer as HTMLElement).getByLabelText("Evidence")).toHaveClass(
      styles.relatedRefs,
    );
  });

  it("renders activity preview markdown through the shared renderer", () => {
    render(
      <ActivityOverlay
        items={[
          activityItem({
            body: "**Why:** keep users informed\n\n- show next step",
            id: "markdown-activity",
            title: "Markdown activity",
          }),
        ]}
        onClose={vi.fn()}
        selectedTask={undefined}
      />,
    );

    const item = screen.getByText("Markdown activity").closest("li") as HTMLElement;
    expect(item).not.toBeNull();
    expect(within(item).getByText("Why:").tagName).toBe("STRONG");
    expect(within(item).getByText("show next step")).toBeInTheDocument();
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

  it("opens archived plan activity in a reader without selecting the active plan", async () => {
    const user = userEvent.setup();
    const onOpenPlan = vi.fn();

    render(
      <ActivityOverlay
        items={[
          activityItem({
            body:
              "**Stored plan**\n\nStored durable plan summary.\n\nTasks:\n- Task 1: Stored task (done)",
            id: "archived-plan-activity",
            kind: "plan_updated",
            relatedRefs: [],
            scopeKind: "plan",
            taskNodeId: null,
            title: "Plan archived",
          }),
        ]}
        onClose={vi.fn()}
        onOpenPlan={onOpenPlan}
        selectedTask={undefined}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Open plan" }));

    const reader = screen.getByLabelText("Plan details");
    expect(within(reader).getByText("Stored plan")).toBeInTheDocument();
    expect(within(reader).getByText(/Stored durable plan summary/)).toBeInTheDocument();
    expect(onOpenPlan).not.toHaveBeenCalled();
  });

  it("renders result reader markdown through the shared renderer", async () => {
    const user = userEvent.setup();

    render(
      <ActivityOverlay
        items={[
          activityItem({
            body: "## Result\n\n- **Done:** markdown rendered",
            id: "markdown-result",
            kind: "result_ready",
            title: "Markdown result",
          }),
        ]}
        onClose={vi.fn()}
        selectedTask={undefined}
      />,
    );

    await user.click(screen.getByRole("button", { name: "View full result" }));

    const reader = screen.getByLabelText("Full result");
    expect(
      within(reader).getByRole("heading", { name: "Result" }),
    ).toBeInTheDocument();
    expect(within(reader).getByText("Done:").tagName).toBe("STRONG");
  });

  it("exposes related ref actions for task, result, files, audit, and diagnostics", async () => {
    const user = userEvent.setup();
    const onOpenAudit = vi.fn();
    const onOpenDiagnostic = vi.fn();
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
              relatedRef("audit", "record-1"),
              relatedRef("diagnostic", "diagnostic:dirty_authoring_state"),
            ],
            taskNodeId: "task-implementation",
            title: "Files changed",
          }),
        ]}
        onClose={vi.fn()}
        onOpenAudit={onOpenAudit}
        onOpenDiagnostic={onOpenDiagnostic}
        onOpenFiles={onOpenFiles}
        onOpenResult={onOpenResult}
        onOpenTask={onOpenTask}
        selectedTask={undefined}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Open task" }));
    await user.click(screen.getByRole("button", { name: "Open result" }));
    await user.click(screen.getByRole("button", { name: "Open files" }));
    await user.click(screen.getByRole("button", { name: "Open audit" }));
    await user.click(screen.getByRole("button", { name: "Export diagnostics" }));

    expect(onOpenTask).toHaveBeenCalledWith("task-implementation");
    expect(onOpenResult).toHaveBeenCalledWith("task-implementation");
    expect(onOpenFiles).toHaveBeenCalledWith("task-implementation");
    expect(onOpenAudit).toHaveBeenCalledWith(
      expect.objectContaining({ id: "record-1", kind: "audit" }),
    );
    expect(onOpenDiagnostic).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "diagnostic:dirty_authoring_state",
        kind: "diagnostic",
      }),
    );
  });

  it("renders related ref hrefs as direct inspection links", () => {
    const onOpenFiles = vi.fn();
    const onOpenAudit = vi.fn();

    render(
      <ActivityOverlay
        items={[
          activityItem({
            relatedRefs: [
              relatedRef("file", "app.txt", {
                href: "/workspaces/workspace-1/inspection?path=app.txt&view=file",
              }),
              relatedRef("audit", "record-1", {
                href: "/sessions/session-1/audit?recordId=record-1",
              }),
            ],
            title: "Read-only answer",
          }),
        ]}
        onClose={vi.fn()}
        onOpenAudit={onOpenAudit}
        onOpenFiles={onOpenFiles}
        selectedTask={undefined}
      />,
    );

    expect(screen.getByRole("link", { name: "Open files" })).toHaveAttribute(
      "href",
      "/workspaces/workspace-1/inspection?path=app.txt&view=file",
    );
    expect(screen.getByRole("link", { name: "Open audit" })).toHaveAttribute(
      "href",
      "/sessions/session-1/audit?recordId=record-1",
    );
    expect(onOpenFiles).not.toHaveBeenCalled();
    expect(onOpenAudit).not.toHaveBeenCalled();
  });

  it("prefers Audit evidence focus links over parent Audit record links", () => {
    render(
      <ActivityOverlay
        items={[
          activityItem({
            relatedRefs: [
              relatedRef("audit", "record-1", {
                href: "/sessions/session-1/audit?recordId=record-1",
              }),
              relatedRef("audit", "evidence-record-1", {
                href: "/sessions/session-1/audit?recordId=record-1&evidenceId=evidence-record-1",
              }),
            ],
            title: "Read-only answer",
          }),
        ]}
        onClose={vi.fn()}
        selectedTask={undefined}
      />,
    );

    expect(screen.getByRole("link", { name: "Open audit" })).toHaveAttribute(
      "href",
      "/sessions/session-1/audit?recordId=record-1&evidenceId=evidence-record-1",
    );
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
  overrides: Partial<SessionActivityItemView["relatedRefs"][number]> = {},
): SessionActivityItemView["relatedRefs"][number] {
  return {
    id,
    kind,
    label: id,
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
