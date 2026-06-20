import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../app/App";
import { navigateApp } from "../app/navigation";
import { AppProviders } from "../app/providers";
import { buildAuditTaskRoute } from "../app/routes";

const requiredEnv = {
  baseUrl: process.env.PLATO_E2E_SIDECAR_BASE_URL,
  sessionId: process.env.PLATO_E2E_SESSION_ID,
  taskId: process.env.PLATO_E2E_TASK_ID,
  workspaceRoot: process.env.PLATO_E2E_WORKSPACE_ROOT,
};

const describeSidecarE2E = Object.values(requiredEnv).every(Boolean)
  ? describe
  : describe.skip;

describeSidecarE2E("Audit result/evidence real sidecar E2E", () => {
  afterEach(() => {
    globalThis.history.pushState(null, "", "/");
  });

  it("opens Audit from Main Page and loads record detail plus evidence", async () => {
    const user = userEvent.setup();
    globalThis.history.pushState(null, "", "/");

    render(
      <AppProviders>
        <App
          runtimeEnv={{
            VITE_PLATO_API_BASE_URL: requiredEnv.baseUrl,
            VITE_PLATO_API_MODE: "http",
            VITE_PLATO_SESSION_ID: requiredEnv.sessionId,
          }}
        />
      </AppProviders>,
    );

    await waitFor(
      () => {
        expect(screen.getAllByText("Diagnostics smoke").length).toBeGreaterThan(0);
      },
      { timeout: 10_000 },
    );
    expect(screen.getAllByText(`Run ${requiredEnv.taskId}`).length).toBeGreaterThan(0);

    await act(async () => {
      navigateApp(
        buildAuditTaskRoute(requiredEnv.sessionId ?? "", requiredEnv.taskId ?? ""),
      );
    });

    expect(await screen.findByRole("heading", { name: "Audit" })).toBeInTheDocument();
    const filters = await screen.findByLabelText("Audit record filters");
    const allRecordsFilter = within(filters).getByRole("button", {
      name: /All records/,
    });
    if (allRecordsFilter.getAttribute("aria-current") !== "true") {
      await user.click(allRecordsFilter);
    }

    expect(
      await screen.findByRole("button", { name: "Audit record Task result available" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Audit record File change recorded" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "Audit record FileWriteObservation observation",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Audit record Logging config snapshot" }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "Audit record Log evidence available" })
        .length,
    ).toBeGreaterThan(0);

    await user.click(
      screen.getByRole("button", { name: "Audit record Task result available" }),
    );

    const resultDetail = await screen.findByLabelText("Audit record detail");
    expect(resultDetail).toHaveTextContent("Why it matters");
    expect(resultDetail).toHaveTextContent("Evidence");
    expect(resultDetail).toHaveTextContent("Timeline task result");
    expect(resultDetail).toHaveTextContent(
      "Provider rate limit prevented task completion.",
    );
    expect(
      await screen.findByText("Evidence payload · Timeline task result"),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Audit record File change recorded" }),
    );

    const fileDetail = await screen.findByLabelText("Audit record detail");
    expect(fileDetail).toHaveTextContent(/(Timeline|Projected) file change/);
    expect(fileDetail).toHaveTextContent("diagnostics-summary.md");
    expect(fileDetail).toHaveTextContent(
      "No sanitized payload is available for this record.",
    );

    await user.click(
      screen.getByRole("button", {
        name: "Audit record FileWriteObservation observation",
      }),
    );

    const eventDetail = await screen.findByLabelText("Audit record detail");
    expect(eventDetail).toHaveTextContent("FileWriteObservation payload");
    expect(
      await screen.findByText("Evidence payload · FileWriteObservation payload"),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("Audit record detail")).toHaveTextContent(
        "diagnostics-summary.md",
      );
    });

    expect(document.body).not.toHaveTextContent(requiredEnv.workspaceRoot ?? "");
  });
});
