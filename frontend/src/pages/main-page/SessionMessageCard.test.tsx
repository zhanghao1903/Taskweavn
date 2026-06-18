import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SessionMessageView } from "../../shared/api/types";
import styles from "./MainPage.module.css";
import { SessionMessageCard } from "./SessionMessageCard";

describe("SessionMessageCard", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-27T12:00:00"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders session-wide message presentation", () => {
    render(<SessionMessageCard message={message({ taskNodeId: null })} />);

    expect(screen.getByText("Update")).toBeInTheDocument();
    expect(screen.getByText("Session activity")).toBeInTheDocument();
    expect(screen.getByText("09:00")).toHaveAttribute(
      "dateTime",
      "2026-05-27T09:00:00",
    );
    expect(screen.getByText("Planning started")).toBeInTheDocument();
    expect(screen.getByText("Plato is producing the draft task plan.")).toBeInTheDocument();
    expect(
      screen
        .getByText("Plato is producing the draft task plan.")
        .closest("[title]"),
    ).toHaveAttribute("title", "Plato is producing the draft task plan.");
    expect(screen.getByText("Planning started").closest("article")).toHaveClass(
      styles.systemConversationMessage,
    );
  });

  it("aligns user-authored messages to the right", () => {
    render(
      <SessionMessageCard
        message={message({
          body: "Please make the conversation feel interactive.",
          title: "User question",
        })}
      />,
    );

    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.getByText("Input")).toBeInTheDocument();
    expect(screen.getByText("09:00")).toBeInTheDocument();
    expect(screen.queryByText("Update")).not.toBeInTheDocument();
    expect(
      screen
        .getByText("Please make the conversation feel interactive.")
        .closest("article"),
    ).toHaveClass(
      styles.userConversationMessage,
      styles.userInputConversationMessage,
    );
  });

  it("shows a local date for messages outside today", () => {
    render(
      <SessionMessageCard
        message={message({
          createdAt: "2026-05-26T09:30:00",
          taskNodeId: null,
        })}
      />,
    );

    expect(screen.getByText("2026-05-26 09:30")).toHaveAttribute(
      "title",
      "2026-05-26 09:30",
    );
  });

  it("distinguishes user answers from typed input", () => {
    render(
      <SessionMessageCard
        message={message({
          body: "Use the playful direction.",
          title: "User answer",
        })}
      />,
    );

    expect(screen.getByText("Answer")).toBeInTheDocument();
    expect(
      screen.getByText("Use the playful direction.").closest("article"),
    ).toHaveClass(
      styles.userConversationMessage,
      styles.userAnswerConversationMessage,
    );
  });

  it("distinguishes user click actions from typed input", () => {
    render(
      <SessionMessageCard
        message={message({
          body: "Retry requested.",
          title: "User message",
        })}
      />,
    );

    expect(screen.getByText("Action")).toBeInTheDocument();
    expect(screen.getByText("Retry requested.").closest("article")).toHaveClass(
      styles.userConversationMessage,
      styles.userActionConversationMessage,
    );
  });

  it("renders message body markdown through the shared renderer", () => {
    render(
      <SessionMessageCard
        message={message({
          body: "**Task completed**\n\n- Result ready",
          taskNodeId: null,
        })}
      />,
    );

    expect(screen.getByText("Task completed").tagName).toBe("STRONG");
    expect(screen.getByText("Result ready")).toBeInTheDocument();
  });

  it("does not truncate long conversation message bodies", () => {
    const longBody = [
      "Line one explains the user intent.",
      "",
      "Line two keeps the complete context visible.",
      "",
      "- First detail",
      "- Second detail",
      "- Third detail",
    ].join("\n");

    render(
      <SessionMessageCard
        message={message({
          body: longBody,
          title: "User message",
        })}
      />,
    );

    const body = screen.getByText("Line one explains the user intent.").closest(
      "[title]",
    );
    expect(body).toHaveAttribute("title", longBody);
    expect(body?.closest("article")).not.toHaveClass(styles.messageCard);
    expect(screen.getByText("Third detail")).toBeInTheDocument();
  });

  it("renders task-scoped message presentation", () => {
    render(
      <SessionMessageCard
        message={message({
          kind: "actionable",
          taskNodeId: "task-implementation",
        })}
      />,
    );

    expect(screen.getByText("Needs reply")).toBeInTheDocument();
    expect(screen.getByText("Task activity")).toBeInTheDocument();
    expect(screen.queryByText("TaskNode: task-implementation")).not.toBeInTheDocument();
  });
});

function message(
  overrides: Partial<SessionMessageView>,
): SessionMessageView {
  return {
    id: "message-1",
    body: "Plato is producing the draft task plan.",
    createdAt: "2026-05-27T09:00:00",
    kind: "informational",
    sessionId: "session-website-plan",
    taskNodeId: null,
    title: "Planning started",
    ...overrides,
  };
}
