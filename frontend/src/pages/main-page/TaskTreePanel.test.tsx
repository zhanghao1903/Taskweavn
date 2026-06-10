import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { renderWithUiText } from "../../shared/ui-text/testing";
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

  it("renders empty task plan copy in zh-CN when the UI locale changes", () => {
    renderWithUiText(
      <TaskTreePanel
        onRetryTask={vi.fn()}
        onSelectTaskPlan={vi.fn()}
        onSelectTask={vi.fn()}
        onStopTask={vi.fn()}
        selectedTaskNodeId={null}
        taskTree={null}
      />,
      { locale: "zh-CN" },
    );

    expect(
      screen.getByRole("heading", { name: "还没有任务计划" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("描述一个目标。Plato 会先为你起草任务计划。"),
    ).toBeInTheDocument();
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
      name: [
        "Plan overview",
        "Personal website project plan",
        "4 tasks in this plan",
        "draft",
      ].join(" "),
    });

    expect(planButton).toHaveAttribute("aria-pressed", "true");

    await user.click(planButton);

    expect(onSelectTaskPlan).toHaveBeenCalledTimes(1);
  });

  it("uses explicit plan title with summary detail when present", () => {
    const { snapshot } = getMainPageMockSnapshot("s3-draft-ready");

    render(
      <TaskTreePanel
        onRetryTask={vi.fn()}
        onSelectTaskPlan={vi.fn()}
        onSelectTask={vi.fn()}
        onStopTask={vi.fn()}
        selectedTaskNodeId={null}
        taskTree={{
          ...snapshot.taskTree!,
          summary: "A concise website plan from content to implementation.",
        }}
      />,
    );

    expect(
      screen.getByText("Personal website project plan"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("A concise website plan from content to implementation."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/4-task plan covering/),
    ).not.toBeInTheDocument();
  });

  it("shows dirty authoring diagnostics and exposes a repair action", async () => {
    const user = userEvent.setup();
    const onRepairAuthoringState = vi.fn();
    const { snapshot } = getMainPageMockSnapshot("s3-draft-ready");

    render(
      <TaskTreePanel
        authoringDiagnostic={{
          code: "dirty_authoring_state",
          message:
            "A stale authoring draft was found after this TaskTree was generated.",
          severity: "warning",
        }}
        onRepairAuthoringState={onRepairAuthoringState}
        onRetryTask={vi.fn()}
        onSelectTaskPlan={vi.fn()}
        onSelectTask={vi.fn()}
        onStopTask={vi.fn()}
        selectedTaskNodeId={null}
        taskTree={snapshot.taskTree}
      />,
    );

    expect(
      screen.getByText("Authoring state needs repair"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "A stale authoring draft was found after this TaskTree was generated.",
      ),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Repair authoring state" }),
    );

    expect(onRepairAuthoringState).toHaveBeenCalledTimes(1);
  });
});
