import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SessionMessageView } from "../../shared/api/types";
import { SessionMessageCard } from "./SessionMessageCard";

describe("SessionMessageCard", () => {
  it("renders session-wide message presentation", () => {
    render(<SessionMessageCard message={message({ taskNodeId: null })} />);

    expect(screen.getByText("Update")).toBeInTheDocument();
    expect(screen.getByText("Session-wide")).toBeInTheDocument();
    expect(screen.getByText("Planning started")).toBeInTheDocument();
    expect(screen.getByText("Plato is producing the draft task plan.")).toBeInTheDocument();
    expect(screen.getByText("Planning started")).toHaveAttribute(
      "title",
      "Planning started",
    );
    expect(
      screen.getByText("Plato is producing the draft task plan."),
    ).toHaveAttribute("title", "Plato is producing the draft task plan.");
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
    createdAt: "2026-05-27T09:00:00Z",
    kind: "informational",
    sessionId: "session-website-plan",
    taskNodeId: null,
    title: "Planning started",
    ...overrides,
  };
}
