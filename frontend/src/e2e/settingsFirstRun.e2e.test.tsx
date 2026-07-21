import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../app/App";
import { AppProviders } from "../app/providers";

const requiredEnv = {
  configuredBaseUrl: process.env.PLATO_E2E_FIRST_RUN_CONFIGURED_BASE_URL,
  configuredSessionId: process.env.PLATO_E2E_FIRST_RUN_CONFIGURED_SESSION_ID,
  unconfiguredBaseUrl: process.env.PLATO_E2E_FIRST_RUN_UNCONFIGURED_BASE_URL,
  unconfiguredSessionId: process.env.PLATO_E2E_FIRST_RUN_UNCONFIGURED_SESSION_ID,
};

const describeSidecarE2E = Object.values(requiredEnv).every(Boolean)
  ? describe
  : describe.skip;

describeSidecarE2E("Settings first-run real sidecar E2E", () => {
  afterEach(() => {
    globalThis.history.pushState(null, "", "/");
  });

  it("saves missing first-run settings and opens the Main Page", async () => {
    const user = userEvent.setup();
    const secret = "sk-sidecar-settings-e2e-secret";
    globalThis.history.pushState(null, "", "/");

    render(
      <AppProviders>
        <App
          runtimeEnv={{
            VITE_PLATO_API_BASE_URL: requiredEnv.unconfiguredBaseUrl,
            VITE_PLATO_API_MODE: "http",
            VITE_PLATO_SESSION_ID: requiredEnv.unconfiguredSessionId,
          }}
        />
      </AppProviders>,
    );

    expect(
      await screen.findByRole("heading", { name: "Setup required" }),
    ).toBeInTheDocument();
    expect(screen.getByText("needs_configuration")).toBeInTheDocument();
    expect(screen.getByText("deepseek")).toBeInTheDocument();
    expect(screen.getByText("DEEPSEEK_API_KEY")).toBeInTheDocument();
    expect(screen.getByText("LLM_API_KEY")).toBeInTheDocument();
    expect(screen.getByText("Configure local provider settings.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry check" })).toBeInTheDocument();
    expect(screen.queryByText("Diagnostics smoke")).not.toBeInTheDocument();
    expect(screen.queryByText("Run diagnostic-export-task")).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("test-sidecar-readiness-key");

    await user.click(screen.getByRole("button", { name: "Configure settings" }));

    expect(
      await screen.findByRole("heading", { name: "Complete first-run setup" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Provider")).toHaveValue("deepseek");
    await user.type(screen.getByLabelText("API key"), secret);
    await user.click(screen.getByRole("button", { name: "Save and check" }));

    expect(await screen.findByText("First-run setup is ready.")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(secret);

    await user.click(screen.getByRole("button", { name: "Continue to Main Page" }));

    await waitFor(
      () => {
        expect(screen.getAllByText("Diagnostics smoke").length).toBeGreaterThan(0);
        expect(
          screen.getAllByText("Run diagnostic-export-task").length,
        ).toBeGreaterThan(0);
      },
      { timeout: 10_000 },
    );
    expect(document.body).not.toHaveTextContent(secret);
  });

  it("opens the Main Page when the sidecar reports configured first-run readiness", async () => {
    globalThis.history.pushState(null, "", "/");

    render(
      <AppProviders>
        <App
          runtimeEnv={{
            VITE_PLATO_API_BASE_URL: requiredEnv.configuredBaseUrl,
            VITE_PLATO_API_MODE: "http",
            VITE_PLATO_SESSION_ID: requiredEnv.configuredSessionId,
          }}
        />
      </AppProviders>,
    );

    await waitFor(
      () => {
        expect(screen.getAllByText("Diagnostics smoke").length).toBeGreaterThan(0);
        expect(
          screen.getAllByText("Run diagnostic-export-task").length,
        ).toBeGreaterThan(0);
      },
      { timeout: 10_000 },
    );
    expect(screen.queryByRole("heading", { name: "Setup required" })).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("test-sidecar-readiness-key");
  });
});
