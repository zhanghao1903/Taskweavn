import { describe, expect, it } from "vitest";

import type {
  ApiError,
  CommandId,
  CommandResponse,
  ConfirmationId,
  UiEvent,
} from "../../../shared/api/types";
import type { CursorOrder } from "../../../shared/runtime/runtimeReducer";
import {
  getMainPageMockSnapshot,
  type MainPageMockSnapshot,
} from "../mockPlatoApi";
import { createMainPageMockRuntimeFacade } from "./mockRuntimeFacade";

describe("Main Page mock runtime facade", () => {
  it("loads mock snapshots into the reducer runtime state", async () => {
    const facade = createMainPageMockRuntimeFacade({
      loadSnapshot: immediateMockSnapshot,
    });

    const result = await facade.load("s3-draft-ready");

    expect(result.metadata.id).toBe("s3-draft-ready");
    expect(result.state.snapshot?.session.id).toBe("session-website-plan");
    expect(result.state.lastAppliedCursor).toBe("cursor-s3-draft-ready");
    expect(result.effects).toEqual([]);
    expect(facade.metadata?.id).toBe("s3-draft-ready");
  });

  it("keeps accepted confirmation commands local until final event facts arrive", async () => {
    const facade = createMainPageMockRuntimeFacade({
      loadSnapshot: immediateMockSnapshot,
    });
    await facade.load("s7-confirmation");
    const confirmationId = requiredConfirmationId(facade.state);

    const accepted = facade.applyCommandResponse(
      acceptedCommandResponse("resolve-confirmation"),
      {
        fallbackCommandId: "resolve-confirmation",
        target: { confirmationId, kind: "confirmation" },
      },
    );

    expect(
      accepted.state.snapshot?.pendingConfirmations[0],
    ).toMatchObject({
      id: confirmationId,
      localStatus: "resolving",
      status: "pending",
    });

    const resolved = facade.receiveEvent(
      uiEvent("confirmation.resolved", {
        commandId: "resolve-confirmation",
        cursor: "cursor-confirmation-resolved",
        payload: {
          confirmationId,
          resolvedAt: "2026-05-17T10:25:00+08:00",
        },
      }),
    );

    expect(
      resolved.state.snapshot?.pendingConfirmations[0],
    ).toMatchObject({
      id: confirmationId,
      localStatus: "idle",
      resolvedAt: "2026-05-17T10:25:00+08:00",
      status: "resolved",
    });
    expect(resolved.state.pendingCommands["resolve-confirmation"]).toBeUndefined();
  });

  it("maps rejected command responses into reducer command failure state", async () => {
    const facade = createMainPageMockRuntimeFacade({
      loadSnapshot: immediateMockSnapshot,
    });
    await facade.load("s7-confirmation");
    const confirmationId = requiredConfirmationId(facade.state);

    facade.applyCommandResponse(acceptedCommandResponse("resolve-confirmation"), {
      fallbackCommandId: "resolve-confirmation",
      target: { confirmationId, kind: "confirmation" },
    });

    const failed = facade.applyCommandResponse(
      failedCommandResponse("resolve-confirmation", {
        code: "command_rejected",
        details: {},
        message: "Confirmation could not be resolved.",
        retryable: true,
      }),
      { fallbackCommandId: "resolve-confirmation" },
    );

    expect(failed.state.pendingCommands["resolve-confirmation"]).toMatchObject({
      status: "failed",
    });
    expect(
      failed.state.snapshot?.pendingConfirmations[0],
    ).toMatchObject({
      localStatus: "resolve_failed",
      status: "pending",
    });
  });

  it("flushes resync effects through the mock snapshot loader", async () => {
    const facade = createMainPageMockRuntimeFacade({
      loadSnapshot: immediateMockSnapshot,
    });
    await facade.load("s11-stale-snapshot");

    const resyncing = facade.receiveEvent(
      uiEvent("session.resync_required", {
        cursor: "cursor-resync",
        payload: { reason: "cursor_expired" },
      }),
    );
    const flushed = await facade.flushMockEffects(resyncing.effects, {
      nextStateId: "s8-completed",
    });

    expect(flushed?.state.snapshot?.session.status).toBe("completed");
    expect(flushed?.state.sync).toEqual({ kind: "idle" });
    expect(flushed?.effects).toEqual([
      { kind: "restart_events", cursor: "cursor-s8-completed" },
    ]);
    expect(facade.metadata?.id).toBe("s8-completed");
  });

  it("flushes query snapshot effects without entering resync mode", async () => {
    const facade = createMainPageMockRuntimeFacade({
      loadSnapshot: immediateMockSnapshot,
    });
    await facade.load("s6-running");

    const invalidated = facade.receiveEvent(
      uiEvent("message.appended", { cursor: "cursor-message" }),
    );
    const flushed = await facade.flushMockEffects(invalidated.effects, {
      nextStateId: "s9-file-changes",
    });

    expect(invalidated.effects).toEqual([
      {
        kind: "query_snapshot",
        page: "main",
        reason: "message.appended invalidated page snapshot.",
      },
    ]);
    expect(flushed?.state.snapshot?.fileChangeSummary).not.toBeNull();
    expect(flushed?.effects).toEqual([]);
  });

  it("preserves reducer cursor behavior through injected cursor ordering", async () => {
    const facade = createMainPageMockRuntimeFacade({
      compareCursor: cursorOrder("gap"),
      loadSnapshot: immediateMockSnapshot,
    });
    await facade.load("s3-draft-ready");

    const result = facade.receiveEvent(
      uiEvent("message.appended", { cursor: "cursor-gap" }),
    );

    expect(result.state.sync).toEqual({
      kind: "resyncing",
      reason: "Event cursor gap before cursor-gap.",
    });
    expect(result.effects).toEqual([
      {
        kind: "resync",
        page: "main",
        reason: "Event cursor gap before cursor-gap.",
      },
    ]);
    expect(result.warnings).toEqual([
      expect.objectContaining({ code: "cursor_gap" }),
    ]);
  });
});

async function immediateMockSnapshot(
  stateId: string,
): Promise<MainPageMockSnapshot> {
  return getMainPageMockSnapshot(
    stateId as Parameters<typeof getMainPageMockSnapshot>[0],
  );
}

function requiredConfirmationId(
  state: ReturnType<typeof createMainPageMockRuntimeFacade>["state"],
): ConfirmationId {
  const confirmationId = state.snapshot?.pendingConfirmations[0]?.id;
  if (!confirmationId) {
    throw new Error("Expected mock snapshot to include a confirmation.");
  }

  return confirmationId;
}

function cursorOrder(order: CursorOrder) {
  return () => order;
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

function acceptedCommandResponse(commandId: CommandId): CommandResponse {
  return {
    error: null,
    ok: true,
    refresh: {
      affectedScopes: [],
      affectedTaskRefs: [],
      suggestedQueries: ["GET /api/v1/sessions/session-website-plan/messages"],
      waitForEvents: true,
    },
    requestId: `request-${commandId}`,
    result: {
      affectedObjects: [],
      affectedTaskRefs: [],
      commandId,
      debugRefs: {},
      emittedMessageIds: [`message-${commandId}`],
      message: "Command accepted.",
      objectRefs: [],
      publishedTaskIds: [],
      status: "accepted",
    },
  };
}

function failedCommandResponse(
  commandId: CommandId,
  error: ApiError,
): CommandResponse {
  return {
    error,
    ok: false,
    refresh: {
      affectedScopes: [],
      affectedTaskRefs: [],
      suggestedQueries: [],
      waitForEvents: false,
    },
    requestId: `request-${commandId}`,
    result: {
      ...acceptedCommandResponse(commandId).result!,
      status: "rejected",
    },
  };
}
