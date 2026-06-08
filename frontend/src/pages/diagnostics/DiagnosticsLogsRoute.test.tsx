import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DiagnosticsLogsRoute } from "./DiagnosticsLogsRoute";
import type { PlatoApi } from "../../shared/api/platoApi";

describe("DiagnosticsLogsRoute", () => {
  it("exports a diagnostic bundle and renders the sidecar descriptor", async () => {
    const user = userEvent.setup();
    const api = {
      exportDiagnosticBundle: vi.fn<
        Pick<PlatoApi, "exportDiagnosticBundle">["exportDiagnosticBundle"]
      >(async () => ({
        data: {
          bundleDir: "/tmp/diagnostics/diag-1",
          bundleDirLabel: "workspace://current/.plato/diagnostics/diag-1",
          bundleId: "diag-1",
          createdAt: "2026-06-05T12:00:00Z",
          fileCount: 7,
          includedSections: ["session", "audit", "frontend"],
          manifestPath: "/tmp/diagnostics/diag-1/manifest.json",
          manifestPathLabel:
            "workspace://current/.plato/diagnostics/diag-1/manifest.json",
          redactionProfile: "product_1_0_default",
          schemaVersion: "plato.diagnostics_export.v1",
          sections: [
            { name: "session", status: "included", warnings: [] },
            { name: "frontend", status: "partial", warnings: ["truncated"] },
          ],
          warnings: ["missing events"],
          zipPath: "/tmp/diagnostics/diag-1.zip",
          zipPathLabel: "workspace://current/.plato/diagnostics/diag-1.zip",
        },
        error: null,
        generatedAt: "2026-06-05T12:00:00Z",
        ok: true,
        requestId: "diagnostic-export-query",
      })),
    };

    render(
      <DiagnosticsLogsRoute
        api={api}
        location={{
          pathname: "/sessions/session-1/diagnostics/logs",
          search: "?category=audit&recordId=record-1",
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Export diagnostics" }));

    expect(api.exportDiagnosticBundle).toHaveBeenCalledWith("session-1");
    expect(
      await screen.findByRole("heading", { name: "Bundle ready" }),
    ).toBeInTheDocument();
    expect(screen.getByText("diag-1")).toBeInTheDocument();
    expect(
      screen.getByText("workspace://current/.plato/diagnostics/diag-1.zip"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "workspace://current/.plato/diagnostics/diag-1/manifest.json",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("product_1_0_default")).toBeInTheDocument();
    expect(screen.getByText("2 warnings recorded in the manifest.")).toBeInTheDocument();
  });

  it("shows a retryable failure state when sidecar export fails", async () => {
    const user = userEvent.setup();
    const api = {
      exportDiagnosticBundle: vi.fn<
        Pick<PlatoApi, "exportDiagnosticBundle">["exportDiagnosticBundle"]
      >(async () => {
        throw new Error("sidecar unavailable");
      }),
    };

    render(
      <DiagnosticsLogsRoute
        api={api}
        location={{ pathname: "/sessions/session-1/diagnostics/logs" }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Export diagnostics" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Diagnostic export failed. Retry or use the CLI command.",
    );
  });

  it("keeps export disabled when the HTTP sidecar is not active", () => {
    render(
      <DiagnosticsLogsRoute
        location={{ pathname: "/sessions/session-1/diagnostics/logs" }}
        runtimeEnv={{ VITE_PLATO_API_MODE: "mock" }}
      />,
    );

    expect(screen.getByRole("button", { name: "Export diagnostics" })).toBeDisabled();
    expect(
      screen.getByText(
        "Start Plato with the local sidecar to export diagnostics from the UI.",
      ),
    ).toBeInTheDocument();
  });
});
