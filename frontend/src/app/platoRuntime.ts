import type { AuditMockScenarioId } from "../pages/audit-page/mockAuditScenarios";
import {
  createAuditMockApi,
  type AuditMockApi,
} from "../pages/audit-page/mockAuditApi";
import { createHttpMainPageAdapter } from "../pages/main-page/httpMainPageAdapter";
import type { MainPageAdapter } from "../pages/main-page/runtime/adapter";
import { createHttpPlatoApi } from "../shared/api/platoApi";
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
  VITE_PLATO_AUDIT_MOCK_SCENARIO?: AuditMockScenarioId;
};

const runtimeLogger = createFrontendLogger("runtime");

export function createMainPageAdapterFromRuntimeEnv(
  env: PlatoRuntimeEnv = import.meta.env,
): MainPageAdapter | undefined {
  if (env.VITE_PLATO_API_MODE !== "http") {
    configureFrontendLogSink(null);
    runtimeLogger.info("main-page.adapter.mock", {
      mode: env.VITE_PLATO_API_MODE ?? "mock",
    });
    return undefined;
  }

  const sessionId = env.VITE_PLATO_SESSION_ID;
  const baseUrl = env.VITE_PLATO_API_BASE_URL ?? globalThis.location.origin;
  configureFrontendLogSink(
    sessionId ? createHttpErrorLogSink(baseUrl, sessionId) : null,
  );

  runtimeLogger.info("main-page.adapter.http", {
    baseUrl,
    logLevel: env.VITE_PLATO_LOG_LEVEL ?? "default",
    sessionId: sessionId ?? null,
  });

  return createHttpMainPageAdapter({
    api: createHttpPlatoApi({
      baseUrl,
    }),
    liveLabel: "Live Session",
    sessionId: sessionId ?? null,
  });
}

export function createAuditApiFromRuntimeEnv(
  env: PlatoRuntimeEnv = import.meta.env,
): AuditMockApi {
  if (env.VITE_PLATO_API_MODE === "http") {
    const baseUrl = env.VITE_PLATO_API_BASE_URL ?? globalThis.location.origin;

    runtimeLogger.info("audit.adapter.http", {
      baseUrl,
      sessionId: env.VITE_PLATO_SESSION_ID ?? null,
    });

    return createHttpPlatoApi({ baseUrl });
  }

  const scenarioId = env.VITE_PLATO_AUDIT_MOCK_SCENARIO ?? "a3-records-ready";
  runtimeLogger.info("audit.adapter.mock", {
    scenarioId,
  });

  return createAuditMockApi(scenarioId);
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
