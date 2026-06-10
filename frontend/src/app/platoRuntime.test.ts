import { afterEach, describe, expect, it, vi } from "vitest";

import type { CommandResponse, UiEvent } from "../shared/api/types";
import {
  createAuditApiFromRuntimeEnv,
  createMainPageAdapterFromRuntimeEnv,
  createMainPageRuntimeReducerHarnessFromEnv,
  resolvePlatoRuntimeEnv,
  resolvePlatoWorkspaceEntryRuntime,
} from "./platoRuntime";

describe("Plato runtime wiring", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses the hidden fixture adapter by default", () => {
    expect(createMainPageAdapterFromRuntimeEnv({})).toMatchObject({
      runtimeKind: "mock",
      sessionId: null,
      showStatePicker: false,
    });
    expect(createMainPageAdapterFromRuntimeEnv({ VITE_PLATO_API_MODE: "mock" })).toMatchObject({
      runtimeKind: "mock",
      sessionId: null,
      showStatePicker: false,
    });
  });

  it("prefers Electron preload runtime config when available", () => {
    vi.stubGlobal("window", {
      platoRuntimeConfig: {
        apiBaseUrl: "http://127.0.0.1:53226",
        apiMode: "http",
        disableEvents: true,
        sessionId: "session-electron",
      },
    });

    expect(resolvePlatoRuntimeEnv({ VITE_PLATO_API_MODE: "mock" })).toMatchObject({
      VITE_PLATO_API_BASE_URL: "http://127.0.0.1:53226",
      VITE_PLATO_API_MODE: "http",
      VITE_PLATO_DISABLE_EVENTS: "1",
      VITE_PLATO_SESSION_ID: "session-electron",
    });
  });

  it("resolves Electron workspace entry runtime when selection is required", () => {
    const bridge = {
      chooseWorkspace: vi.fn(),
      getGitStatus: vi.fn(),
      getState: vi.fn(),
      useWorkspace: vi.fn(),
    };
    vi.stubGlobal("window", {
      platoElectronWorkspace: bridge,
      platoRuntimeConfig: {
        workspace: {
          id: "workspace-1",
          isCurrent: true,
          label: "Project",
          name: "Project",
          pathLabel: "Project",
        },
        workspaceEntryRequired: true,
      },
    });

    expect(resolvePlatoWorkspaceEntryRuntime()).toEqual({
      bridge,
      currentWorkspace: {
        id: "workspace-1",
        isCurrent: true,
        label: "Project",
        name: "Project",
        pathLabel: "Project",
      },
      isRequired: true,
    });
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

  it("lets Main Page routes override the HTTP session and workspace", () => {
    const adapter = createMainPageAdapterFromRuntimeEnv(
      {
        VITE_PLATO_API_BASE_URL: "https://plato.example",
        VITE_PLATO_API_MODE: "http",
        VITE_PLATO_SESSION_ID: "session-env",
      },
      {
        sessionId: "session-route",
        workspaceId: "workspace-route",
      },
    );

    expect(adapter).toBeDefined();
    expect(adapter?.sessionId).toBe("session-route");
    expect(adapter?.workspaceId).toBe("workspace-route");
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

  it("keeps the runtime reducer harness disabled by default", () => {
    expect(createMainPageRuntimeReducerHarnessFromEnv({})).toBeNull();
    expect(
      createMainPageRuntimeReducerHarnessFromEnv({
        VITE_PLATO_RUNTIME_REDUCER_HARNESS: "off",
      }),
    ).toBeNull();
  });

  it("creates a test-only MainPage reducer compatibility harness when enabled", async () => {
    const harness = createMainPageRuntimeReducerHarnessFromEnv({
      VITE_PLATO_API_MODE: "mock",
      VITE_PLATO_RUNTIME_REDUCER_HARNESS: "test",
    });

    expect(harness).not.toBeNull();
    await harness?.facade.load("s6-running");

    const result = harness?.routeEvent({
      commandId: null,
      createdAt: "2026-05-17T10:20:00+08:00",
      cursor: "cursor-message",
      eventId: "event-message",
      eventType: "message.appended",
      messageIds: [],
      payload: {},
      sessionId: "session-website-plan",
      taskNodeIds: [],
    });

    expect(result).toMatchObject({
      compatible: true,
      legacyAction: {
        kind: "refetch",
        status: "connected",
      },
      reducerIntent: {
        refetch: true,
        resync: false,
      },
    });
  });

  it("uses the test-only harness to cover representative MainPage event behavior", async () => {
    const messageHarness = await createLoadedHarness("s7-confirmation");

    expect(
      messageHarness.routeEvent(
        uiEvent("message.appended", { cursor: "cursor-message" }),
      ),
    ).toMatchObject({
      compatible: true,
      legacyAction: {
        kind: "refetch",
        status: "connected",
      },
      reducerIntent: {
        refetch: true,
        resync: false,
      },
    });

    const resyncHarness = await createLoadedHarness("s7-confirmation");

    expect(
      resyncHarness.routeEvent(
        uiEvent("session.resync_required", {
          cursor: "cursor-resync",
          payload: { reason: "cursor_expired" },
        }),
      ),
    ).toMatchObject({
      compatible: true,
      legacyAction: {
        kind: "refetch",
        status: "resyncing",
      },
      reducerIntent: {
        refetch: false,
        resync: true,
      },
    });

    const failedCommandHarness = await createLoadedHarness("s7-confirmation");
    const confirmationId =
      failedCommandHarness.facade.state.snapshot?.pendingConfirmations[0]?.id;
    expect(confirmationId).toBeTruthy();

    failedCommandHarness.facade.applyCommandResponse(
      acceptedCommandResponse("resolve-confirmation"),
      {
        fallbackCommandId: "resolve-confirmation",
        target: {
          confirmationId: confirmationId ?? "confirmation-missing",
          kind: "confirmation",
        },
      },
    );

    expect(
      failedCommandHarness.routeEvent(
        uiEvent("command.failed", {
          commandId: "resolve-confirmation",
          cursor: "cursor-command-failed",
          payload: { message: "Command could not be applied." },
        }),
      ),
    ).toMatchObject({
      compatible: true,
      legacyAction: {
        errorMessage: "An update failed. Refreshing the session.",
        kind: "refetch",
        status: "connected",
      },
      reducerIntent: {
        refetch: true,
        resync: false,
      },
      state: {
        pendingCommands: {
          "resolve-confirmation": {
            status: "failed",
          },
        },
      },
    });

    const unsupportedHarmlessHarness = await createLoadedHarness("s7-confirmation");

    expect(
      unsupportedHarmlessHarness.routeEvent(
        uiEvent("plato.future_event", {
          cursor: "cursor-unsupported-harmless",
        }),
      ),
    ).toMatchObject({
      compatible: false,
      legacyAction: {
        kind: "refetch",
        status: "connected",
      },
      reducerIntent: {
        refetch: false,
        resync: false,
      },
      warnings: [expect.objectContaining({ code: "event_unsupported" })],
    });

    const unsupportedVisibleHarness = await createLoadedHarness("s7-confirmation");

    expect(
      unsupportedVisibleHarness.routeEvent(
        uiEvent("plato.future_event", {
          cursor: "cursor-unsupported-visible",
          taskNodeIds: ["task-implementation"],
        }),
      ),
    ).toMatchObject({
      compatible: true,
      legacyAction: {
        kind: "refetch",
        status: "connected",
      },
      reducerIntent: {
        refetch: false,
        resync: true,
      },
      warnings: [expect.objectContaining({ code: "event_unsupported" })],
    });
  });
});

async function createLoadedHarness(stateId: string) {
  const harness = createMainPageRuntimeReducerHarnessFromEnv({
    VITE_PLATO_API_MODE: "mock",
    VITE_PLATO_RUNTIME_REDUCER_HARNESS: "test",
  });
  if (harness === null) {
    throw new Error("Expected runtime reducer harness.");
  }

  await harness.facade.load(stateId);
  return harness;
}

function uiEvent(
  eventType: string,
  overrides: Partial<UiEvent> = {},
): UiEvent {
  return {
    commandId: null,
    createdAt: "2026-05-17T10:20:00+08:00",
    cursor: "cursor-event",
    eventId: `event-${eventType}`,
    eventType: eventType as UiEvent["eventType"],
    messageIds: [],
    payload: {},
    sessionId: "session-website-plan",
    taskNodeIds: [],
    ...overrides,
  };
}

function acceptedCommandResponse(commandId: string): CommandResponse {
  return {
    error: null,
    ok: true,
    refresh: {
      affectedScopes: [],
      affectedTaskRefs: [],
      suggestedQueries: [],
      waitForEvents: true,
    },
    requestId: `request-${commandId}`,
    result: {
      affectedObjects: [],
      affectedTaskRefs: [],
      commandId,
      debugRefs: {},
      emittedMessageIds: [],
      message: "accepted",
      objectRefs: [],
      publishedTaskIds: [],
      status: "accepted",
    },
  };
}
