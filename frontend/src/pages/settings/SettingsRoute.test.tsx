import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PLATO_NAVIGATION_EVENT } from "../../app/navigation";
import { ApiClientError } from "../../shared/api/client";
import type {
  DiagnosticBundleExportResult,
  SettingsConfigSummary,
  SettingsConfigUpdateResult,
  SettingsReadinessReport,
} from "../../shared/api/platoApi";
import type {
  TokenUsageSummary,
  TokenUsageSummaryResponse,
  UsageAggregationDimension,
} from "../../shared/api/tokenUsageTypes";
import type { ApiError, QueryResponse } from "../../shared/api/types";
import {
  UI_LOCALE_PREFERENCE_STORAGE_KEY,
  UiTextProvider,
  type UiLocale,
} from "../../shared/ui-text";
import { WORKSPACE_GIT_INITIALIZE_ON_OPEN_STORAGE_KEY as WORKSPACE_GIT_STORAGE_KEY } from "../../shared/workspace/workspaceGitPreference";
import { SettingsRoute, type SettingsRouteApi } from "./SettingsRoute";

describe("SettingsRoute", () => {
  beforeEach(() => {
    installTestLocalStorage();
  });

  afterEach(() => {
    globalThis.history.pushState(null, "", "/");
    globalThis.localStorage?.clear();
    vi.restoreAllMocks();
  });

  it("loads safe config without exposing stored secret values", async () => {
    renderWithQueryClient(
      <SettingsRoute api={settingsApi()} runtimeEnv={{ VITE_PLATO_API_MODE: "http" }} />,
    );

    expect(await screen.findByDisplayValue("deepseek-v4-pro")).toBeInTheDocument();
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
          provider: "deepseek",
        },
        logging: {
          selectedProfile: "normal",
        },
        webSearch: {
          enabled: false,
          maxResults: 5,
          mode: "basic",
          provider: "tavily",
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

    await screen.findByDisplayValue("deepseek-v4-pro");
    await user.click(screen.getByRole("button", { name: "Export diagnostics" }));

    expect(await screen.findByText("diagnostic-bundle-session-1")).toBeInTheDocument();
    expect(api.exportDiagnosticBundle).toHaveBeenCalledWith("session-1");
  });

  it("renders core Settings chrome in zh-CN", async () => {
    renderWithQueryClient(
      <SettingsRoute api={settingsApi()} runtimeEnv={{ VITE_PLATO_API_MODE: "http" }} />,
      { locale: "zh-CN" },
    );

    expect(await screen.findByRole("heading", { name: "设置" })).toBeInTheDocument();
    expect(screen.getByText("已配置")).toBeInTheDocument();
    expect(screen.getByLabelText("服务商")).toBeInTheDocument();
    expect(screen.getByLabelText("API 密钥")).toBeInTheDocument();
    expect(screen.getByLabelText("网页搜索 API 密钥")).toBeInTheDocument();
    expect(screen.getByLabelText("界面语言")).toBeInTheDocument();
    expect(screen.getByLabelText("工作区 Git")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存并检查" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出诊断" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("Interface language");
  });

  it("keeps a selected logging profile visible even when it is not in the profile list", async () => {
    renderWithQueryClient(
      <SettingsRoute
        api={settingsApi({
          config: settingsConfig({
            apiKeyConfigured: true,
            loggingProfiles: ["normal"],
            selectedProfile: "full-debug",
          }),
        })}
        runtimeEnv={{ VITE_PLATO_API_MODE: "http" }}
      />,
    );

    expect(await screen.findByLabelText("Logging profile")).toHaveValue("full-debug");
    expect(screen.getByRole("option", { name: "full-debug" })).toBeInTheDocument();
  });

  it("persists the UI language preference from Settings", async () => {
    const user = userEvent.setup();

    renderWithQueryClient(
      <SettingsRoute api={settingsApi()} runtimeEnv={{ VITE_PLATO_API_MODE: "http" }} />,
    );

    await screen.findByDisplayValue("deepseek-v4-pro");
    await user.selectOptions(
      screen.getByLabelText("Interface language"),
      "zh-CN",
    );

    expect(
      globalThis.localStorage.getItem(UI_LOCALE_PREFERENCE_STORAGE_KEY),
    ).toBe("zh-CN");
    expect(screen.getByLabelText("Interface language")).toHaveValue("zh-CN");
  });

  it("saves global Web Search configuration without keeping the secret visible", async () => {
    const user = userEvent.setup();
    const api = settingsApi({
      config: settingsConfig({
        apiKeyConfigured: true,
        webSearchApiKeyConfigured: false,
      }),
    });

    renderWithQueryClient(
      <SettingsRoute api={api} runtimeEnv={{ VITE_PLATO_API_MODE: "http" }} />,
    );

    await user.click(await screen.findByRole("checkbox", { name: "Web Search" }));
    await user.selectOptions(screen.getByLabelText("Result limit"), "4");
    await user.type(screen.getByLabelText("Web Search API key"), "tvly-route-secret");
    await user.click(screen.getByRole("button", { name: "Save and check" }));

    await waitFor(() => {
      expect(api.updateSettingsConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          webSearch: {
            apiKey: "tvly-route-secret",
            enabled: true,
            maxResults: 4,
            mode: "basic",
            provider: "tavily",
          },
        }),
      );
    });
    expect(document.body).not.toHaveTextContent("tvly-route-secret");
  });

  it("defaults workspace Git initialization on when Git is available", async () => {
    const setGitPreference = vi.fn(async (value: PlatoWorkspaceGitPreference) => value);
    const workspaceBridge = workspaceBridgeFor({
      getGitPreference: vi.fn(async () => ({ initializeGitOnOpen: null })),
      getGitStatus: vi.fn(async () => ({
        status: "available" as const,
        version: "git version 2.45.0",
      })),
      setGitPreference,
    });

    renderWithQueryClient(
      <SettingsRoute
        api={settingsApi()}
        runtimeEnv={{ VITE_PLATO_API_MODE: "http" }}
        workspaceBridge={workspaceBridge}
      />,
    );

    expect(
      await screen.findByText("Git available: git version 2.45.0"),
    ).toBeInTheDocument();

    const checkbox = screen.getByRole("checkbox", {
      name: "Initialize Git for opened workspaces",
    });
    await waitFor(() => {
      expect(checkbox).toBeChecked();
    });
    expect(globalThis.localStorage.getItem(WORKSPACE_GIT_STORAGE_KEY)).toBe("1");
    expect(setGitPreference).toHaveBeenCalledWith({ initializeGitOnOpen: true });
  });

  it("persists an explicit workspace Git initialization opt-out", async () => {
    const user = userEvent.setup();
    const setGitPreference = vi.fn(async (value: PlatoWorkspaceGitPreference) => value);
    const workspaceBridge = workspaceBridgeFor({
      getGitPreference: vi.fn(async () => ({ initializeGitOnOpen: false })),
      getGitStatus: vi.fn(async () => ({
        status: "available" as const,
        version: "git version 2.45.0",
      })),
      setGitPreference,
    });

    renderWithQueryClient(
      <SettingsRoute
        api={settingsApi()}
        runtimeEnv={{ VITE_PLATO_API_MODE: "http" }}
        workspaceBridge={workspaceBridge}
      />,
    );

    expect(
      await screen.findByText("Git available: git version 2.45.0"),
    ).toBeInTheDocument();

    const checkbox = screen.getByRole("checkbox", {
      name: "Initialize Git for opened workspaces",
    });
    expect(checkbox).not.toBeChecked();
    await user.click(checkbox);

    expect(checkbox).toBeChecked();
    expect(globalThis.localStorage.getItem(WORKSPACE_GIT_STORAGE_KEY)).toBe("1");
    expect(setGitPreference).toHaveBeenCalledWith({ initializeGitOnOpen: true });
  });

  it("disables workspace Git initialization when Git is unavailable", async () => {
    const workspaceBridge = workspaceBridgeFor({
      getGitStatus: vi.fn(async () => ({ status: "missing" as const })),
    });

    renderWithQueryClient(
      <SettingsRoute
        api={settingsApi()}
        runtimeEnv={{ VITE_PLATO_API_MODE: "http" }}
        workspaceBridge={workspaceBridge}
      />,
    );

    expect(await screen.findByText("Git not found")).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", {
        name: "Initialize Git for opened workspaces",
      }),
    ).toBeDisabled();
  });

  it("manages workspace archive, restore, and Plato data deletion in the data tab", async () => {
    const user = userEvent.setup();
    const activeWorkspace = workspaceEntry("workspace-active", "Active Project");
    const archivedWorkspace = {
      ...workspaceEntry("workspace-archived", "Archived Project"),
      lifecycleStatus: "archived" as const,
    };
    const dataState: PlatoWorkspaceEntryState = {
      archivedWorkspaces: [archivedWorkspace],
      currentWorkspace: activeWorkspace,
      error: null,
      recentWorkspaces: [],
      status: "ready",
    };
    const archiveWorkspace = vi.fn(async () => ({
      state: dataState,
      status: "ok" as const,
    }));
    const deleteWorkspaceData = vi.fn(async () => ({
      state: dataState,
      status: "ok" as const,
    }));
    const restoreWorkspace = vi.fn(async () => ({
      state: dataState,
      status: "ok" as const,
    }));
    const api = settingsApi();

    renderWithQueryClient(
      <SettingsRoute
        api={api}
        location={{ pathname: "/settings", search: "?tab=data" }}
        runtimeEnv={{ VITE_PLATO_API_MODE: "http" }}
        workspaceBridge={workspaceBridgeFor({
          archiveWorkspace,
          deleteWorkspaceData,
          getState: vi.fn(async () => dataState),
          restoreWorkspace,
        })}
      />,
    );

    expect((await screen.findAllByText("Active Project")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Archived Project").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Archive workspace" }));
    expect(archiveWorkspace).toHaveBeenCalledWith("workspace-active");

    await user.click(screen.getByRole("button", { name: "Restore workspace" }));
    expect(restoreWorkspace).toHaveBeenCalledWith("workspace-archived");

    await user.click(screen.getAllByRole("button", { name: "Delete Plato data" })[0]);
    const dialog = screen.getByRole("alertdialog");
    await user.click(
      within(dialog).getByRole("button", { name: "Delete Plato data" }),
    );

    expect(deleteWorkspaceData).toHaveBeenCalledWith("workspace-active");
  });

  it("switches Settings tabs through client navigation", async () => {
    const user = userEvent.setup();
    const handleNavigation = vi.fn();
    globalThis.history.pushState(null, "", "/settings");
    globalThis.addEventListener(PLATO_NAVIGATION_EVENT, handleNavigation);

    try {
      renderWithQueryClient(
        <SettingsRoute
          api={settingsApi()}
          runtimeEnv={{ VITE_PLATO_API_MODE: "http" }}
        />,
      );

      await user.click(await screen.findByRole("link", { name: "Data Management" }));

      expect(globalThis.location.pathname).toBe("/settings");
      expect(globalThis.location.search).toBe("?tab=data");
      expect(handleNavigation).toHaveBeenCalledTimes(1);
    } finally {
      globalThis.removeEventListener(PLATO_NAVIGATION_EVENT, handleNavigation);
    }
  });
});

function renderWithQueryClient(
  children: ReactNode,
  options: { locale?: UiLocale } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <UiTextProvider locale={options.locale ?? "en-US"}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </UiTextProvider>,
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
    getTokenUsageSummary: vi.fn(async (request) =>
      okResponse(tokenUsageSummary(request.dimension)),
    ),
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
  loggingProfiles = ["normal"],
  selectedProfile = "normal",
  webSearchApiKeyConfigured = false,
  webSearchEnabled = false,
}: {
  apiKeyConfigured: boolean;
  loggingProfiles?: string[];
  selectedProfile?: string | null;
  webSearchApiKeyConfigured?: boolean;
  webSearchEnabled?: boolean;
}): SettingsConfigSummary {
  return {
    diagnostics: {
      bundleExportAvailable: true,
      httpExportRouteAvailable: true,
    },
    generatedAt: "2026-06-06T09:00:00Z",
    llm: {
      apiKeyConfigured,
      apiKeyEnvVar: "DEEPSEEK_API_KEY",
      apiKeySource: apiKeyConfigured ? "stored" : "none",
      model: "deepseek-v4-pro",
      modelSource: "stored",
      provider: "deepseek",
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
    webSearch: {
      apiKeyConfigured: webSearchApiKeyConfigured,
      apiKeyEnvVar: "TAVILY_API_KEY",
      apiKeySource: webSearchApiKeyConfigured ? "stored" : "none",
      enabled: webSearchEnabled,
      maxResults: 5,
      mode: "basic",
      provider: "tavily",
      providerOptions: [
        {
          id: "tavily",
          label: "Tavily",
          preferredApiKeyEnvVar: "TAVILY_API_KEY",
          requiredApiKeyEnvVars: ["TAVILY_API_KEY"],
        },
      ],
      providerSource: webSearchEnabled ? "stored" : "default",
      status: webSearchEnabled
        ? webSearchApiKeyConfigured
          ? "ready"
          : "missing_key"
        : "disabled",
    },
    logging: {
      defaultProfile: "normal",
      enabled: true,
      level: "INFO",
      profiles: loggingProfiles.map((profile) => ({
        description: `Record ${profile} summaries.`,
        id: profile,
      })),
      selectedProfile,
      selectedProfileKnown:
        selectedProfile === null ? true : loggingProfiles.includes(selectedProfile),
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
            envVars: ["DEEPSEEK_API_KEY", "LLM_API_KEY"],
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
      missingEnvVars: ready ? [] : ["DEEPSEEK_API_KEY", "LLM_API_KEY"],
      model: "deepseek-v4-pro",
      modelSource: "env",
      provider: "deepseek",
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

function workspaceBridgeFor(
  overrides: Partial<PlatoElectronWorkspaceBridge> = {},
): PlatoElectronWorkspaceBridge {
  return {
    chooseWorkspace: vi.fn(async () => ({
      state: workspaceEntryState(),
      status: "ready" as const,
    })),
    getGitStatus: vi.fn(async () => ({
      status: "available" as const,
      version: "git version 2.45.0",
    })),
    getState: vi.fn(async () => workspaceEntryState()),
    useWorkspace: vi.fn(async () => ({
      state: workspaceEntryState(),
      status: "ready" as const,
    })),
    ...overrides,
  };
}

function workspaceEntryState(): PlatoWorkspaceEntryState {
  return {
    archivedWorkspaces: [],
    currentWorkspace: null,
    error: null,
    recentWorkspaces: [],
    status: "ready",
  };
}

function workspaceEntry(
  id: string,
  name: string,
): PlatoWorkspaceEntrySummary {
  return {
    id,
    isCurrent: id === "workspace-active",
    label: name,
    name,
    pathLabel: name,
  };
}

function tokenUsageSummary(
  dimension: UsageAggregationDimension,
): TokenUsageSummaryResponse {
  const totals: TokenUsageSummary = {
    cacheHitRatio: 0.4,
    cacheHitTokens: 20,
    cacheMissTokens: 30,
    cacheRateSource: "hit_miss_tokens",
    cachedTokens: 20,
    callCount: 1,
    dimension,
    firstOccurredAt: "2026-06-06T09:00:00Z",
    id: `${dimension}-total`,
    inputTokens: 40,
    label: `${dimension} usage`,
    lastOccurredAt: "2026-06-06T09:00:00Z",
    outputTokens: 10,
    reasoningTokens: null,
    totalTokens: 50,
    unknownUsageCallCount: 0,
    workspaceId: "workspace-1",
  };
  return {
    dimension,
    rows: [totals],
    totals,
  };
}

function installTestLocalStorage(): void {
  const storage = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      clear: () => storage.clear(),
      getItem: (key: string) => storage.get(key) ?? null,
      key: (index: number) => Array.from(storage.keys())[index] ?? null,
      get length() {
        return storage.size;
      },
      removeItem: (key: string) => storage.delete(key),
      setItem: (key: string, value: string) => storage.set(key, value),
    },
  });
}
