import { describe, expect, it } from "vitest";

import type { UiEvent } from "../../../shared/api/types";
import { resyncEventKey, routeMainPageEvent } from "./eventRouter";

describe("MainPage event router", () => {
  it("treats lightweight message events as refetch hints", () => {
    expect(routeMainPageEvent(uiEvent("message.appended"))).toEqual({
      kind: "refetch",
      status: "connected",
    });
  });

  it("marks resync-required events as resyncing refetch hints", () => {
    expect(routeMainPageEvent(uiEvent("session.resync_required"))).toEqual({
      kind: "refetch",
      status: "resyncing",
    });
  });

  it("surfaces command failed event messages", () => {
    expect(
      routeMainPageEvent({
        ...uiEvent("command.failed"),
        payload: {
          message: "Command could not be applied.",
        },
      }),
    ).toEqual({
      errorMessage: "Command could not be applied.",
      kind: "refetch",
      status: "connected",
    });
  });

  it("builds a stable resync loop-guard key", () => {
    expect(
      resyncEventKey({
        ...uiEvent("session.resync_required"),
        cursor: "cursor-1",
        payload: {
          reason: "replay_unavailable",
        },
      }),
    ).toBe("cursor-1:replay_unavailable");
  });
});

function uiEvent(eventType: UiEvent["eventType"]): UiEvent {
  return {
    eventId: `event-${eventType}`,
    sessionId: "session-1",
    eventType,
    cursor: "cursor-1",
    taskNodeIds: [],
    messageIds: [],
    payload: {},
    createdAt: "2026-05-17T10:20:00+08:00",
  };
}

