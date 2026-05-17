import { createHttpMainPageAdapter } from "../pages/main-page/httpMainPageAdapter";
import type { MainPageAdapter } from "../pages/main-page/mockPlatoApi";
import { createHttpPlatoApi } from "../shared/api/platoApi";

export type PlatoRuntimeEnv = {
  VITE_PLATO_API_BASE_URL?: string;
  VITE_PLATO_API_MODE?: "mock" | "http";
  VITE_PLATO_SESSION_ID?: string;
};

export function createMainPageAdapterFromRuntimeEnv(
  env: PlatoRuntimeEnv = import.meta.env,
): MainPageAdapter | undefined {
  if (env.VITE_PLATO_API_MODE !== "http") {
    return undefined;
  }

  const sessionId = env.VITE_PLATO_SESSION_ID;
  if (!sessionId) {
    throw new Error("VITE_PLATO_SESSION_ID is required when VITE_PLATO_API_MODE=http.");
  }

  return createHttpMainPageAdapter({
    api: createHttpPlatoApi({
      baseUrl: env.VITE_PLATO_API_BASE_URL ?? globalThis.location.origin,
    }),
    liveLabel: "Live Session",
    sessionId,
  });
}
