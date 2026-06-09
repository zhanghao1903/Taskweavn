import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  FirstRunReadinessGate,
  type SettingsReadinessApi,
} from "./FirstRunReadinessGate";
import type { SettingsReadinessReport } from "../../shared/api/platoApi";
import type { QueryResponse } from "../../shared/api/types";

describe("FirstRunReadinessGate", () => {
  afterEach(() => {
    globalThis.history.pushState(null, "", "/");
  });

  it("bypasses readiness checks outside HTTP runtime mode", () => {
    renderWithQueryClient(
      <FirstRunReadinessGate runtimeEnv={{ VITE_PLATO_API_MODE: "mock" }}>
        <div>Main Page Ready</div>
      </FirstRunReadinessGate>,
    );

    expect(screen.getByText("Main Page Ready")).toBeInTheDocument();
  });

  it("renders first-run blockers without exposing secret values", async () => {
    const api: SettingsReadinessApi = {
      getSettingsReadiness: vi.fn(async () => okResponse(blockedReadiness())),
    };

    renderWithQueryClient(
      <FirstRunReadinessGate api={api}>
        <div>Main Page Ready</div>
      </FirstRunReadinessGate>,
    );

    expect(
      await screen.findByRole("heading", { name: "Setup required" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Main Page Ready")).not.toBeInTheDocument();
    expect(screen.getByText("deepseek")).toBeInTheDocument();
    expect(screen.getByText("DEEPSEEK_API_KEY")).toBeInTheDocument();
    expect(screen.getByText("LLM_API_KEY")).toBeInTheDocument();
    expect(screen.getByText("Configure local provider settings.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Configure settings" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("sk-secret");
  });

  it("opens the Settings route from the first-run blocker", async () => {
    const user = userEvent.setup();
    const api: SettingsReadinessApi = {
      getSettingsReadiness: vi.fn(async () => okResponse(blockedReadiness())),
    };

    renderWithQueryClient(
      <FirstRunReadinessGate api={api}>
        <div>Main Page Ready</div>
      </FirstRunReadinessGate>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Configure settings" }),
    );

    expect(globalThis.location.pathname).toBe("/settings");
    expect(globalThis.location.search).toBe("?source=first-run&returnTo=%2F");
  });

  it("continues to the Main Page when first-run readiness is satisfied", async () => {
    const api: SettingsReadinessApi = {
      getSettingsReadiness: vi.fn(async () => okResponse(readyReadiness())),
    };

    renderWithQueryClient(
      <FirstRunReadinessGate api={api}>
        <div>Main Page Ready</div>
      </FirstRunReadinessGate>,
    );

    expect(await screen.findByText("Main Page Ready")).toBeInTheDocument();
    expect(screen.queryByText("Setup required")).not.toBeInTheDocument();
  });

  it("shows degraded readiness as a non-blocking warning", async () => {
    const api: SettingsReadinessApi = {
      getSettingsReadiness: vi.fn(async () => okResponse(degradedReadiness())),
    };

    renderWithQueryClient(
      <FirstRunReadinessGate api={api}>
        <div>Main Page Ready</div>
      </FirstRunReadinessGate>,
    );

    expect(await screen.findByText("Main Page Ready")).toBeInTheDocument();
    expect(screen.getByText("Setup warning")).toBeInTheDocument();
    expect(screen.getByText("Session logging is disabled.")).toBeInTheDocument();
  });

  it("shows a retryable state when the readiness route is unavailable", async () => {
    const user = userEvent.setup();
    const api: SettingsReadinessApi = {
      getSettingsReadiness: vi
        .fn<SettingsReadinessApi["getSettingsReadiness"]>()
        .mockRejectedValueOnce(new Error("sidecar unavailable"))
        .mockResolvedValueOnce(okResponse(readyReadiness())),
    };

    renderWithQueryClient(
      <FirstRunReadinessGate api={api}>
        <div>Main Page Ready</div>
      </FirstRunReadinessGate>,
    );

    expect(
      await screen.findByRole("heading", { name: "Setup check unavailable" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry check" }));

    expect(await screen.findByText("Main Page Ready")).toBeInTheDocument();
    expect(api.getSettingsReadiness).toHaveBeenCalledTimes(2);
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

function okResponse(
  data: SettingsReadinessReport,
): QueryResponse<SettingsReadinessReport> {
  return {
    data,
    error: null,
    generatedAt: data.generatedAt,
    ok: true,
    requestId: "settings-readiness",
  };
}

function blockedReadiness(): SettingsReadinessReport {
  return {
    ...readyReadiness(),
    blockingIssues: [
      {
        code: "llm.missing_api_key",
        envVars: ["DEEPSEEK_API_KEY", "LLM_API_KEY"],
        message: "LLM API key configuration is missing.",
        recoveryActions: ["open_settings"],
        severity: "blocking",
      },
    ],
    firstRun: {
      blockingIssueCodes: ["llm.missing_api_key"],
      ready: false,
      recommendedActions: ["open_settings"],
    },
    llm: {
      ...readyReadiness().llm,
      apiKeyConfigured: false,
      configured: false,
      missingEnvVars: ["DEEPSEEK_API_KEY", "LLM_API_KEY"],
    },
    status: "needs_configuration",
  };
}

function readyReadiness(): SettingsReadinessReport {
  return {
    blockingIssues: [],
    diagnostics: {
      bundleExportAvailable: true,
      cliCommandTemplate:
        "uv run taskweavn diagnostics export --workspace <workspace> --session-id <sessionId> --output <dir>",
      httpExportRouteAvailable: true,
    },
    firstRun: {
      blockingIssueCodes: [],
      ready: true,
      recommendedActions: ["none"],
    },
    generatedAt: "2026-06-05T12:00:00Z",
    llm: {
      apiKeyConfigured: true,
      configured: true,
      missingEnvVars: [],
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
    status: "ready",
    warnings: [],
    workspaceRootLabel: "workspace://current",
  };
}

function degradedReadiness(): SettingsReadinessReport {
  return {
    ...readyReadiness(),
    status: "degraded",
    warnings: [
      {
        code: "logging.disabled",
        envVars: [],
        message: "Session logging is disabled.",
        recoveryActions: ["open_settings"],
        severity: "warning",
      },
    ],
  };
}
