import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../../shared/api/client";
import type {
  DiagnosticBundleExportResult,
  SettingsConfigSummary,
  SettingsConfigUpdateResult,
  SettingsReadinessReport,
} from "../../shared/api/platoApi";
import type { ApiError, QueryResponse } from "../../shared/api/types";
import { SettingsRoute, type SettingsRouteApi } from "./SettingsRoute";

describe("SettingsRoute", () => {
  afterEach(() => {
    globalThis.history.pushState(null, "", "/");
  });

  it("loads safe config without exposing stored secret values", async () => {
    renderWithQueryClient(
      <SettingsRoute api={settingsApi()} runtimeEnv={{ VITE_PLATO_API_MODE: "http" }} />,
    );

    expect(await screen.findByDisplayValue("anthropic/test-model")).toBeInTheDocument();
    expect(screen.getByText("configured")).toBeInTheDocument();
    expect(screen.getByText(/Configured via stored/)).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("sk-existing-secret");
  });

  it("renders as a dismissible modal when requested", async () => {
    const user = userEvent.setup();
    globalThis.history.pushState(null, "", "/settings?returnTo=/sessions/live");

    renderWithQueryClient(
      <SettingsRoute
        api={settingsApi()}
        presentation="modal"
        runtimeEnv={{ VITE_PLATO_API_MODE: "http" }}
      />,
    );

    expect(
      await screen.findByRole("dialog", { name: "Settings" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Close settings" }));

    expect(globalThis.location.pathname).toBe("/sessions/live");
  });

  it("saves config, rechecks readiness, and continues to Main Page", async () => {
    const user = userEvent.setup();
    const api = settingsApi({
      config: settingsConfig({ apiKeyConfigured: false }),
      readiness: settingsReadiness({ ready: true }),
    });
    globalThis.history.pushState(null, "", "/settings?source=first-run&returnTo=/");

    renderWithQueryClient(
      <SettingsRoute api={api} runtimeEnv={{ VITE_PLATO_API_MODE: "http" }} />,
    );

    await user.clear(await screen.findByLabelText("Model"));
    await user.type(screen.getByLabelText("Model"), "anthropic/updated-model");
    await user.type(screen.getByLabelText("API key"), "sk-route-secret");
    await user.click(screen.getByRole("button", { name: "Save and check" }));

    await waitFor(() => {
      expect(api.updateSettingsConfig).toHaveBeenCalledWith({
        llm: {
          apiKey: "sk-route-secret",
          model: "anthropic/updated-model",
          provider: "litellm",
        },
        logging: {
          selectedProfile: "normal",
        },
      });
    });
    expect(api.recheckSettingsReadiness).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("First-run setup is ready.")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("sk-route-secret");

    await user.click(screen.getByRole("button", { name: "Continue to Main Page" }));

    expect(globalThis.location.pathname).toBe("/");
  });

  it("shows structured save failures without keeping the secret field populated", async () => {
    const user = userEvent.setup();
    const apiError: ApiError = {
      code: "bad_request",
      details: {
        fieldErrors: [
          {
            message: "an API key is required for the selected provider",
            path: "llm.apiKey",
          },
        ],
        productCategory: "llm_auth_or_config",
        recoveryActions: ["open_settings", "export_diagnostics"],
        severity: "action_required",
      },
      message: "settings config update is invalid",
      retryable: false,
    };
    const api = settingsApi({
      updateError: new ApiClientError({
        method: "PATCH",
        path: "/api/v1/settings/config",
        responseBody: {
          data: null,
          error: apiError,
          ok: false,
        },
        status: 400,
      }),
    });

    renderWithQueryClient(
      <SettingsRoute api={api} runtimeEnv={{ VITE_PLATO_API_MODE: "http" }} />,
    );

    await user.clear(await screen.findByLabelText("API key"));
    await user.type(screen.getByLabelText("API key"), "sk-failing-secret");
    await user.click(screen.getByRole("button", { name: "Save and check" }));

    expect(
      await screen.findByText("settings config update is invalid"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("an API key is required for the selected provider"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("API key")).toHaveValue("");
    expect(document.body).not.toHaveTextContent("sk-failing-secret");
  });

  it("exports diagnostics when a sidecar session is available", async () => {
    const user = userEvent.setup();
    const api = settingsApi();

    renderWithQueryClient(
      <SettingsRoute api={api} runtimeEnv={{ VITE_PLATO_API_MODE: "http" }} />,
    );

    await screen.findByDisplayValue("anthropic/test-model");
    await user.click(screen.getByRole("button", { name: "Export diagnostics" }));

    expect(await screen.findByText("diagnostic-bundle-session-1")).toBeInTheDocument();
    expect(api.exportDiagnosticBundle).toHaveBeenCalledWith("session-1");
  });
});

function renderWithQueryClient(children: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>,
  );
}

function settingsApi({
  config = settingsConfig({ apiKeyConfigured: true }),
  readiness = settingsReadiness({ ready: true }),
  updateError,
}: {
  config?: SettingsConfigSummary;
  readiness?: SettingsReadinessReport;
  updateError?: Error;
} = {}): SettingsRouteApi {
  return {
    exportDiagnosticBundle: vi.fn(async () => okResponse(diagnosticExport())),
    getSettingsConfig: vi.fn(async () => okResponse(config)),
    listSessions: vi.fn(async () =>
      okResponse({
        sessions: [
          {
            createdAt: "2026-06-06T09:00:00Z",
            id: "session-1",
            name: "Diagnostics smoke",
            projectId: "local",
            status: "running" as const,
            updatedAt: "2026-06-06T09:00:00Z",
            workflowId: "authoring",
          },
        ],
      }),
    ),
    recheckSettingsReadiness: vi.fn(async () => okResponse(readiness)),
    updateSettingsConfig: vi.fn(async () => {
      if (updateError !== undefined) {
        throw updateError;
      }
      return okResponse({
        config: settingsConfig({ apiKeyConfigured: true }),
        readiness,
        schemaVersion: "plato.settings_config_update.v1",
        updatedAt: "2026-06-06T09:01:00Z",
      } satisfies SettingsConfigUpdateResult);
    }),
  };
}

function okResponse<T>(data: T): QueryResponse<T> {
  return {
    data,
    error: null,
    generatedAt: "2026-06-06T09:00:00Z",
    ok: true,
    requestId: "settings-test",
  };
}

function settingsConfig({
  apiKeyConfigured,
}: {
  apiKeyConfigured: boolean;
}): SettingsConfigSummary {
  return {
    diagnostics: {
      bundleExportAvailable: true,
      httpExportRouteAvailable: true,
    },
    generatedAt: "2026-06-06T09:00:00Z",
    llm: {
      apiKeyConfigured,
      apiKeyEnvVar: "LLM_API_KEY",
      apiKeySource: apiKeyConfigured ? "stored" : "none",
      model: "anthropic/test-model",
      modelSource: "stored",
      provider: "litellm",
      providerOptions: [
        {
          id: "litellm",
          label: "LiteLLM",
          preferredApiKeyEnvVar: "LLM_API_KEY",
          requiredApiKeyEnvVars: ["LLM_API_KEY"],
        },
        {
          id: "deepseek",
          label: "DeepSeek",
          preferredApiKeyEnvVar: "DEEPSEEK_API_KEY",
          requiredApiKeyEnvVars: ["DEEPSEEK_API_KEY", "LLM_API_KEY"],
        },
      ],
      providerSource: "stored",
    },
    logging: {
      defaultProfile: "normal",
      enabled: true,
      level: "INFO",
      profiles: [
        {
          description: "Record normal summaries.",
          id: "normal",
        },
      ],
      selectedProfile: "normal",
      selectedProfileKnown: true,
      selectedProfileSource: "stored",
    },
    schemaVersion: "plato.settings_config.v1",
    workspaceRootLabel: "workspace://current",
  };
}

function settingsReadiness({
  ready,
}: {
  ready: boolean;
}): SettingsReadinessReport {
  return {
    blockingIssues: ready
      ? []
      : [
          {
            code: "llm.missing_api_key",
            envVars: ["LLM_API_KEY"],
            message: "LLM API key configuration is missing.",
            recoveryActions: ["open_settings"],
            severity: "blocking",
          },
        ],
    diagnostics: {
      bundleExportAvailable: true,
      cliCommandTemplate:
        "uv run taskweavn diagnostics export --workspace <workspace> --session-id <sessionId> --output <dir>",
      httpExportRouteAvailable: true,
    },
    firstRun: {
      blockingIssueCodes: ready ? [] : ["llm.missing_api_key"],
      ready,
      recommendedActions: ready ? ["none"] : ["open_settings"],
    },
    generatedAt: "2026-06-06T09:02:00Z",
    llm: {
      apiKeyConfigured: ready,
      configured: ready,
      missingEnvVars: ready ? [] : ["LLM_API_KEY"],
      model: "anthropic/test-model",
      modelSource: "env",
      provider: "litellm",
      providerSource: "env",
      requestTimeoutConfigured: false,
      requestTimeoutSeconds: 180,
      requestTimeoutValid: true,
      thinking: {
        configured: false,
      },
    },
    logging: {
      defaultProfile: "normal",
      enabled: true,
      level: "INFO",
      profiles: [],
      selectedProfile: null,
      selectedProfileKnown: true,
    },
    schemaVersion: "plato.settings_readiness.v1",
    status: ready ? "ready" : "needs_configuration",
    warnings: [],
    workspaceRootLabel: "workspace://current",
  };
}

function diagnosticExport(): DiagnosticBundleExportResult {
  return {
    bundleDir: "/tmp/bundle",
    bundleDirLabel: "workspace://current/.plato/diagnostics/bundle",
    bundleId: "diagnostic-bundle-session-1",
    createdAt: "2026-06-06T09:03:00Z",
    fileCount: 3,
    includedSections: ["session"],
    manifestPath: "/tmp/bundle/manifest.json",
    manifestPathLabel: "workspace://current/.plato/diagnostics/manifest.json",
    redactionProfile: "product_1_0_default",
    schemaVersion: "plato.diagnostics_export.v1",
    sections: [],
    warnings: [],
    zipPath: "/tmp/bundle.zip",
    zipPathLabel: "workspace://current/.plato/diagnostics/bundle.zip",
  };
}
