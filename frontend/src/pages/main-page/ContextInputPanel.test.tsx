import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ContextInputPanel } from "./ContextInputPanel";
import type { MainPageInputViewModel } from "./mainPageViewModel";

describe("ContextInputPanel", () => {
  it("uses the scoped placeholder without repeating helper copy when input is enabled", () => {
    render(
      <ContextInputPanel
        draft=""
        error={null}
        input={inputView()}
        onDraftChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText("Writing to Task 4")).toBeInTheDocument();
    expect(screen.getByText("Visual direction")).toBeInTheDocument();
    expect(screen.getByLabelText("Context message")).toHaveAttribute(
      "placeholder",
      "Add guidance for this task.",
    );
    expect(screen.queryByText("Add guidance for this task.")).not.toBeInTheDocument();
  });

  it("uses the disabled reason as the input placeholder when input is read-only", () => {
    render(
      <ContextInputPanel
        draft=""
        error={null}
        input={inputView({
          disabled: true,
          disabledReason: "Completed tasks are read-only.",
        })}
        onDraftChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText("Completed tasks are read-only.")).toBeInTheDocument();
    expect(screen.getByLabelText("Context message")).toBeDisabled();
    expect(screen.getByLabelText("Context message")).toHaveAttribute(
      "placeholder",
      "Completed tasks are read-only.",
    );
  });
});

function inputView(
  overrides: Partial<MainPageInputViewModel> = {},
): MainPageInputViewModel {
  return {
    disabled: false,
    disabledReason: null,
    mode: "append_task_input",
    scope: {
      description: "Visual direction",
      label: "Writing to Task 4",
      placeholder: "Add guidance for this task.",
    },
    target: "task",
    taskNodeId: "task-visual-direction",
    ...overrides,
  };
}
