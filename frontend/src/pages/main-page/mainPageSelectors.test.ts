import { describe, expect, it } from "vitest";

import type {
  FileChangeSummaryView,
  ResultCardView,
  SessionMessageView,
  TaskNodeCardView,
} from "../../shared/api/types";
import { enUS, zhCN } from "../../shared/ui-text";
import {
  buildTaskScopedProjection,
  isTaskNodeInScope,
  selectAuditSummaryPresentation,
  selectAuditVerdictPresentation,
  selectConfirmationOptionVariant,
  selectEventConnectionStatusPresentation,
  selectFileChangeTypePresentation,
  selectMessageKindPresentation,
  selectMainPagePrimaryStatusPresentation,
  selectSessionStatusPresentation,
  selectTaskNodeDimensionPresentation,
  selectTaskNodeStatusPresentation,
} from "./mainPageSelectors";
import { getMainPageMockSnapshot } from "./mockPlatoApi";

describe("main page selectors", () => {
  it("keeps the full projection when no TaskNode is selected", () => {
    const messages = [
      message("message-session", null),
      message("message-child", "task-child"),
    ];
    const result = resultCard("task-child");
    const fileChangeSummary = fileSummary("task-child");

    const projection = buildTaskScopedProjection({
      fileChangeSummary,
      messages,
      nodes: taskNodes,
      result,
      selectedTaskNodeId: null,
    });

    expect(projection.selectedTask).toBeUndefined();
    expect(projection.messages).toBe(messages);
    expect(projection.result).toBe(result);
    expect(projection.fileChangeSummary).toBe(fileChangeSummary);
    expect(projection.isMessageScoped).toBe(false);
  });

  it("includes session-wide and subtree messages for the selected TaskNode", () => {
    const projection = buildTaskScopedProjection({
      fileChangeSummary: null,
      messages: [
        message("message-session", null),
        message("message-parent", "task-parent"),
        message("message-child", "task-child"),
        message("message-sibling", "task-sibling"),
      ],
      nodes: taskNodes,
      result: null,
      selectedTaskNodeId: "task-parent",
    });

    expect(projection.messages.map((item) => item.id)).toEqual([
      "message-session",
      "message-parent",
      "message-child",
    ]);
    expect(projection.isMessageScoped).toBe(true);
    expect(projection.visibleMessageCount).toBe(3);
    expect(projection.totalMessageCount).toBe(4);
  });

  it("hides result cards outside the selected TaskNode subtree", () => {
    const result = resultCard("task-child");

    expect(
      buildTaskScopedProjection({
        fileChangeSummary: null,
        messages: [],
        nodes: taskNodes,
        result,
        selectedTaskNodeId: "task-parent",
      }).result,
    ).toBe(result);

    expect(
      buildTaskScopedProjection({
        fileChangeSummary: null,
        messages: [],
        nodes: taskNodes,
        result,
        selectedTaskNodeId: "task-sibling",
      }).result,
    ).toBeNull();
  });

  it("aggregates file changes from the selected TaskNode subtree", () => {
    const projection = buildTaskScopedProjection({
      fileChangeSummary: {
        ...fileSummary("task-child"),
        changedFiles: [
          fileChange("src/child.ts", "task-child"),
          fileChange("src/sibling.ts", "task-sibling"),
        ],
      },
      messages: [],
      nodes: taskNodes,
      result: null,
      selectedTaskNodeId: "task-parent",
    });

    expect(projection.fileChangeSummary).toMatchObject({
      taskNodeId: "task-parent",
      recursive: true,
      summary:
        "Recursive summary: 1 files changed in the selected task and its children.",
    });
    expect(projection.fileChangeSummary?.changedFiles).toEqual([
      expect.objectContaining({ path: "src/child.ts" }),
    ]);
  });

  it("guards against cyclic parent links while checking scope", () => {
    const cyclicNodes = [
      taskNode("task-a", "task-c"),
      taskNode("task-b", "task-a"),
      taskNode("task-c", "task-b"),
    ];

    expect(isTaskNodeInScope("task-x", "task-a", cyclicNodes)).toBe(false);
  });

  it("centralizes session and task status badge presentation", () => {
    expect(selectSessionStatusPresentation("waiting_user")).toEqual({
      label: "Waiting for user",
      tone: "warning",
    });
    expect(selectSessionStatusPresentation("completed")).toEqual({
      label: "Completed",
      tone: "success",
    });
    expect(selectTaskNodeStatusPresentation("waiting_user")).toEqual({
      label: "Waiting",
      tone: "warning",
    });
    expect(selectTaskNodeStatusPresentation("failed")).toEqual({
      label: "Failed",
      tone: "danger",
    });
  });

  it("derives TaskNode badges from canonical dimensions before flat status fallback", () => {
    expect(
      selectTaskNodeDimensionPresentation({
        ...taskNode("task-waiting", null),
        confirmation: "pending",
        execution: "running",
        readiness: "published",
        status: "running",
      }),
    ).toEqual({
      label: "Waiting",
      tone: "warning",
    });

    expect(
      selectTaskNodeDimensionPresentation({
        ...taskNode("task-done", null),
        confirmation: null,
        execution: "done",
        readiness: "published",
        status: "waiting_user",
      }),
    ).toEqual({
      label: "Done",
      tone: "success",
    });

    expect(
      selectTaskNodeDimensionPresentation({
        ...taskNode("task-legacy", null),
        status: "waiting_user",
      }),
    ).toEqual({
      label: "Waiting",
      tone: "warning",
    });
  });

  it("derives page status from canonical dimensions and permission state", () => {
    const confirmationState = getMainPageMockSnapshot("s7-confirmation");
    expect(
      selectMainPagePrimaryStatusPresentation(
        confirmationState.snapshot,
        confirmationState.metadata,
      ),
    ).toEqual({
      label: "Waiting for user",
      tone: "warning",
    });

    const staleState = getMainPageMockSnapshot("s11-stale-snapshot");
    expect(
      selectMainPagePrimaryStatusPresentation(
        staleState.snapshot,
        staleState.metadata,
      ),
    ).toEqual({
      label: "Stale",
      tone: "warning",
    });

    const runningState = getMainPageMockSnapshot("s6-running");
    const runningTaskTree = runningState.snapshot.taskTree;
    if (runningTaskTree === null || runningTaskTree.executionRollup == null) {
      throw new Error("Expected s6-running to include a TaskTree execution rollup.");
    }
    const runningSnapshot = {
      ...runningState.snapshot,
      pendingConfirmations: [],
      taskTree: {
        ...runningTaskTree,
        executionRollup: {
          ...runningTaskTree.executionRollup,
          blockedByConfirmation: 0,
        },
      },
    };
    expect(
      selectMainPagePrimaryStatusPresentation(
        runningSnapshot,
        runningState.metadata,
        enUS.main,
      ),
    ).toEqual({
      label: "Executing",
      tone: "blue",
    });
    expect(
      selectMainPagePrimaryStatusPresentation(
        runningSnapshot,
        runningState.metadata,
        zhCN.main,
      ),
    ).toEqual({
      label: "执行中",
      tone: "blue",
    });
  });

  it("centralizes auxiliary badge and action presentation", () => {
    expect(selectMessageKindPresentation("actionable")).toEqual({
      label: "Needs reply",
      tone: "warning",
    });
    expect(selectMessageKindPresentation("error")).toEqual({
      label: "Error",
      tone: "danger",
    });
    expect(selectEventConnectionStatusPresentation("resyncing")).toEqual({
      label: "Resyncing",
      tone: "warning",
    });
    expect(selectFileChangeTypePresentation("renamed")).toEqual({
      label: "Renamed",
      tone: "blue",
    });
    expect(selectFileChangeTypePresentation("created")).toEqual({
      label: "Created",
      tone: "success",
    });
    expect(selectFileChangeTypePresentation("modified")).toEqual({
      label: "Modified",
      tone: "warning",
    });
    expect(selectConfirmationOptionVariant("danger")).toBe("danger");
    expect(selectConfirmationOptionVariant("secondary")).toBe("secondary");
  });

  it("centralizes audit verdict presentation for Main Page audit affordances", () => {
    expect(selectAuditVerdictPresentation("not_available")).toEqual({
      label: "Not available",
      tone: "neutral",
    });
    expect(selectAuditVerdictPresentation("warning")).toEqual({
      label: "Warning",
      tone: "warning",
    });
    expect(selectAuditSummaryPresentation(null)).toEqual({
      label: "Not available",
      tone: "neutral",
    });
  });
});

const taskNodes = [
  taskNode("task-parent", null),
  taskNode("task-child", "task-parent"),
  taskNode("task-sibling", null),
];

function taskNode(
  id: string,
  parentId: string | null,
): TaskNodeCardView {
  return {
    id,
    badges: {
      directFileChangeCount: 0,
      pendingConfirmationCount: 0,
      subtreeFileChangeCount: 0,
      unreadMessageCount: 0,
    },
    depth: parentId ? 1 : 0,
    displayIndex: 1,
    orderIndex: 0,
    parentId,
    permissions: {
      canAppendGuidance: true,
      canCancel: false,
      canEdit: true,
      canPublish: false,
      canResolveConfirmation: false,
      canRetry: false,
    },
    status: "queued",
    summary: `${id} summary`,
    title: id,
    version: 1,
  };
}

function message(
  id: string,
  taskNodeId: string | null,
): SessionMessageView {
  return {
    id,
    body: `${id} body`,
    createdAt: "2026-05-17T10:00:00+08:00",
    kind: "informational",
    sessionId: "session-test",
    taskNodeId,
    title: id,
  };
}

function resultCard(taskNodeId: string): ResultCardView {
  return {
    id: "result-test",
    sessionId: "session-test",
    summary: "Result summary",
    taskNodeId,
    title: "Result",
    updatedAt: "2026-05-17T10:00:00+08:00",
  };
}

function fileSummary(taskNodeId: string): FileChangeSummaryView {
  return {
    changedFiles: [fileChange("src/file.ts", taskNodeId)],
    recursive: true,
    sessionId: "session-test",
    summary: "1 file changed.",
    taskNodeId,
    updatedAt: "2026-05-17T10:00:00+08:00",
  };
}

function fileChange(path: string, ownerTaskNodeId: string) {
  return {
    changeType: "modified" as const,
    ownerTaskNodeId,
    path,
    summary: `${path} changed`,
  };
}
