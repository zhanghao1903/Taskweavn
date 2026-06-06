import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { getMainPageMockSnapshot } from "./mockPlatoApi";
import { TaskTreePanel } from "./TaskTreePanel";

describe("TaskTreePanel", () => {
  it("uses user-facing empty task plan copy", () => {
    render(
      <TaskTreePanel
        onRetryTask={vi.fn()}
        onSelectTaskPlan={vi.fn()}
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
        onSelectTaskPlan={vi.fn()}
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

  it("exposes the whole plan as a selectable target", async () => {
    const user = userEvent.setup();
    const onSelectTaskPlan = vi.fn();
    const { snapshot } = getMainPageMockSnapshot("s3-draft-ready");

    render(
      <TaskTreePanel
        isTaskPlanSelected={true}
        onRetryTask={vi.fn()}
        onSelectTaskPlan={onSelectTaskPlan}
        onSelectTask={vi.fn()}
        onStopTask={vi.fn()}
        selectedTaskNodeId={null}
        taskTree={snapshot.taskTree}
      />,
    );

    const planButton = screen.getByRole("button", {
      name: "Plan overview Personal website project plan 4 tasks in this plan draft",
    });

    expect(planButton).toHaveAttribute("aria-pressed", "true");

    await user.click(planButton);

    expect(onSelectTaskPlan).toHaveBeenCalledTimes(1);
  });
});
