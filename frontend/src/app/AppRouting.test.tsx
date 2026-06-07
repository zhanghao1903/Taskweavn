import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { AppProviders } from "./providers";

describe("App routing", () => {
  afterEach(() => {
    globalThis.history.pushState(null, "", "/");
  });

  it("renders Main Page at the root route", async () => {
    globalThis.history.pushState(null, "", "/");

    render(
      <AppProviders>
        <App />
      </AppProviders>,
    );

    expect(await screen.findByText("Plan & Progress")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View audit" })).toHaveAttribute(
      "href",
      expect.stringContaining("/audit"),
    );
    expect(screen.queryByRole("heading", { name: "Audit" })).not.toBeInTheDocument();
  });

  it("renders Audit Page for session audit routes", async () => {
    globalThis.history.pushState(null, "", "/sessions/session-website-plan/audit");

    render(
      <AppProviders>
        <App />
      </AppProviders>,
    );

    expect(await screen.findByRole("heading", { name: "Audit" })).toBeInTheDocument();
    expect(screen.getByLabelText("Audit records")).toBeInTheDocument();
  });

  it("renders Audit Page for task audit routes", async () => {
    globalThis.history.pushState(
      null,
      "",
      "/sessions/session-website-plan/tasks/task-implementation/audit",
    );

    render(
      <AppProviders>
        <App />
      </AppProviders>,
    );

    expect(await screen.findByRole("heading", { name: "Audit" })).toBeInTheDocument();
    expect(screen.getByText("Action completed")).toBeInTheDocument();
  });

  it("re-renders the Main Page after Audit Page Return SPA navigation", async () => {
    const user = userEvent.setup();
    globalThis.history.pushState(
      null,
      "",
      "/sessions/session-website-plan/tasks/task-implementation/audit",
    );

    render(
      <AppProviders>
        <App />
      </AppProviders>,
    );

    expect(await screen.findByRole("heading", { name: "Audit" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Return" }));

    expect(await screen.findByText("Plan & Progress")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Audit" })).not.toBeInTheDocument();
    expect(globalThis.location.pathname).not.toContain("/audit");
  });
});
