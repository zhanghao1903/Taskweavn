import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../app/App";
import { navigateApp } from "../app/navigation";
import { buildAuditTaskRoute, buildWorkspaceInspectionRoute } from "../app/routes";
import { AppProviders } from "../app/providers";

const requiredEnv = {
  baseUrl: process.env.PLATO_E2E_SIDECAR_BASE_URL,
  inspectionFilePath: process.env.PLATO_E2E_INSPECTION_FILE_PATH,
  sessionId: process.env.PLATO_E2E_SESSION_ID,
  taskId: process.env.PLATO_E2E_TASK_ID,
  workspaceId: process.env.PLATO_E2E_WORKSPACE_ID,
  workspaceRoot: process.env.PLATO_E2E_WORKSPACE_ROOT,
};

const describeSidecarE2E = Object.values(requiredEnv).every(Boolean)
  ? describe
  : describe.skip;

describeSidecarE2E("Workspace inspection real sidecar E2E", () => {
  afterEach(() => {
    globalThis.history.pushState(null, "", "/");
  });

  it("opens Audit file evidence in the read-only file and diff viewer", async () => {
    const user = userEvent.setup();
    const workspaceId = requiredEnv.workspaceId ?? "";
    const inspectionFilePath = requiredEnv.inspectionFilePath ?? "";
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

    await user.click(
      await screen.findByRole("button", {
        name: "Audit record File change recorded",
      }),
    );

    const detail = await screen.findByLabelText("Audit record detail");
    expect(detail).toHaveTextContent("Workspace evidence");
    expect(detail).toHaveTextContent(inspectionFilePath);
    expect(within(detail).getByRole("link", { name: "Open file" })).toHaveAttribute(
      "href",
      expect.stringContaining(`/workspaces/${workspaceId}/inspection`),
    );

    await user.click(within(detail).getByRole("link", { name: "View diff" }));

    expect(await screen.findByRole("heading", { name: "File diff" })).toBeInTheDocument();
    expect(
      await screen.findByText("+Workspace inspection seeded change."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: inspectionFilePath })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(requiredEnv.workspaceRoot ?? "");

    await act(async () => {
      navigateApp(
        buildWorkspaceInspectionRoute({
          sessionId: requiredEnv.sessionId,
          view: "status",
          workspaceId,
        }),
      );
    });

    expect(await screen.findByRole("heading", { name: "dirty" })).toBeInTheDocument();
    expect(screen.getByText(inspectionFilePath)).toBeInTheDocument();
    expect(screen.getAllByText("Unstaged").length).toBeGreaterThan(0);
    expect(document.body).not.toHaveTextContent(requiredEnv.workspaceRoot ?? "");
  }, 15_000);
});
