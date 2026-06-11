import type { AuditMockScenarioId } from "../pages/audit-page/mockAuditScenarios";
import {
  createAuditMockApi,
  type AuditMockApi,
} from "../pages/audit-page/mockAuditApi";
import { createHttpMainPageAdapter } from "../pages/main-page/httpMainPageAdapter";
import { createMainPageMockAdapter } from "../pages/main-page/mockPlatoApi";
import {
  routeMainPageEventWithReducerCompatibility,
  type MainPageEventCompatibilityResult,
} from "../pages/main-page/runtime/eventRouterCompatibility";
import {
  createMainPageMockRuntimeFacade,
  type MainPageMockRuntimeFacade,
} from "../pages/main-page/runtime/mockRuntimeFacade";
import type { MainPageAdapter } from "../pages/main-page/runtime/adapter";
import type { UiEvent } from "../shared/api/types";
import {
  createHttpPlatoApi,
  type EventSourceLike,
} from "../shared/api/platoApi";
import {
  configureFrontendLogSink,
  createFrontendLogger,
  type FrontendLogEntry,
} from "../shared/logging/frontendLogger";

export type PlatoRuntimeEnv = {
  VITE_PLATO_API_BASE_URL?: string;
  VITE_PLATO_LOG_LEVEL?: "debug" | "info" | "warn" | "error" | "silent";
  VITE_PLATO_API_MODE?: "mock" | "http";
  VITE_PLATO_SESSION_ID?: string;
  VITE_PLATO_DISABLE_EVENTS?: "0" | "1";
  VITE_PLATO_AUDIT_MOCK_SCENARIO?: AuditMockScenarioId;
  VITE_PLATO_RUNTIME_REDUCER_HARNESS?: "off" | "test";
  VITE_PLATO_UI_LOCALE?: string;
};

export type PlatoWorkspaceEntryRuntime = {
  bridge: PlatoElectronWorkspaceBridge | null;
  currentWorkspace: PlatoWorkspaceEntrySummary | null;
  isRequired: boolean;
};

const runtimeLogger = createFrontendLogger("runtime");

export function resolvePlatoRuntimeEnv(
  env: PlatoRuntimeEnv = import.meta.env,
): PlatoRuntimeEnv {
  const electronRuntime = globalThis.window?.platoRuntimeConfig;
  if (!electronRuntime) {
    return env;
  }

  return {
    ...env,
    VITE_PLATO_API_BASE_URL:
      electronRuntime.apiBaseUrl ?? env.VITE_PLATO_API_BASE_URL,
    VITE_PLATO_API_MODE: electronRuntime.apiMode ?? env.VITE_PLATO_API_MODE,
    VITE_PLATO_DISABLE_EVENTS:
      electronRuntime.disableEvents === true
        ? "1"
        : env.VITE_PLATO_DISABLE_EVENTS,
    VITE_PLATO_SESSION_ID:
      electronRuntime.sessionId ?? env.VITE_PLATO_SESSION_ID,
    VITE_PLATO_UI_LOCALE:
      electronRuntime.uiLocale ?? env.VITE_PLATO_UI_LOCALE,
  };
}

export function resolvePlatoWorkspaceEntryRuntime(): PlatoWorkspaceEntryRuntime {
  const electronRuntime = globalThis.window?.platoRuntimeConfig;
  return {
    bridge: globalThis.window?.platoElectronWorkspace ?? null,
    currentWorkspace: electronRuntime?.workspace ?? null,
    isRequired: electronRuntime?.workspaceEntryRequired === true,
  };
}

export function createMainPageAdapterFromRuntimeEnv(
  env: PlatoRuntimeEnv = import.meta.env,
  options: {
    sessionId?: string | null;
    workspaceId?: string | null;
  } = {},
): MainPageAdapter | undefined {
  const runtimeEnv = resolvePlatoRuntimeEnv(env);
  if (runtimeEnv.VITE_PLATO_API_MODE !== "http") {
    configureFrontendLogSink(null);
    runtimeLogger.info("main-page.adapter.mock", {
      mode: runtimeEnv.VITE_PLATO_API_MODE ?? "mock",
    });
    return createMainPageMockAdapter({
      showStatePicker: false,
    });
  }

  const sessionId = options.sessionId ?? runtimeEnv.VITE_PLATO_SESSION_ID;
  const baseUrl = runtimeEnv.VITE_PLATO_API_BASE_URL ?? globalThis.location.origin;
  configureFrontendLogSink(
    sessionId ? createHttpErrorLogSink(baseUrl, sessionId) : null,
  );

  runtimeLogger.info("main-page.adapter.http", {
    baseUrl,
    logLevel: runtimeEnv.VITE_PLATO_LOG_LEVEL ?? "default",
    sessionId: sessionId ?? null,
  });

  return createHttpMainPageAdapter({
    api: createHttpPlatoApi({
      baseUrl,
      eventSourceFactory:
        runtimeEnv.VITE_PLATO_DISABLE_EVENTS === "1"
          ? createNoopEventSource
          : undefined,
    }),
    liveLabel: "Live Session",
    sessionId: sessionId ?? null,
    workspaceId: options.workspaceId ?? null,
  });
}

function createNoopEventSource(): EventSourceLike {
  return {
    addEventListener() {
      return undefined;
    },
    close() {
      return undefined;
    },
  };
}

export function createAuditApiFromRuntimeEnv(
  env: PlatoRuntimeEnv = import.meta.env,
): AuditMockApi {
  const runtimeEnv = resolvePlatoRuntimeEnv(env);
  if (runtimeEnv.VITE_PLATO_API_MODE === "http") {
    const baseUrl = runtimeEnv.VITE_PLATO_API_BASE_URL ?? globalThis.location.origin;

    runtimeLogger.info("audit.adapter.http", {
      baseUrl,
      sessionId: runtimeEnv.VITE_PLATO_SESSION_ID ?? null,
    });

    return createHttpPlatoApi({ baseUrl });
  }

  const scenarioId =
    runtimeEnv.VITE_PLATO_AUDIT_MOCK_SCENARIO ?? "a3-records-ready";
  runtimeLogger.info("audit.adapter.mock", {
    scenarioId,
  });

  return createAuditMockApi(scenarioId);
}

export type MainPageRuntimeReducerHarness = {
  facade: MainPageMockRuntimeFacade;
  routeEvent: (event: UiEvent) => MainPageEventCompatibilityResult;
};

export function createMainPageRuntimeReducerHarnessFromEnv(
  env: PlatoRuntimeEnv = import.meta.env,
): MainPageRuntimeReducerHarness | null {
  const runtimeEnv = resolvePlatoRuntimeEnv(env);
  if (runtimeEnv.VITE_PLATO_RUNTIME_REDUCER_HARNESS !== "test") {
    return null;
  }

  runtimeLogger.info("main-page.runtime-reducer-harness.enabled", {
    mode: runtimeEnv.VITE_PLATO_RUNTIME_REDUCER_HARNESS,
  });

  const facade = createMainPageMockRuntimeFacade();

  return {
    facade,
    routeEvent(event) {
      return routeMainPageEventWithReducerCompatibility(facade, event);
    },
  };
}

function createHttpErrorLogSink(
  baseUrl: string,
  sessionId: string,
): (entry: FrontendLogEntry) => void {
  const normalizedBaseUrl = baseUrl.replace(/\/$/, "");
  const url = `${normalizedBaseUrl}/api/v1/sessions/${encodeURIComponent(
    sessionId,
  )}/client-logs/errors`;

  return (entry) => {
    void globalThis
      .fetch(url, {
        body: JSON.stringify({ entry }),
        headers: {
          "Content-Type": "application/json",
        },
        keepalive: true,
        method: "POST",
      })
      .catch(() => {
        // File logging is diagnostic only; never break the UI because the
        // diagnostic channel itself is unavailable.
      });
  };
}
