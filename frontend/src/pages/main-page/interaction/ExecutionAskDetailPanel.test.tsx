import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ExecutionAskDetailPanel } from "./ExecutionAskDetailPanel";
import type { MainPageDetailView } from "../mainPageViewModel";

type ExecutionAskDetail = Extract<
  MainPageDetailView,
  { kind: "executionAsk" }
>;

describe("ExecutionAskDetailPanel", () => {
  it("answers a concrete ASK with the selected option", async () => {
    const user = userEvent.setup();
    const onAnswer = vi.fn();

    render(
      <ExecutionAskDetailPanel
        detail={executionAskDetail()}
        onAnswer={onAnswer}
        onCancel={vi.fn()}
        onDefer={vi.fn()}
      />,
    );

    expect(screen.getByText("Task: Initial implementation")).toBeInTheDocument();
    expect(screen.getByText("Waiting")).toBeInTheDocument();
    expect(screen.queryByText("pending")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Cancel question" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Cancel ASK")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Vercel/ }));
    await user.click(screen.getByRole("button", { name: "Answer" }));

    expect(onAnswer).toHaveBeenCalledWith({
      selectedOptionIds: ["vercel"],
      text: null,
    });
  });

  it("answers a text-only ASK when free text is required", async () => {
    const user = userEvent.setup();
    const onAnswer = vi.fn();

    render(
      <ExecutionAskDetailPanel
        detail={executionAskDetail({
          ask: {
            ...executionAskDetail().ask,
            answerType: "free_text",
            allowFreeText: true,
            allowNoOptionWithText: true,
            suggestedOptions: [],
          },
        })}
        onAnswer={onAnswer}
        onCancel={vi.fn()}
        onDefer={vi.fn()}
      />,
    );

    await user.type(
      screen.getByLabelText("Answer text"),
      "Use the staging endpoint.",
    );
    await user.click(screen.getByRole("button", { name: "Answer" }));

    expect(onAnswer).toHaveBeenCalledWith({
      selectedOptionIds: [],
      text: "Use the staging endpoint.",
    });
  });

  it("ignores suggested options for free-text ASK answers", async () => {
    const user = userEvent.setup();
    const onAnswer = vi.fn();

    render(
      <ExecutionAskDetailPanel
        detail={executionAskDetail({
          ask: {
            ...executionAskDetail().ask,
            answerType: "free_text",
            allowFreeText: true,
            allowNoOptionWithText: true,
            suggestedOptions: [
              {
                id: "text",
                label: "TEXT",
                description: "Answer with text.",
              },
            ],
          },
        })}
        onAnswer={onAnswer}
        onCancel={vi.fn()}
        onDefer={vi.fn()}
      />,
    );

    expect(
      screen.queryByRole("button", { name: /TEXT/ }),
    ).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("Answer text"), "Use the default.");
    await user.click(screen.getByRole("button", { name: "Answer" }));

    expect(onAnswer).toHaveBeenCalledWith({
      selectedOptionIds: [],
      text: "Use the default.",
    });
  });

  it("submits batched execution ASK questions as one answer", async () => {
    const user = userEvent.setup();
    const onAnswer = vi.fn();

    render(
      <ExecutionAskDetailPanel
        detail={executionAskDetail({
          ask: {
            ...executionAskDetail().ask,
            question: "Portfolio planning details",
            questions: [
              {
                id: "role",
                question: "What is your professional role?",
                inputHint: "Designer, frontend engineer, product manager...",
                required: true,
              },
              {
                id: "goal",
                question: "What is the main goal of the portfolio?",
                inputHint: "Find a job, attract clients, build a brand...",
                required: true,
              },
            ],
            suggestedOptions: [],
            answerType: "free_text",
            allowFreeText: true,
            allowNoOptionWithText: true,
          },
        })}
        onAnswer={onAnswer}
        onCancel={vi.fn()}
        onDefer={vi.fn()}
      />,
    );

    const answerButton = screen.getByRole("button", { name: "Answer" });
    expect(answerButton).toBeDisabled();

    await user.type(
      screen.getByLabelText(/What is your professional role/),
      "Frontend engineer",
    );
    expect(answerButton).toBeDisabled();

    await user.type(
      screen.getByLabelText(/What is the main goal/),
      "Find product engineering roles",
    );
    await user.click(answerButton);

    expect(onAnswer).toHaveBeenCalledWith({
      selectedOptionIds: [],
      text:
        "Batch ASK answers:\n\n" +
        "1. What is your professional role?\n" +
        "Answer: Frontend engineer\n\n" +
        "2. What is the main goal of the portfolio?\n" +
        "Answer: Find product engineering roles",
    });
  });

  it("preserves local draft when a command error is shown", async () => {
    const user = userEvent.setup();

    render(
      <ExecutionAskDetailPanel
        detail={executionAskDetail({
          commandError: "Answer submission was rejected.",
        })}
        onAnswer={vi.fn()}
        onCancel={vi.fn()}
        onDefer={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Vercel/ }));

    expect(screen.getByRole("button", { name: /Vercel/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Answer submission was rejected.",
    );
  });

  it("disables controls while defer and cancel commands are pending", () => {
    const { rerender } = render(
      <ExecutionAskDetailPanel
        detail={executionAskDetail({ isDeferringAsk: true })}
        onAnswer={vi.fn()}
        onCancel={vi.fn()}
        onDefer={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Deferring" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Answer" })).toBeDisabled();

    rerender(
      <ExecutionAskDetailPanel
        detail={executionAskDetail({ isCancellingAsk: true })}
        onAnswer={vi.fn()}
        onCancel={vi.fn()}
        onDefer={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Cancelling" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Answer" })).toBeDisabled();
  });

  it("blocks stale ASK ids when the selected task does not match", () => {
    const onAnswer = vi.fn();
    const detail = executionAskDetail();

    render(
      <ExecutionAskDetailPanel
        detail={executionAskDetail({
          selectedTask: {
            ...detail.selectedTask!,
            id: "task-other",
          },
        })}
        onAnswer={onAnswer}
        onCancel={vi.fn()}
        onDefer={vi.fn()}
      />,
    );

    expect(screen.getByText(/question no longer matches/)).toBeInTheDocument();
    expect(screen.queryByText(/This ASK/)).not.toBeInTheDocument();
    expect(screen.queryByText(/TaskNode/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Answer" })).toBeDisabled();
  });
});

function executionAskDetail(
  overrides: Partial<ExecutionAskDetail> = {},
): ExecutionAskDetail {
  const detail: ExecutionAskDetail = {
    ask: {
      id: "ask-deployment-target",
      sessionId: "session-website-plan",
      taskNodeId: "task-implementation",
      taskRef: {
        kind: "published",
        id: "task-implementation",
      },
      question: "Where should the first deployment target point?",
      reason: "The task needs a deployment target before it can continue.",
      suggestedOptions: [
        {
          id: "vercel",
          label: "Vercel",
          description: "Use Vercel for the first deployment path.",
        },
        {
          id: "netlify",
          label: "Netlify",
          description: "Use Netlify for the first deployment path.",
        },
      ],
      answerType: "single_choice",
      allowFreeText: true,
      allowNoOptionWithText: false,
      blocking: true,
      attachmentsSupported: false,
      status: "pending",
      answerId: null,
      resumeHint: "Resume after answer.",
      createdAt: "2026-05-17T10:22:00+08:00",
      answeredAt: null,
      deferredAt: null,
      cancelledAt: null,
      expiredAt: null,
    },
    commandError: null,
    header: {
      body: "The task needs user input.",
      eyebrow: "Task input",
      title: "Initial implementation",
    },
    isAnsweringAsk: false,
    isCancellingAsk: false,
    isDeferringAsk: false,
    selectedTask: {
      id: "task-implementation",
      taskRef: {
        kind: "published",
        id: "task-implementation",
      },
      parentId: null,
      title: "Initial implementation",
      summary: "Build the first app shell.",
      status: "waiting_user",
      readiness: "published",
      execution: "waiting_for_user",
      confirmation: null,
      auditVerdict: "not_available",
      depth: 0,
      displayIndex: 1,
      orderIndex: 0,
      badges: {
        directFileChangeCount: 0,
        pendingConfirmationCount: 0,
        subtreeFileChangeCount: 0,
        unreadMessageCount: 0,
      },
      permissions: {
        canAppendGuidance: true,
        canCancel: false,
        canEdit: false,
        canPublish: false,
        canResolveConfirmation: false,
        canRetry: false,
      },
      readonlyReason: null,
      version: 1,
    },
    kind: "executionAsk",
  };

  return {
    ...detail,
    ...overrides,
  };
}
