import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import type { TaskNodeCardView } from "../../shared/api/types";
import { UiTextProvider } from "../../shared/ui-text";
import { MainPageDetailPanel } from "./MainPageDetailPanel";
import type { MainPageDetailView } from "./mainPageViewModel";

describe("MainPageDetailPanel", () => {
  it("shows whole-plan interaction details", () => {
    render(
      <MainPageDetailPanel
        detail={{
          header: {
            body: "Review the generated task plan before publishing.",
            eyebrow: "Draft task plan",
            title: "Review the generated structure",
          },
          kind: "plan",
          taskTree: {
            generatedAt: "2026-06-05T00:00:00.000Z",
            id: "task-tree-1",
            nodes: [
              taskNode({
                id: "task-one",
                summary: "Plan-level task.",
                title: "Task one",
              }),
            ],
            sessionId: "session-website-plan",
            status: "draft",
            title: "Personal website project plan",
            version: 1,
          },
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
      screen.getByRole("heading", { name: "Review the generated structure" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Plan interaction")).toBeInTheDocument();
    expect(screen.getByText("1 task")).toBeInTheDocument();
    expect(screen.queryByLabelText("Task actions")).not.toBeInTheDocument();
  });

  it("shows the full selected task content in the detail panel", () => {
    const title =
      "Choose the right technical stack and deployment approach for the content site";
    const summary =
      "Compare framework, hosting, build, routing, and operational tradeoffs before implementation begins.";
    const intent =
      "Select the platform stack before page implementation begins.";
    const instructions =
      "Evaluate React, routing, static hosting, deployment rollback, and local developer setup.";
    const acceptanceCriteria = [
      "A final framework decision is documented.",
      "A deployment target is selected.",
    ];

    render(
      <MainPageDetailPanel
        detail={{
          header: {
            body: summary,
            eyebrow: "Task",
            title,
          },
          isRetryingTask: false,
          isStoppingTask: false,
          kind: "task",
          selectedTask: taskNode({
            acceptanceCriteria,
            instructions,
            intent,
            summary,
            title,
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

    expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    expect(screen.getByText(summary)).toBeInTheDocument();
    expect(screen.getByLabelText("Task details")).toBeInTheDocument();
    expect(screen.getByText("Intent")).toBeInTheDocument();
    expect(screen.getByText(intent)).toBeInTheDocument();
    expect(screen.getByText("Instructions")).toBeInTheDocument();
    expect(screen.getByText(instructions)).toBeInTheDocument();
    expect(screen.getByText("Acceptance criteria")).toBeInTheDocument();
    expect(screen.getByText(acceptanceCriteria[0])).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Task actions" })).not.toBeInTheDocument();
    expect(screen.queryByText("TaskNode")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Input now applies/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Completed TaskNodes are read-only/i),
    ).not.toBeInTheDocument();
  });

  it("shows session token usage for draft selected tasks when a usage loader is available", async () => {
    const loadTokenUsageSummary = vi.fn(async () => ({
      dimension: "session" as const,
      totals: {
        dimension: "session" as const,
        id: "total",
        label: "Total",
        workspaceId: "workspace-a",
        sessionId: "session-1",
        planId: null,
        taskNodeId: null,
        callCount: 2,
        unknownUsageCallCount: 1,
        inputTokens: 1000,
        outputTokens: 250,
        totalTokens: null,
        reasoningTokens: null,
        cachedTokens: 400,
        cacheHitTokens: 400,
        cacheMissTokens: 600,
        cacheHitRatio: 0.4,
        cacheRateSource: "hit_miss_tokens" as const,
        firstOccurredAt: "2026-06-10T00:00:00Z",
        lastOccurredAt: "2026-06-10T00:01:00Z",
      },
      rows: [],
    }));

    renderWithQueryClient(
      <MainPageDetailPanel
        detail={{
          header: {
            body: "Compare framework options.",
            eyebrow: "Task",
            title: "Choose stack",
          },
          isRetryingTask: false,
          isStoppingTask: false,
          kind: "task",
          selectedTask: taskNode({
            id: "task-technical-stack",
            summary: "Compare framework options.",
            title: "Choose stack",
          }),
        }}
        loadTokenUsageSummary={loadTokenUsageSummary}
        onAnswerAsk={vi.fn()}
        onCancelAsk={vi.fn()}
        onConfirmationDecision={vi.fn()}
        onDeferAsk={vi.fn()}
        onRetryTask={vi.fn()}
        onShowFileChanges={vi.fn()}
        onShowResult={vi.fn()}
        onStopTask={vi.fn()}
        sessionId="session-1"
        workspaceId="workspace-a"
      />,
    );

    const usageLine = await screen.findByLabelText("Token usage");
    expect(usageLine).toHaveTextContent("Token usage");
    await waitFor(() => {
      expect(usageLine).toHaveTextContent("1,250");
    });
    expect(screen.queryByText("1,000 / 250")).not.toBeInTheDocument();
    expect(screen.queryByText("40.0%")).not.toBeInTheDocument();
    expect(loadTokenUsageSummary).toHaveBeenCalledWith(
      {
        dimension: "session",
        sessionId: "session-1",
      },
      "workspace-a",
    );
  });

  it("shows task token usage for published selected tasks when a usage loader is available", async () => {
    const loadTokenUsageSummary = vi.fn(async () => ({
      dimension: "task" as const,
      totals: {
        dimension: "task" as const,
        id: "total",
        label: "Total",
        workspaceId: "workspace-a",
        sessionId: "session-1",
        planId: "plan-1",
        taskNodeId: "task-technical-stack",
        callCount: 1,
        unknownUsageCallCount: 0,
        inputTokens: 700,
        outputTokens: 300,
        totalTokens: 1000,
        reasoningTokens: null,
        cachedTokens: null,
        cacheHitTokens: null,
        cacheMissTokens: null,
        cacheHitRatio: null,
        cacheRateSource: "unavailable" as const,
        firstOccurredAt: "2026-06-10T00:00:00Z",
        lastOccurredAt: "2026-06-10T00:01:00Z",
      },
      rows: [],
    }));

    renderWithQueryClient(
      <MainPageDetailPanel
        detail={{
          header: {
            body: "Compare framework options.",
            eyebrow: "Task",
            title: "Choose stack",
          },
          isRetryingTask: false,
          isStoppingTask: false,
          kind: "task",
          selectedTask: taskNode({
            id: "task-technical-stack",
            summary: "Compare framework options.",
            taskRef: {
              id: "task-technical-stack",
              kind: "published",
            },
            title: "Choose stack",
          }),
        }}
        loadTokenUsageSummary={loadTokenUsageSummary}
        onAnswerAsk={vi.fn()}
        onCancelAsk={vi.fn()}
        onConfirmationDecision={vi.fn()}
        onDeferAsk={vi.fn()}
        onRetryTask={vi.fn()}
        onShowFileChanges={vi.fn()}
        onShowResult={vi.fn()}
        onStopTask={vi.fn()}
        sessionId="session-1"
        workspaceId="workspace-a"
      />,
    );

    const usageLine = await screen.findByLabelText("Token usage");
    await waitFor(() => {
      expect(usageLine).toHaveTextContent("1,000");
    });
    expect(loadTokenUsageSummary).toHaveBeenCalledWith(
      {
        dimension: "task",
        sessionId: "session-1",
        taskNodeId: "task-technical-stack",
      },
      "workspace-a",
    );
  });

  it("shows a budget warning for high task token usage", async () => {
    const loadTokenUsageSummary = vi.fn(async () => ({
      dimension: "task" as const,
      totals: {
        dimension: "task" as const,
        id: "total",
        label: "Total",
        workspaceId: "workspace-a",
        sessionId: "session-1",
        planId: "plan-1",
        taskNodeId: "task-technical-stack",
        callCount: 12,
        unknownUsageCallCount: 0,
        inputTokens: 900000,
        outputTokens: 250000,
        totalTokens: 1150000,
        reasoningTokens: null,
        cachedTokens: null,
        cacheHitTokens: null,
        cacheMissTokens: null,
        cacheHitRatio: null,
        cacheRateSource: "unavailable" as const,
        firstOccurredAt: "2026-06-10T00:00:00Z",
        lastOccurredAt: "2026-06-10T00:01:00Z",
      },
      rows: [],
    }));

    renderWithQueryClient(
      <MainPageDetailPanel
        detail={{
          header: {
            body: "Compare framework options.",
            eyebrow: "Task",
            title: "Choose stack",
          },
          isRetryingTask: false,
          isStoppingTask: false,
          kind: "task",
          selectedTask: taskNode({
            id: "task-technical-stack",
            summary: "Compare framework options.",
            taskRef: {
              id: "task-technical-stack",
              kind: "published",
            },
            title: "Choose stack",
          }),
        }}
        loadTokenUsageSummary={loadTokenUsageSummary}
        onAnswerAsk={vi.fn()}
        onCancelAsk={vi.fn()}
        onConfirmationDecision={vi.fn()}
        onDeferAsk={vi.fn()}
        onRetryTask={vi.fn()}
        onShowFileChanges={vi.fn()}
        onShowResult={vi.fn()}
        onStopTask={vi.fn()}
        sessionId="session-1"
        workspaceId="workspace-a"
      />,
    );

    const budgetLine = await screen.findByLabelText("Budget");
    expect(budgetLine).toHaveTextContent("High usage");
    expect(budgetLine).toHaveAttribute(
      "title",
      "This scope has reached at least 1,000,000 tokens. Review usage before continuing long-running work.",
    );
  });

  it("hides stop for published selected tasks that are not running", () => {
    render(
      <MainPageDetailPanel
        detail={{
          header: {
            body: "The task is complete.",
            eyebrow: "Task",
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
        workspaceId="ws-a"
      />,
    );

    expect(screen.getByText("1 file")).toBeInTheDocument();
    expect(screen.getByText("Includes child tasks")).toBeInTheDocument();
    expect(screen.getByText("src/App.tsx")).toBeInTheDocument();
    expect(screen.queryByText("Updated page layout.")).not.toBeInTheDocument();
    expect(screen.queryByText("One file changed.")).not.toBeInTheDocument();
    expect(screen.queryByText("Recursive subtree summary")).not.toBeInTheDocument();
    expect(screen.queryByText(/Owner TaskNode/i)).not.toBeInTheDocument();
    expect(screen.queryByText("task-implementation")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open file" })).toHaveAttribute(
      "href",
      "/workspaces/ws-a/inspection?path=src%2FApp.tsx&returnFocus=file_change&returnSessionId=session-website-plan&returnTaskNodeId=task-implementation&sessionId=session-website-plan&taskNodeId=task-implementation&view=file",
    );
    expect(screen.getByRole("link", { name: "View diff" })).toHaveAttribute(
      "href",
      expect.stringContaining("view=diff"),
    );
  });

  it("renders file change details with zh-CN UI text", () => {
    render(
      <UiTextProvider locale="zh-CN">
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
          workspaceId="ws-a"
        />
      </UiTextProvider>,
    );

    expect(
      screen.getByRole("complementary", { name: "详情" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("变更文件")).toHaveLength(2);
    expect(screen.getByText("1 个文件")).toBeInTheDocument();
    expect(screen.getByText("包含子任务")).toBeInTheDocument();
    expect(screen.getByText("修改")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开文件" })).toHaveAttribute(
      "href",
      expect.stringContaining("view=file"),
    );
    expect(screen.getByRole("link", { name: "查看 Diff" })).toHaveAttribute(
      "href",
      expect.stringContaining("view=diff"),
    );
  });

  it("hides generic state notes instead of repeating them in the detail panel", () => {
    render(
      <MainPageDetailPanel
        detail={stateNoteDetail}
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
      screen.queryByRole("complementary", { name: "Details" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Describe the goal.")).not.toBeInTheDocument();
    expect(screen.queryByText("State note")).not.toBeInTheDocument();
  });

  it("uses task copy for resolved confirmation details", () => {
    render(
      <MainPageDetailPanel
        detail={{
          decision: "confirmed",
          header: {
            body: "The action was confirmed.",
            eyebrow: "Confirmation",
            title: "Action confirmed",
          },
          kind: "confirmationResolved",
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
      screen.getByText("The confirmation was accepted. Plato can continue from this task."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/TaskNode/)).not.toBeInTheDocument();
  });

  it("keeps result sections out of the default result card", () => {
    render(
      <MainPageDetailPanel
        detail={resultDetail}
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

    expect(screen.getByText("Result summary")).toBeInTheDocument();
    expect(screen.getByText(resultDetail.result.summary)).toBeInTheDocument();
    expect(screen.getByText("2 sections available.")).toBeInTheDocument();
    expect(screen.queryByText("Delivered structure")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "View full result" }),
    ).toBeInTheDocument();
  });

  it("renders result summary markdown through the shared renderer", async () => {
    const user = userEvent.setup();
    const detail: Extract<MainPageDetailView, { kind: "result" }> = {
      ...resultDetail,
      result: {
        ...resultDetail.result,
        summary: "## Done\n\n- **Verified:** build passed",
        sections: [
          {
            body: "`npm run build` completed.",
            kind: "text",
            title: "Verification",
          },
        ],
      },
    };

    render(
      <MainPageDetailPanel
        detail={detail}
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

    expect(screen.getByRole("heading", { name: "Done" })).toBeInTheDocument();
    expect(screen.getByText("Verified:").tagName).toBe("STRONG");

    await user.click(
      screen.getByRole("button", { name: "View full result" }),
    );

    const reader = screen.getByLabelText("Full result");
    expect(within(reader).getByText("npm run build").tagName).toBe("CODE");
  });

  it("shows workspace changes next to the result summary", () => {
    render(
      <MainPageDetailPanel
        detail={resultWithFileChangesDetail}
        onAnswerAsk={vi.fn()}
        onCancelAsk={vi.fn()}
        onConfirmationDecision={vi.fn()}
        onDeferAsk={vi.fn()}
        onRetryTask={vi.fn()}
        onShowFileChanges={vi.fn()}
        onShowResult={vi.fn()}
        onStopTask={vi.fn()}
        workspaceId="ws-a"
      />,
    );

    const workspaceChanges = screen.getByLabelText("Workspace changes");
    expect(within(workspaceChanges).getByText("1 file")).toBeInTheDocument();
    expect(within(workspaceChanges).getByText("src/App.tsx")).toBeInTheDocument();
    expect(within(workspaceChanges).getByRole("link", { name: "Open file" })).toHaveAttribute(
      "href",
      "/workspaces/ws-a/inspection?path=src%2FApp.tsx&returnFocus=file_change&returnSessionId=session-website-plan&returnTaskNodeId=task-implementation&sessionId=session-website-plan&taskNodeId=task-implementation&view=file",
    );
    expect(within(workspaceChanges).getByRole("link", { name: "View diff" })).toHaveAttribute(
      "href",
      expect.stringContaining("view=diff"),
    );
  });

  it("opens and closes the result reader for full structured content", async () => {
    const user = userEvent.setup();

    render(
      <MainPageDetailPanel
        detail={resultDetail}
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

    await user.click(
      screen.getByRole("button", { name: "View full result" }),
    );

    const reader = screen.getByLabelText("Full result");
    expect(within(reader).getByText("Full result")).toBeInTheDocument();
    expect(within(reader).getByText("Delivered structure")).toBeInTheDocument();
    expect(within(reader).getByText("Implementation checklist")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Back to summary" }));

    expect(screen.queryByLabelText("Full result")).not.toBeInTheDocument();
    expect(screen.getByText("Result summary")).toBeInTheDocument();
    expect(screen.queryByText("Delivered structure")).not.toBeInTheDocument();
  });

  it("labels long unstructured full results as a summary", async () => {
    const user = userEvent.setup();

    render(
      <MainPageDetailPanel
        detail={longSummaryResultDetail}
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

    expect(screen.getByText("Full result available.")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "View full result" }),
    );

    const reader = screen.getByLabelText("Full result");
    expect(within(reader).getByText("Summary")).toBeInTheDocument();
    expect(within(reader).queryByText("0 sections")).not.toBeInTheDocument();
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

const stateNoteDetail: MainPageDetailView = {
  kind: "note",
  body: "Describe the goal.",
  header: {
    body: "Describe the goal.",
    eyebrow: "Workspace",
    title: "Workspace session",
  },
};

const resultDetail: Extract<MainPageDetailView, { kind: "result" }> = {
  kind: "result",
  fileChangeSummary: null,
  header: {
    body: "Review the generated result.",
    eyebrow: "Result",
    title: "Result ready",
  },
  result: {
    id: "result-implementation",
    sessionId: "session-website-plan",
    taskNodeId: "task-implementation",
    title: "Implementation plan",
    summary:
      "The first implementation plan is ready, including page structure, styling direction, and build tasks.",
    sections: [
      {
        body: "A focused structure for the page, detail panel, and input bar.",
        kind: "text",
        title: "Delivered structure",
      },
      {
        body: "Review layout, visual direction, build, and verification tasks.",
        kind: "list",
        title: "Implementation checklist",
      },
    ],
    updatedAt: "2026-06-05T00:00:00.000Z",
  },
};

const resultWithFileChangesDetail: Extract<MainPageDetailView, { kind: "result" }> = {
  ...resultDetail,
  fileChangeSummary: fileChangesDetail.fileChangeSummary,
};

const longSummaryResultDetail: Extract<MainPageDetailView, { kind: "result" }> = {
  ...resultDetail,
  result: {
    ...resultDetail.result,
    summary:
      "Plato completed the review and produced a concise implementation outcome that explains what changed, why it matters, how the user can inspect it, and what follow-up checks should be done before accepting the work as complete.",
    sections: [],
  },
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
    displayIndex: 2,
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

function renderWithQueryClient(children: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>,
  );
}
