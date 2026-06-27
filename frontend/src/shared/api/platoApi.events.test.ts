import { describe, expect, it, vi } from "vitest";

import { createHttpPlatoApi } from "./platoApi";
import type { EventSourceLike } from "./platoApi";
import type { UiEvent } from "./types";

describe("createHttpPlatoApi event subscription", () => {
  it("subscribes to SSE events and closes the source", () => {
    const sources: FakeEventSource[] = [];
    const api = createHttpPlatoApi({
      baseUrl: "https://plato.test/",
      eventSourceFactory: (url) => {
        const source = new FakeEventSource(url);
        sources.push(source);
        return source;
      },
    });
    const onEvent = vi.fn<(event: UiEvent) => void>();

    const unsubscribe = api.subscribeSessionEvents(
      "session 1",
      "cursor/1",
      onEvent,
    );
    sources[0].emit("message", uiEvent);
    unsubscribe();

    expect(sources[0].url).toBe(
      "https://plato.test/api/v1/sessions/session%201/events?cursor=cursor%2F1",
    );
    expect(onEvent).toHaveBeenCalledWith(uiEvent);
    expect(sources[0].closed).toBe(true);
  });

  it("subscribes to named SSE event types emitted by the sidecar", () => {
    const sources: FakeEventSource[] = [];
    const api = createHttpPlatoApi({
      baseUrl: "https://plato.test/",
      eventSourceFactory: (url) => {
        const source = new FakeEventSource(url);
        sources.push(source);
        return source;
      },
    });
    const onEvent = vi.fn<(event: UiEvent) => void>();

    api.subscribeSessionEvents("session-1", null, onEvent);
    sources[0].emit("session.resync_required", {
      ...uiEvent,
      eventType: "session.resync_required",
    });
    sources[0].emit("audit.records_changed", {
      ...uiEvent,
      eventType: "audit.records_changed",
    });
    sources[0].emit("message.appended", uiEvent);

    expect(onEvent).toHaveBeenCalledTimes(3);
    expect(onEvent).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ eventType: "session.resync_required" }),
    );
    expect(onEvent).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ eventType: "audit.records_changed" }),
    );
    expect(onEvent).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({ eventType: "message.appended" }),
    );
  });
});

class FakeEventSource implements EventSourceLike {
  closed = false;
  private listeners = new Map<string, (event: { data: string }) => void>();

  constructor(readonly url: string) {}

  addEventListener(
    type: string,
    listener: (event: { data: string }) => void,
  ): void {
    this.listeners.set(type, listener);
  }

  close(): void {
    this.closed = true;
  }

  emit(type: string, event: UiEvent): void {
    this.listeners.get(type)?.({
      data: JSON.stringify(event),
    });
  }
}

const uiEvent: UiEvent = {
  commandId: null,
  createdAt: "2026-05-17T10:00:00+08:00",
  cursor: "cursor-2",
  eventId: "event-1",
  eventType: "message.appended",
  messageIds: ["message-1"],
  payload: {
    body: "Message body",
    kind: "informational",
    title: "Message title",
  },
  sessionId: "session 1",
  taskNodeIds: [],
};
