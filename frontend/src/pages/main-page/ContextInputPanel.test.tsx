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
        recoveryActions={[]}
      />,
    );

    expect(screen.getByText("Writing to")).toBeInTheDocument();
    expect(screen.getByText("Task 4")).toBeInTheDocument();
    expect(screen.queryByText("Visual direction")).not.toBeInTheDocument();
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
        recoveryActions={[]}
      />,
    );

    expect(screen.getByLabelText("Context message")).toBeDisabled();
    expect(screen.getByLabelText("Context message")).toHaveAttribute(
      "placeholder",
      "Completed tasks are read-only.",
    );
    expect(
      screen.queryByText("Completed tasks are read-only."),
    ).not.toBeInTheDocument();
  });

  it("renders input command recovery labels with command errors", () => {
    render(
      <ContextInputPanel
        draft="Plan a smaller version"
        error="Input submission was rejected."
        input={inputView()}
        onDraftChange={vi.fn()}
        onSubmit={vi.fn()}
        recoveryActions={["edit_input", "retry_command"]}
      />,
    );

    expect(screen.getByText("Input submission was rejected.")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Input submission was rejected.",
    );
    expect(screen.getByText("Edit input")).toBeInTheDocument();
    expect(screen.getByText("Retry command")).toBeInTheDocument();
  });

  it("marks the submit button as busy while the message is being submitted", () => {
    render(
      <ContextInputPanel
        draft="Plan a smaller version"
        error={null}
        input={inputView()}
        isSubmitting
        onDraftChange={vi.fn()}
        onSubmit={vi.fn()}
        recoveryActions={[]}
      />,
    );

    const submit = screen.getByRole("button", { name: "Send message" });
    expect(submit).toBeDisabled();
    expect(submit).toHaveAttribute("aria-busy", "true");
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
