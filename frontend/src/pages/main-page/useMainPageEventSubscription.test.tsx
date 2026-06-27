import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { UiEvent } from "../../shared/api/types";
import type { MainPageAdapter, SubscribeSessionEvents } from "./runtime/adapter";
import {
  createMainPageMockAdapter,
  getMainPageMockSnapshot,
} from "./mockPlatoApi";
import { useMainPageEventSubscription } from "./useMainPageEventSubscription";

describe("useMainPageEventSubscription", () => {
  it("subscribes to the active session event stream", async () => {
    const snapshotData = getMainPageMockSnapshot("s3-draft-ready");
    const subscribeSessionEvents = vi.fn<SubscribeSessionEvents>(() => () => {
      // No-op unsubscribe for the hook boundary test.
    });

    const { result } = renderEventSubscription({
      adapter: testAdapter({ subscribeSessionEvents }),
      snapshotData,
    });

    await waitFor(() => {
      expect(result.current.eventConnectionStatus).toBe("connected");
    });

    expect(subscribeSessionEvents).toHaveBeenCalledWith(
      "session-website-plan",
      "cursor-s3-draft-ready",
      expect.any(Function),
      null,
    );
  });

  it("refetches snapshot facts when a routed session event arrives", async () => {
    const snapshotData = getMainPageMockSnapshot("s3-draft-ready");
    let emitEvent: ((event: UiEvent) => void) | null = null;
    const refetchSnapshot = vi.fn(async () => ({
      data: snapshotData,
      status: "success",
    }));
    const subscribeSessionEvents = vi.fn<SubscribeSessionEvents>(
      (_sessionId, _cursor, onEvent) => {
        emitEvent = onEvent;
        return () => undefined;
      },
    );

    const { result } = renderEventSubscription({
      adapter: testAdapter({ subscribeSessionEvents }),
      refetchSnapshot,
      snapshotData,
    });

    await waitFor(() => {
      expect(result.current.eventConnectionStatus).toBe("connected");
    });
    expect(emitEvent).not.toBeNull();

    act(() => {
      emitEvent?.(messageAppendedEvent("session-website-plan"));
    });

    await waitFor(() => {
      expect(refetchSnapshot).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(result.current.eventConnectionStatus).toBe("connected");
    });
  });

  it("ignores duplicate runtime event cursors from finite SSE reconnects", async () => {
    const snapshotData = getMainPageMockSnapshot("s3-draft-ready");
    let emitEvent: ((event: UiEvent) => void) | null = null;
    const refetchSnapshot = vi.fn(async () => ({
      data: snapshotData,
      status: "success",
    }));
    const subscribeSessionEvents = vi.fn<SubscribeSessionEvents>(
      (_sessionId, _cursor, onEvent) => {
        emitEvent = onEvent;
        return () => undefined;
      },
    );

    renderEventSubscription({
      adapter: testAdapter({ subscribeSessionEvents }),
      refetchSnapshot,
      snapshotData,
    });

    await waitFor(() => {
      expect(emitEvent).not.toBeNull();
    });

    const event = messageAppendedEvent("session-website-plan");
    act(() => {
      emitEvent?.(event);
      emitEvent?.(event);
    });

    await waitFor(() => {
      expect(refetchSnapshot).toHaveBeenCalledTimes(1);
    });
  });
});

type RenderEventSubscriptionOptions = {
  adapter?: MainPageAdapter;
  refetchSnapshot?: () => Promise<{
    data?: ReturnType<typeof getMainPageMockSnapshot>;
    status: string;
  }>;
  resetKey?: string | null;
  snapshotData?: ReturnType<typeof getMainPageMockSnapshot>;
};

function renderEventSubscription({
  adapter = testAdapter(),
  refetchSnapshot = async () => ({
    data: getMainPageMockSnapshot("s3-draft-ready"),
    status: "success",
  }),
  resetKey = "s3-draft-ready",
  snapshotData = getMainPageMockSnapshot("s3-draft-ready"),
}: RenderEventSubscriptionOptions = {}) {
  return renderHook(() =>
    useMainPageEventSubscription({
      activeWorkspaceId: null,
      adapter,
      refetchSnapshot,
      resetKey,
      snapshotData,
    }),
  );
}

function testAdapter(overrides: Partial<MainPageAdapter> = {}): MainPageAdapter {
  return createMainPageMockAdapter(overrides);
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
