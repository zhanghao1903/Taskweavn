import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge, Button, Panel, Text } from ".";

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
});
