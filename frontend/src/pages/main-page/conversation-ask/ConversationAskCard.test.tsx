import { render, screen, within } from "@testing-library/react";
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

  it("keeps completed Authoring questions read-only and submits only unanswered questions", async () => {
    const user = userEvent.setup();
    const interaction = buildInteraction({
      authoring: {
        commandError: null,
        commandRecoveryActions: [],
        isSubmitting: false,
        rawTaskId: "raw-1",
      },
    });
    const card = authoringCard();
    card.questions[0] = {
      ...card.questions[0],
      answered: true,
      options: card.questions[0].options.map((option) => ({
        ...option,
        selected: option.id === "grade-seven",
      })),
    };

    render(<ConversationAskCard card={card} interaction={interaction} />);

    expect(
      screen.getByRole("button", { name: /Grade seven.*Selected/ }),
    ).toBeDisabled();
    await user.type(screen.getByPlaceholderText("Add your answer."), "Playful");
    await user.click(
      screen.getByRole("button", { name: "Submit all answers" }),
    );

    expect(interaction.onSubmitAuthoring).toHaveBeenCalledWith("raw-1", [
      { askId: "style", value: "Playful" },
    ]);
  });

  it("answers, defers, and cancels an Execution ASK from Conversation", async () => {
    const user = userEvent.setup();
    const interaction = buildInteraction({
      executionByAskId: {
        "ask-1": {
          askId: "ask-1",
          commandError: null,
          commandRecoveryActions: [],
          isAnswering: false,
          isCancelling: false,
          isDeferring: false,
        },
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
          answered: true,
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
    expect(screen.getAllByText("Answered")).toHaveLength(2);
    const choiceGroup = screen.getByRole("group", {
      name: "Where should Plato deploy?",
    });
    expect(
      within(choiceGroup).getByRole("button", {
        name: /Vercel.*Selected/,
      }),
    ).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(choiceGroup).getByText("✓ Selected")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Answer" })).not.toBeInTheDocument();
  });

  it("places pending and error state on the matching Execution ASK cards", async () => {
    const user = userEvent.setup();
    const firstCard = executionCard({
      askId: "ask-1",
      cardId: "conversation-ask:execution:ask-1",
      title: "First ASK",
    });
    const secondCard = executionCard({
      askId: "ask-2",
      cardId: "conversation-ask:execution:ask-2",
      title: "Second ASK",
      questions: [
        {
          ...executionCard().questions[0],
          id: "ask-2",
          prompt: "Which fallback should Plato use?",
          options: executionCard().questions[0].options.map((option) => ({
            ...option,
            selected: option.id === "vercel",
          })),
        },
      ],
    });
    const interaction = buildInteraction({
      executionByAskId: {
        "ask-1": {
          askId: "ask-1",
          commandError: null,
          commandRecoveryActions: [],
          isAnswering: true,
          isCancelling: false,
          isDeferring: false,
        },
        "ask-2": {
          askId: "ask-2",
          commandError: "Second ASK failed.",
          commandRecoveryActions: [],
          isAnswering: false,
          isCancelling: false,
          isDeferring: false,
        },
      },
      hasExecutionCommandPending: true,
    });

    render(
      <>
        <ConversationAskCard card={firstCard} interaction={interaction} />
        <ConversationAskCard card={secondCard} interaction={interaction} />
      </>,
    );

    const firstForm = screen.getByRole("form", { name: "First ASK" });
    const secondForm = screen.getByRole("form", { name: "Second ASK" });
    expect(within(firstForm).queryByText("Second ASK failed.")).toBeNull();
    expect(within(secondForm).getByText("Second ASK failed.")).toBeVisible();
    expect(
      within(firstForm).getByRole("button", { name: "Answering" }),
    ).toBeDisabled();
    expect(
      within(secondForm).getByRole("button", { name: "Answer" }),
    ).toBeDisabled();

    await user.click(
      within(secondForm).getByRole("button", { name: "Answer" }),
    );
    expect(interaction.onAnswerExecution).not.toHaveBeenCalled();
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
        answered: false,
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
        answered: false,
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
        answered: false,
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
    executionByAskId: {},
    hasExecutionCommandPending: false,
    onAnswerExecution: vi.fn(),
    onCancelExecution: vi.fn(),
    onDeferExecution: vi.fn(),
    onSubmitAuthoring: vi.fn(),
    ...overrides,
  };
}
