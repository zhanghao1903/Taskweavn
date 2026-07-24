import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ConversationAskCardView } from "../../../shared/api/types";
import { ConversationAskCard } from "./ConversationAskCard";
import type { ConversationAskInteraction } from "./conversationAskInteraction";

describe("ConversationAskCard", () => {
  it("submits an Authoring ASK group from the Conversation card", async () => {
    const user = userEvent.setup();
    const interaction = buildInteraction({
      authoring: {
        commandError: null,
        commandRecoveryActions: [],
        isSubmitting: false,
        rawTaskId: "raw-1",
      },
    });

    render(
      <ConversationAskCard
        card={authoringCard()}
        interaction={interaction}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Grade seven" }));
    await user.type(screen.getByPlaceholderText("Add your answer."), "Playful");
    await user.click(
      screen.getByRole("button", { name: "Submit all answers" }),
    );

    expect(interaction.onSubmitAuthoring).toHaveBeenCalledWith("raw-1", [
      { askId: "audience", value: "grade-7" },
      { askId: "style", value: "Playful" },
    ]);
  });

  it("answers, defers, and cancels an Execution ASK from Conversation", async () => {
    const user = userEvent.setup();
    const interaction = buildInteraction({
      execution: {
        askId: "ask-1",
        commandError: null,
        commandRecoveryActions: [],
        isAnswering: false,
        isCancelling: false,
        isDeferring: false,
      },
    });

    render(
      <ConversationAskCard
        card={executionCard()}
        interaction={interaction}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Vercel/ }));
    await user.click(screen.getByRole("button", { name: "Answer" }));
    await user.click(screen.getByRole("button", { name: "Defer" }));
    await user.click(screen.getByRole("button", { name: "Cancel question" }));

    expect(interaction.onAnswerExecution).toHaveBeenCalledWith("ask-1", {
      selectedOptionIds: ["vercel"],
      text: null,
    });
    expect(interaction.onDeferExecution).toHaveBeenCalledWith("ask-1");
    expect(interaction.onCancelExecution).toHaveBeenCalledWith("ask-1");
  });

  it("keeps the original question and marks the selected option after answering", () => {
    const card = executionCard({
      canAnswer: false,
      canCancel: false,
      canDefer: false,
      status: "answered",
      resolvedAt: "2026-07-24T10:05:00Z",
      questions: [
        {
          ...executionCard().questions[0],
          options: executionCard().questions[0].options.map((option) => ({
            ...option,
            selected: option.id === "vercel",
          })),
        },
      ],
    });

    render(<ConversationAskCard card={card} />);

    expect(
      screen.getByRole("heading", {
        name: "Where should Plato deploy?",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Answered")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Vercel/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.queryByRole("button", { name: "Answer" })).not.toBeInTheDocument();
  });
});

function authoringCard(): ConversationAskCardView {
  return {
    cardId: "conversation-ask:authoring:raw-1",
    domain: "authoring",
    status: "pending",
    title: "Planning questions",
    body: "Clarify the courseware direction.",
    rawTaskId: "raw-1",
    questions: [
      {
        id: "audience",
        prompt: "Who is the audience?",
        reason: "The audience controls the tone.",
        required: true,
        answerType: "single_choice",
        allowFreeText: false,
        options: [
          {
            id: "grade-seven",
            value: "grade-7",
            label: "Grade seven",
            selected: false,
          },
          {
            id: "grade-nine",
            value: "grade-9",
            label: "Grade nine",
            selected: false,
          },
        ],
      },
      {
        id: "style",
        prompt: "What visual style?",
        reason: "The style controls the presentation.",
        required: true,
        answerType: "free_text",
        allowFreeText: true,
        options: [],
      },
    ],
    createdAt: "2026-07-24T10:00:00Z",
    canAnswer: true,
    canDefer: false,
    canCancel: false,
  };
}

function executionCard(
  overrides: Partial<ConversationAskCardView> = {},
): ConversationAskCardView {
  return {
    cardId: "conversation-ask:execution:ask-1",
    domain: "execution",
    status: "pending",
    title: "Task needs input",
    body: "Deployment needs a target.",
    askId: "ask-1",
    taskNodeId: "task-1",
    questions: [
      {
        id: "ask-1",
        prompt: "Where should Plato deploy?",
        reason: "Deployment needs a target.",
        required: true,
        answerType: "single_choice",
        allowFreeText: true,
        options: [
          {
            id: "vercel",
            value: "vercel",
            label: "Vercel",
            description: "Use Vercel for the first deployment.",
            selected: false,
          },
          {
            id: "netlify",
            value: "netlify",
            label: "Netlify",
            selected: false,
          },
        ],
      },
    ],
    createdAt: "2026-07-24T10:00:00Z",
    canAnswer: true,
    canDefer: true,
    canCancel: true,
    ...overrides,
  };
}

function buildInteraction(
  overrides: Partial<ConversationAskInteraction> = {},
): ConversationAskInteraction {
  return {
    authoring: null,
    execution: null,
    onAnswerExecution: vi.fn(),
    onCancelExecution: vi.fn(),
    onDeferExecution: vi.fn(),
    onSubmitAuthoring: vi.fn(),
    ...overrides,
  };
}
