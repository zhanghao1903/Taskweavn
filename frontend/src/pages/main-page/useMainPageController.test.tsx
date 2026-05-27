import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { UiEvent } from "../../shared/api/types";
import type {
  LoadMainPageSnapshot,
  MainPageAdapter,
  SubscribeSessionEvents,
} from "./runtime/adapter";
import type { MainPageStateId } from "./mockPlatoApi";
import {
  createMainPageMockAdapter,
  getMainPageMockSnapshot,
} from "./mockPlatoApi";
import { useMainPageController } from "./useMainPageController";

describe("useMainPageController", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the initial runtime snapshot and subscribes to the session event stream", async () => {
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);
    const subscribeSessionEvents = vi.fn<SubscribeSessionEvents>(() => () => {
      // No-op unsubscribe for the controller boundary test.
    });

    const { result } = renderMainPageController({
      adapter: testAdapter({
        loadSnapshot,
        subscribeSessionEvents,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    expect(result.current.stateId).toBe("s3-draft-ready");
    expect(result.current.eventConnectionStatus).toBe("connected");
    expect(loadSnapshot).toHaveBeenCalledWith("s3-draft-ready", null);
    expect(subscribeSessionEvents).toHaveBeenCalledWith(
      "session-website-plan",
      "cursor-s3-draft-ready",
      expect.any(Function),
    );
  });

  it("resets local coordination state when switching fixture states", async () => {
    const { result } = renderMainPageController({
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.selectTask("task-visual-direction");
      result.current.actions.showResult();
      result.current.actions.changeInputDraft("temporary guidance");
    });

    expect(result.current.selectedTaskNodeId).toBe("task-visual-direction");
    expect(result.current.detailOverride).toBe("result");
    expect(result.current.inputDraft).toBe("temporary guidance");

    act(() => {
      result.current.actions.changeState("s9-file-changes");
    });

    expect(result.current.stateId).toBe("s9-file-changes");
    expect(result.current.selectedTaskNodeId).toBe(null);
    expect(result.current.detailOverride).toBe("auto");
    expect(result.current.inputDraft).toBe("");
    expect(result.current.inputError).toBe(null);
    expect(result.current.taskTreeCommandError).toBe(null);
  });

  it("switches the active session after creating a session", async () => {
    const createSession = vi.fn(async () => ({
      session: {
        id: "session-new",
        name: "New session",
      },
      sessionId: "session-new",
    }));
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);
    vi.stubGlobal("prompt", vi.fn(() => "New session"));

    const { result } = renderMainPageController({
      adapter: testAdapter({
        createSession,
        loadSnapshot,
        runtimeKind: "http",
        sessionId: "session-website-plan",
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.createSession();
    });

    await waitFor(() => {
      expect(createSession).toHaveBeenCalledWith({ name: "New session" });
    });
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledWith(
        "s3-draft-ready",
        "session-new",
      );
    });

    expect(result.current.activeSessionId).toBe("session-new");
  });

  it("refetches snapshot facts when a routed session event arrives", async () => {
    let emitEvent: ((event: UiEvent) => void) | null = null;
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);
    const subscribeSessionEvents = vi.fn<SubscribeSessionEvents>(
      (_sessionId, _cursor, onEvent) => {
        emitEvent = onEvent;
        return () => undefined;
      },
    );

    const { result } = renderMainPageController({
      adapter: testAdapter({
        loadSnapshot,
        subscribeSessionEvents,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });
    expect(emitEvent).not.toBeNull();

    act(() => {
      emitEvent?.(messageAppendedEvent("session-website-plan"));
    });

    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(result.current.eventConnectionStatus).toBe("connected");
    });
  });
});

function renderMainPageController({
  adapter = testAdapter(),
  initialStateId = "s3-draft-ready",
}: {
  adapter?: MainPageAdapter;
  initialStateId?: MainPageStateId;
}) {
  return renderHook(
    () =>
      useMainPageController({
        adapter,
        initialStateId,
      }),
    {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={createTestQueryClient()}>
          {children}
        </QueryClientProvider>
      ),
    },
  );
}

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

const loadImmediateSnapshot: LoadMainPageSnapshot = async (stateId) =>
  getMainPageMockSnapshot(stateId as MainPageStateId);

function testAdapter(overrides: Partial<MainPageAdapter> = {}): MainPageAdapter {
  return createMainPageMockAdapter({
    loadSnapshot: loadImmediateSnapshot,
    ...overrides,
  });
}

function messageAppendedEvent(sessionId: string): UiEvent {
  return {
    eventId: "event-message-appended",
    sessionId,
    eventType: "message.appended",
    cursor: "cursor-after-message",
    taskNodeIds: [],
    messageIds: ["message-from-event"],
    payload: {
      title: "Worker update",
      body: "The event stream appended a message.",
      kind: "informational",
    },
    createdAt: "2026-05-17T10:21:00+08:00",
  };
}
