import { describe, expect, it } from "vitest";

import type { UiEvent } from "../../../shared/api/types";
import { createMainPageMockRuntimeFacade } from "./mockRuntimeFacade";
import { routeMainPageEventWithReducerCompatibility } from "./eventRouterCompatibility";
import { getMainPageMockSnapshot } from "../mockPlatoApi";

describe("MainPage event router reducer compatibility", () => {
  it("keeps message events compatible with legacy refetch behavior", async () => {
    const facade = createMainPageMockRuntimeFacade({
      loadSnapshot: immediateMockSnapshot,
    });
    await facade.load("s6-running");

    const result = routeMainPageEventWithReducerCompatibility(
      facade,
      uiEvent("message.appended", { cursor: "cursor-message" }),
    );

    expect(result.legacyAction).toEqual({
      kind: "refetch",
      status: "connected",
    });
    expect(result.reducerIntent).toEqual({
      errorMessage: null,
      refetch: true,
      resync: false,
    });
    expect(result.compatible).toBe(true);
  });

  it("keeps resync-required events compatible with legacy resyncing behavior", async () => {
    const facade = createMainPageMockRuntimeFacade({
      loadSnapshot: immediateMockSnapshot,
    });
    await facade.load("s11-stale-snapshot");

    const result = routeMainPageEventWithReducerCompatibility(
      facade,
      uiEvent("session.resync_required", {
        cursor: "cursor-resync",
        payload: { reason: "cursor_expired" },
      }),
    );

    expect(result.legacyAction).toEqual({
      kind: "refetch",
      status: "resyncing",
    });
    expect(result.reducerIntent).toEqual({
      errorMessage: null,
      refetch: false,
      resync: true,
    });
    expect(result.compatible).toBe(true);
  });

  it("keeps command failed events compatible while preserving reducer command state", async () => {
    const facade = createMainPageMockRuntimeFacade({
      loadSnapshot: immediateMockSnapshot,
    });
    await facade.load("s7-confirmation");

    const confirmationId = facade.state.snapshot?.pendingConfirmations[0]?.id;
    if (!confirmationId) {
      throw new Error("Expected confirmation fixture.");
    }

    facade.applyCommandResponse(
      {
        error: null,
        ok: true,
        refresh: {
          affectedScopes: [],
          affectedTaskRefs: [],
          suggestedQueries: [],
          waitForEvents: true,
        },
        requestId: "request-resolve-confirmation",
        result: {
          affectedObjects: [],
          affectedTaskRefs: [],
          commandId: "resolve-confirmation",
          debugRefs: {},
          emittedMessageIds: [],
          message: "accepted",
          objectRefs: [],
          publishedTaskIds: [],
          status: "accepted",
        },
      },
      {
        fallbackCommandId: "resolve-confirmation",
        target: { confirmationId, kind: "confirmation" },
      },
    );

    const result = routeMainPageEventWithReducerCompatibility(
      facade,
      uiEvent("command.failed", {
        commandId: "resolve-confirmation",
        cursor: "cursor-command-failed",
        payload: { message: "Command could not be applied." },
      }),
    );

    expect(result.legacyAction).toEqual({
      errorMessage: "An update failed. Refreshing the session.",
      kind: "refetch",
      status: "connected",
    });
    expect(result.reducerIntent).toEqual({
      errorMessage: null,
      refetch: true,
      resync: false,
    });
    expect(result.compatible).toBe(true);
    expect(result.state.pendingCommands["resolve-confirmation"]).toMatchObject({
      status: "failed",
    });
    expect(result.state.snapshot?.pendingConfirmations[0]).toMatchObject({
      localStatus: "resolve_failed",
      status: "pending",
    });
  });
});

async function immediateMockSnapshot(
  stateId: string,
): Promise<ReturnType<typeof getMainPageMockSnapshot>> {
  return getMainPageMockSnapshot(
    stateId as Parameters<typeof getMainPageMockSnapshot>[0],
  );
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
