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

  it("preserves local draft when a command error is shown", async () => {
    const user = userEvent.setup();

    render(
      <ExecutionAskDetailPanel
        detail={executionAskDetail({
          commandError: "ASK answer command was rejected.",
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
      "ASK answer command was rejected.",
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

    expect(screen.getByText(/no longer matches/)).toBeInTheDocument();
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
      eyebrow: "Execution ASK",
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
