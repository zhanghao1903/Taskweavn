import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthoringAskWorkArea } from "./AuthoringAskWorkArea";
import type { MainPageAuthoringAskViewModel } from "../mainPageViewModel";

describe("AuthoringAskWorkArea", () => {
  it("submits all valid authoring ASK answers in one batch", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <AuthoringAskWorkArea
        onSubmit={onSubmit}
        view={authoringAskView()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Portfolio" }));
    await user.click(screen.getByRole("button", { name: "Quiet editorial" }));

    expect(screen.getByText("Clarification questions")).toBeInTheDocument();
    expect(screen.queryByText("Authoring ASK")).not.toBeInTheDocument();
    expect(
      screen.getByText("Review the questions, then submit all answers together."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/backend projection/i)).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Submit all answers" }),
    );

    expect(onSubmit).toHaveBeenCalledWith({
      rawTaskId: "raw-task-website-goal",
      answers: [
        { askId: "authoring-ask-site-type", value: "portfolio" },
        { askId: "authoring-ask-style", value: "quiet_editorial" },
      ],
    });
  });

  it("keeps drafts local when any answer is missing", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <AuthoringAskWorkArea
        onSubmit={onSubmit}
        view={authoringAskView()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Portfolio" }));
    await user.click(
      screen.getByRole("button", { name: "Submit all answers" }),
    );

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Portfolio" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(
      screen.getByText("Complete all questions before submitting."),
    ).toBeInTheDocument();
  });

  it("renders command errors without clearing local choices", async () => {
    const user = userEvent.setup();

    render(
      <AuthoringAskWorkArea
        onSubmit={vi.fn()}
        view={authoringAskView({
          commandError: "Authoring ASK command was rejected.",
        })}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Portfolio" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Authoring ASK command was rejected.",
    );
    expect(screen.getByRole("button", { name: "Portfolio" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("disables controls while submitting", () => {
    render(
      <AuthoringAskWorkArea
        onSubmit={vi.fn()}
        view={authoringAskView({ isSubmitting: true })}
      />,
    );

    expect(screen.getByRole("button", { name: "Portfolio" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Submitting" })).toBeDisabled();
  });
});

function authoringAskView(
  overrides: Partial<MainPageAuthoringAskViewModel> = {},
): MainPageAuthoringAskViewModel {
  return {
    asks: [
      {
        id: "authoring-ask-site-type",
        question: "What kind of website should Plato plan first?",
        reason: "The TaskTree depends on the primary purpose.",
        required: true,
        options: [
          { label: "Portfolio", tone: "primary", value: "portfolio" },
          { label: "Blog", value: "blog" },
        ],
        status: "pending",
      },
      {
        id: "authoring-ask-style",
        question: "Which visual direction should guide the first draft?",
        reason: "The style direction keeps downstream work aligned.",
        required: false,
        options: [
          {
            label: "Quiet editorial",
            tone: "primary",
            value: "quiet_editorial",
          },
          { label: "Technical portfolio", value: "technical_portfolio" },
        ],
        status: "pending",
      },
    ],
    commandError: null,
    isSubmitting: false,
    rawTaskId: "raw-task-website-goal",
    summary: "The session needs planning clarification.",
    title: "Understanding goal",
    ...overrides,
  };
}
