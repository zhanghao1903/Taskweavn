import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { navigateApp } from "./navigation";
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

    expect(
      await screen.findByRole("heading", { name: "Plan & Progress" }),
    ).toBeInTheDocument();
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

  it("renders Workspace Inspection routes outside the Main Page", async () => {
    globalThis.history.pushState(
      null,
      "",
      "/workspaces/ws-a/inspection?view=file&path=src%2FApp.tsx",
    );

    render(
      <AppProviders>
        <App />
      </AppProviders>,
    );

    expect(
      await screen.findByRole("heading", { name: "Inspection unavailable" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Workspace inspection requires the local sidecar."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Plan & Progress" }),
    ).not.toBeInTheDocument();
  });

  it("re-renders Workspace Inspection when only query parameters change", async () => {
    globalThis.history.pushState(
      null,
      "",
      "/workspaces/ws-a/inspection?view=diff&path=src%2FApp.tsx",
    );

    render(
      <AppProviders>
        <App />
      </AppProviders>,
    );

    expect(await screen.findByRole("heading", { name: "File diff" })).toBeInTheDocument();

    await act(async () => {
      navigateApp("/workspaces/ws-a/inspection?view=status");
    });

    expect(
      await screen.findByRole("heading", { name: "Changed files" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "File diff" })).not.toBeInTheDocument();
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

    expect(
      await screen.findByRole("heading", { name: "Plan & Progress" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View audit" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Audit" })).not.toBeInTheDocument();
    expect(globalThis.location.pathname).not.toContain("/audit");
  });

  it("keeps Audit return workspace and task target during SPA navigation", async () => {
    const user = userEvent.setup();
    globalThis.history.pushState(
      null,
      "",
      "/sessions/session-website-plan/tasks/task-implementation/audit?returnFocus=task&returnSessionId=session-return&returnTaskNodeId=task-return&workspaceId=workspace-return",
    );

    render(
      <AppProviders>
        <App />
      </AppProviders>,
    );

    expect(await screen.findByRole("heading", { name: "Audit" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Return" }));

    expect(globalThis.location.pathname).toBe("/sessions/session-return");
    expect(globalThis.location.search).toBe(
      "?taskNodeId=task-return&workspaceId=workspace-return",
    );
    expect(
      await screen.findByRole("heading", { name: "Plan & Progress" }),
    ).toBeInTheDocument();
  });
});
