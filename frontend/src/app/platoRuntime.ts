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
