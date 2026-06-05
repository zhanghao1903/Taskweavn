import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SessionMessageView } from "../../shared/api/types";
import { SessionMessageCard } from "./SessionMessageCard";

describe("SessionMessageCard", () => {
  it("renders session-wide message presentation", () => {
    render(<SessionMessageCard message={message({ taskNodeId: null })} />);

    expect(screen.getByText("informational")).toBeInTheDocument();
    expect(screen.getByText("Session-wide")).toBeInTheDocument();
    expect(screen.getByText("Planning started")).toBeInTheDocument();
    expect(screen.getByText("Plato is producing the draft TaskTree.")).toBeInTheDocument();
    expect(screen.getByText("Planning started")).toHaveAttribute(
      "title",
      "Planning started",
    );
    expect(
      screen.getByText("Plato is producing the draft TaskTree."),
    ).toHaveAttribute("title", "Plato is producing the draft TaskTree.");
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

    expect(screen.getByText("actionable")).toBeInTheDocument();
    expect(screen.getByText("Task activity")).toBeInTheDocument();
    expect(screen.queryByText("TaskNode: task-implementation")).not.toBeInTheDocument();
  });
});

function message(
  overrides: Partial<SessionMessageView>,
): SessionMessageView {
  return {
    id: "message-1",
    body: "Plato is producing the draft TaskTree.",
    createdAt: "2026-05-27T09:00:00Z",
    kind: "informational",
    sessionId: "session-website-plan",
    taskNodeId: null,
    title: "Planning started",
    ...overrides,
  };
}
