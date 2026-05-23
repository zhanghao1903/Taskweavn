import { describe, expect, it } from "vitest";

import { createMainPageAdapterFromRuntimeEnv } from "./platoRuntime";

describe("Plato runtime wiring", () => {
  it("uses the fixture adapter by default", () => {
    expect(createMainPageAdapterFromRuntimeEnv({})).toBeUndefined();
    expect(createMainPageAdapterFromRuntimeEnv({ VITE_PLATO_API_MODE: "mock" })).toBeUndefined();
  });

  it("creates an HTTP-backed MainPage adapter without a startup session", () => {
    const adapter = createMainPageAdapterFromRuntimeEnv({
      VITE_PLATO_API_BASE_URL: "https://plato.example",
      VITE_PLATO_API_MODE: "http",
    });

    expect(adapter).toBeDefined();
    expect(adapter?.sessionId).toBeNull();
  });

  it("creates an HTTP-backed MainPage adapter when configured", () => {
    const adapter = createMainPageAdapterFromRuntimeEnv({
      VITE_PLATO_API_BASE_URL: "https://plato.example",
      VITE_PLATO_API_MODE: "http",
      VITE_PLATO_SESSION_ID: "session-live",
    });

    expect(adapter).toBeDefined();
    expect(adapter?.appendSessionInput).toBeTypeOf("function");
  });
});
