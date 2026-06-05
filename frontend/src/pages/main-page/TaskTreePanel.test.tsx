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
        "Describe a goal. Plato will draft a task plan for review.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/task structure/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/No TaskTree yet/i)).not.toBeInTheDocument();
  });

  it("shows an understanding transition while the first task plan is generating", () => {
    render(
      <TaskTreePanel
        isGeneratingTaskPlan={true}
        onRetryTask={vi.fn()}
        onSelectTask={vi.fn()}
        onStopTask={vi.fn()}
        selectedTaskNodeId={null}
        taskTree={null}
      />,
    );

    expect(
      screen.getByRole("status", { name: "Generating task plan" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Generating task plan" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Plato is understanding your goal and shaping the first task plan.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "No task plan yet" }),
    ).not.toBeInTheDocument();
  });
});
