import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TaskTreePanel } from "./TaskTreePanel";

describe("TaskTreePanel", () => {
  it("uses user-facing empty task plan copy", () => {
    render(
      <TaskTreePanel
        onRetryTask={vi.fn()}
        onSelectTask={vi.fn()}
        onStopTask={vi.fn()}
        selectedTaskNodeId={null}
        taskTree={null}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "No task plan yet" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Describe your goal. Plato will turn it into a task plan for review before execution.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/task structure/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/No TaskTree yet/i)).not.toBeInTheDocument();
  });
});
