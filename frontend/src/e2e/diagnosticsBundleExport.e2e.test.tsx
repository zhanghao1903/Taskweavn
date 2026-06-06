import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { DiagnosticsLogsRoute } from "../pages/diagnostics/DiagnosticsLogsRoute";

const requiredEnv = {
  baseUrl: process.env.PLATO_E2E_SIDECAR_BASE_URL,
  diagnosticsLogUrl: process.env.PLATO_E2E_DIAGNOSTICS_LOG_URL,
  logRecordId: process.env.PLATO_E2E_LOG_RECORD_ID,
  sessionId: process.env.PLATO_E2E_SESSION_ID,
  workspaceRoot: process.env.PLATO_E2E_WORKSPACE_ROOT,
};

const describeSidecarE2E = Object.values(requiredEnv).every(Boolean)
  ? describe
  : describe.skip;

describeSidecarE2E("Diagnostics bundle export real sidecar E2E", () => {
  it("exports diagnostics from the seeded Audit log handoff route", async () => {
    const user = userEvent.setup();
    const url = new URL(requiredEnv.diagnosticsLogUrl ?? "");

    render(
      <DiagnosticsLogsRoute
        location={{
          pathname: url.pathname,
          search: url.search,
        }}
        runtimeEnv={{
          VITE_PLATO_API_BASE_URL: requiredEnv.baseUrl,
          VITE_PLATO_API_MODE: "http",
        }}
      />,
    );

    expect(screen.getByText(requiredEnv.sessionId ?? "")).toBeInTheDocument();
    expect(screen.getByText(requiredEnv.logRecordId ?? "")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Export diagnostics" }));

    expect(
      await screen.findByRole(
        "heading",
        { name: "Bundle ready" },
        { timeout: 10_000 },
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("product_1_0_default")).toBeInTheDocument();
    expect(
      screen.getByText((content) =>
        content.startsWith("workspace://current/.taskweavn/diagnostics/")
        && content.endsWith(".zip"),
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText((content) =>
        content.startsWith("workspace://current/.taskweavn/diagnostics/")
        && content.endsWith("/manifest.json"),
      ),
    ).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(requiredEnv.workspaceRoot ?? "");
  });
});
