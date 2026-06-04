import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Badge, Button, ChoiceGroup, Panel, Text } from ".";

describe("shared primitives", () => {
  it("renders a button with default button type", () => {
    render(<Button>Confirm</Button>);

    expect(screen.getByRole("button", { name: "Confirm" })).toHaveAttribute(
      "type",
      "button",
    );
  });

  it("renders a badge with visible text", () => {
    render(<Badge tone="warning">waiting user</Badge>);

    expect(screen.getByText("waiting user")).toBeInTheDocument();
  });

  it("renders a labelled panel", () => {
    render(
      <Panel title="TaskTree" titleId="tasktree-title">
        <p>Task content</p>
      </Panel>,
    );

    expect(screen.getByRole("region", { name: "TaskTree" })).toHaveTextContent(
      "Task content",
    );
  });

  it("renders text using the requested element", () => {
    render(
      <Text as="h1" variant="heading">
        Plato
      </Text>,
    );

    expect(screen.getByRole("heading", { name: "Plato" })).toBeInTheDocument();
  });

  it("selects one choice in single mode", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <ChoiceGroup
        label="Deployment target"
        onChange={onChange}
        options={[
          { label: "Vercel", value: "vercel" },
          { label: "Netlify", value: "netlify" },
        ]}
        selectedValues={[]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Vercel" }));

    expect(onChange).toHaveBeenCalledWith(["vercel"]);
  });

  it("toggles multiple choices in multi mode", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <ChoiceGroup
        mode="multi"
        onChange={onChange}
        options={[
          { label: "React", value: "react" },
          { label: "Vite", value: "vite" },
        ]}
        selectedValues={["react"]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Vite" }));
    await user.click(screen.getByRole("button", { name: "React" }));

    expect(onChange).toHaveBeenNthCalledWith(1, ["react", "vite"]);
    expect(onChange).toHaveBeenNthCalledWith(2, []);
  });

  it("prevents interaction while disabled", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <ChoiceGroup
        disabled
        onChange={onChange}
        options={[{ label: "Approve", value: "approve" }]}
        selectedValues={[]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Approve" }));

    expect(onChange).not.toHaveBeenCalled();
  });

  it("prevents interaction while loading", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <ChoiceGroup
        label="Runtime"
        loading
        onChange={onChange}
        options={[{ label: "Default agent", value: "default-agent" }]}
        selectedValues={[]}
      />,
    );

    expect(screen.getByRole("group", { name: "Runtime" })).toHaveAttribute(
      "aria-busy",
      "true",
    );

    await user.click(screen.getByRole("button", { name: "Default agent" }));

    expect(onChange).not.toHaveBeenCalled();
  });

  it("renders segmented selected choices", () => {
    render(
      <ChoiceGroup
        label="Confirm"
        layout="segmented"
        onChange={vi.fn()}
        options={[
          { label: "Yes", value: "yes" },
          { label: "No", value: "no", tone: "danger" },
        ]}
        selectedValues={["yes"]}
      />,
    );

    expect(screen.getByRole("button", { name: "Yes" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "No" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("supports keyboard selection and validation feedback", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <ChoiceGroup
        error="Choose one option."
        onChange={onChange}
        options={[{ label: "Skip", value: "skip" }]}
        selectedValues={[]}
      />,
    );

    await user.tab();
    await user.keyboard("[Space]");

    expect(onChange).toHaveBeenCalledWith(["skip"]);
    expect(screen.getByRole("alert")).toHaveTextContent("Choose one option.");
  });
});
