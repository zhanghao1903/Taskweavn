import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MainPageTopBar } from "./MainPageTopBar";

describe("MainPageTopBar", () => {
  it("keeps top navigation focused on identity, context, and status", () => {
    render(
      <MainPageTopBar
        brandLabel="Plato"
        contextItems={["Personal Website", "Task authoring", "website"]}
        statuses={[{ label: "Running", tone: "blue" }]}
      />,
    );

    expect(screen.getByRole("banner", { name: "Plato" })).toBeInTheDocument();
    expect(screen.getByText("Personal Website")).toBeInTheDocument();
    expect(screen.getByText("Task authoring")).toBeInTheDocument();
    expect(screen.getByText("Session: website")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "查看审计" })).toBeNull();
    expect(screen.queryByRole("button", { name: "设置" })).toBeNull();
  });

  it("keeps the trailing slot available for fixture-only controls", () => {
    render(
      <MainPageTopBar
        brandLabel="Plato"
        contextItems={["Personal Website", "Task authoring", "website"]}
        statuses={[]}
        trailing={<label htmlFor="state-picker">State</label>}
      />,
    );

    expect(screen.getByText("State")).toBeInTheDocument();
  });
});
