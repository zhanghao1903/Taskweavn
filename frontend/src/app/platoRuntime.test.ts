import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createAuditApiFromRuntimeEnv,
  createMainPageAdapterFromRuntimeEnv,
} from "./platoRuntime";

describe("Plato runtime wiring", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

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

  it("creates a mock Audit API by default", async () => {
    const api = createAuditApiFromRuntimeEnv({
      VITE_PLATO_AUDIT_MOCK_SCENARIO: "a11-permission-denied",
      VITE_PLATO_API_MODE: "mock",
    });

    await expect(
      api.getAuditSnapshot({ sessionId: "session-website-plan" }),
    ).resolves.toMatchObject({
      data: {
        pageState: {
          kind: "permission_denied",
        },
      },
      ok: true,
    });
  });

  it("creates an HTTP-backed Audit API when configured", async () => {
    const calls: string[] = [];
    const api = createAuditApiFromRuntimeEnv({
      VITE_PLATO_API_BASE_URL: "https://plato.example",
      VITE_PLATO_API_MODE: "http",
    });

    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      calls.push(String(input));
      return new Response(
        JSON.stringify({
          data: null,
          error: null,
          generatedAt: "2026-05-24T10:00:00Z",
          ok: true,
          requestId: "request-audit-runtime",
        }),
        {
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    });

    await api.getAuditSnapshot({ sessionId: "session-live" });

    expect(calls).toEqual([
      "https://plato.example/api/v1/sessions/session-live/audit",
    ]);
  });
});
