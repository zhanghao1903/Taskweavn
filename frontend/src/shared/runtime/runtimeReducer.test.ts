import { describe, expect, it } from "vitest";

import { getMainPageMockSnapshot } from "../../pages/main-page/mockPlatoApi";
import type {
  ApiError,
  AskId,
  CommandId,
  CommandResult,
  ConfirmationId,
  MainPageSnapshot,
  UiEvent,
} from "../api/types";
import {
  createInitialRuntimeState,
  reduceRuntimeState,
  type CursorOrder,
  type RuntimeState,
} from "./runtimeReducer";

describe("runtime reducer foundation", () => {
  it("loads snapshots and initializes cursor state", () => {
    const snapshot = mainSnapshot("s3-draft-ready");

    const { state, effects, warnings } = reduceRuntimeState(
      createInitialRuntimeState("main"),
      { kind: "snapshot.loaded", page: "main", snapshot },
    );

    expect(state.snapshot).toBe(snapshot);
    expect(state.lastAppliedCursor).toBe(snapshot.cursor);
    expect(state.sync).toEqual({ kind: "idle" });
    expect(effects).toEqual([]);
    expect(warnings).toEqual([]);
  });

  it("keeps accepted commands local and does not mutate final snapshot facts", () => {
    const state = loadedMainState("s6-running");
    const before = state.snapshot;
    const result = commandResult("command-accepted");

    const { state: nextState, effects } = reduceRuntimeState(state, {
      kind: "command.accepted",
      result,
    });

    expect(nextState.pendingCommands["command-accepted"]).toMatchObject({
      commandId: "command-accepted",
      status: "accepted",
      target: { kind: "generic" },
    });
    expect(nextState.snapshot?.session.status).toBe(before?.session.status);
    expect(nextState.snapshot?.taskTree?.status).toBe(before?.taskTree?.status);
    expect(nextState.snapshot?.planning?.state).toBe(before?.planning?.state);
    expect(effects).toEqual([]);
  });

  it("tracks ASK command targets and clears only the completed command", () => {
    const state = loadedMainState("s14-execution-ask");
    const askId = requiredActiveAskId(state);

    const withAskCommand = reduceRuntimeState(state, {
      kind: "command.accepted",
      result: commandResult("answer-ask"),
      target: { action: "answer", askId, kind: "ask" },
    }).state;
    const withSecondCommand = reduceRuntimeState(withAskCommand, {
      kind: "command.accepted",
      result: commandResult("append-guidance"),
    }).state;

    const completed = reduceRuntimeState(withSecondCommand, {
      kind: "event.received",
      event: uiEvent("command.completed", {
        commandId: "answer-ask",
        cursor: "cursor-ask-completed",
      }),
    });

    expect(completed.state.pendingCommands["answer-ask"]).toBeUndefined();
    expect(completed.state.pendingCommands["append-guidance"]).toMatchObject({
      commandId: "append-guidance",
      status: "accepted",
      target: { kind: "generic" },
    });
    expect(completed.state.snapshot?.activeAsk?.id).toBe(askId);
    expect(completed.effects).toEqual([
      {
        kind: "query_snapshot",
        page: "main",
        reason: "command.completed invalidated page snapshot.",
      },
    ]);
  });

  it("applies command failure only to the matching ASK command", () => {
    const state = loadedMainState("s14-execution-ask");
    const askId = requiredActiveAskId(state);
    const withAnswerCommand = reduceRuntimeState(state, {
      kind: "command.accepted",
      result: commandResult("answer-ask"),
      target: { action: "answer", askId, kind: "ask" },
    }).state;
    const withDeferCommand = reduceRuntimeState(withAnswerCommand, {
      kind: "command.accepted",
      result: commandResult("defer-ask"),
      target: { action: "defer", askId, kind: "ask" },
    }).state;

    const failed = reduceRuntimeState(withDeferCommand, {
      kind: "event.received",
      event: uiEvent("command.failed", {
        commandId: "answer-ask",
        cursor: "cursor-ask-failed",
        payload: { message: "ASK answer was rejected." },
      }),
    });

    expect(failed.state.pendingCommands["answer-ask"]).toMatchObject({
      commandId: "answer-ask",
      status: "failed",
      target: { action: "answer", askId, kind: "ask" },
    });
    expect(failed.state.pendingCommands["defer-ask"]).toMatchObject({
      commandId: "defer-ask",
      status: "accepted",
      target: { action: "defer", askId, kind: "ask" },
    });
    expect(failed.effects).toEqual([
      {
        kind: "query_snapshot",
        page: "main",
        reason: "command.failed invalidated page snapshot.",
      },
    ]);
  });

  it("models confirmation resolving, final resolution facts, and failed local resolution", () => {
    const state = loadedMainState("s7-confirmation");
    const confirmation = state.snapshot?.pendingConfirmations[0];
    expect(confirmation?.status).toBe("pending");

    const accepted = reduceRuntimeState(state, {
      kind: "command.accepted",
      result: commandResult("resolve-confirmation"),
      target: {
        confirmationId: confirmation?.id ?? "missing",
        kind: "confirmation",
      },
    }).state;

    expect(confirmationById(accepted, confirmation?.id)).toMatchObject({
      localStatus: "resolving",
      status: "pending",
    });

    const resolved = reduceRuntimeState(accepted, {
      kind: "event.received",
      event: uiEvent("confirmation.resolved", {
        commandId: "resolve-confirmation",
        cursor: "cursor-confirmation-resolved",
        payload: {
          confirmationId: confirmation?.id,
          resolvedAt: "2026-05-17T10:21:00+08:00",
        },
      }),
    }).state;

    expect(confirmationById(resolved, confirmation?.id)).toMatchObject({
      localStatus: "idle",
      resolvedAt: "2026-05-17T10:21:00+08:00",
      status: "resolved",
    });
    expect(resolved.pendingCommands["resolve-confirmation"]).toBeUndefined();

    const failed = reduceRuntimeState(accepted, {
      commandId: "resolve-confirmation",
      error: apiError("command_rejected", "User decision was rejected."),
      kind: "command.failed",
    }).state;

    expect(confirmationById(failed, confirmation?.id)).toMatchObject({
      localStatus: "resolve_failed",
      status: "pending",
    });
    expect(failed.pendingCommands["resolve-confirmation"]).toMatchObject({
      status: "failed",
    });

    const failedEvent = reduceRuntimeState(accepted, {
      kind: "event.received",
      event: uiEvent("command.failed", {
        commandId: "resolve-confirmation",
        cursor: "cursor-command-failed",
        payload: { message: "User decision was rejected." },
      }),
    });

    expect(confirmationById(failedEvent.state, confirmation?.id)).toMatchObject({
      localStatus: "resolve_failed",
      status: "pending",
    });
    expect(failedEvent.effects).toEqual([
      {
        kind: "query_snapshot",
        page: "main",
        reason: "command.failed invalidated page snapshot.",
      },
    ]);
  });

  it("requests resync for stale events and resync-class command failures", () => {
    const state = loadedMainState("s11-stale-snapshot");

    const resyncEventResult = reduceRuntimeState(state, {
      kind: "event.received",
      event: uiEvent("session.resync_required", {
        cursor: "cursor-resync",
        payload: { reason: "cursor_expired" },
      }),
    });

    expect(resyncEventResult.state.sync).toEqual({
      kind: "resyncing",
      reason: "cursor_expired",
    });
    expect(resyncEventResult.effects).toEqual([
      { kind: "resync", page: "main", reason: "cursor_expired" },
    ]);

    const accepted = reduceRuntimeState(state, {
      kind: "command.accepted",
      result: commandResult("publish-command"),
    }).state;

    const conflictResult = reduceRuntimeState(accepted, {
      commandId: "publish-command",
      error: apiError("version_conflict", "Snapshot version is stale."),
      kind: "command.failed",
    });

    expect(conflictResult.state.sync).toEqual({
      kind: "resyncing",
      reason: "Snapshot version is stale.",
    });
    expect(conflictResult.effects).toEqual([
      {
        kind: "resync",
        page: "main",
        reason: "Snapshot version is stale.",
      },
    ]);
  });

  it("ignores duplicate cursors and requests resync on cursor gaps", () => {
    const state = loadedMainState("s3-draft-ready");

    const duplicate = reduceRuntimeState(
      state,
      {
        kind: "event.received",
        event: uiEvent("message.appended", { cursor: "cursor-duplicate" }),
      },
      { compareCursor: cursorOrder("duplicate_or_old") },
    );

    expect(duplicate.state.lastAppliedCursor).toBe(state.lastAppliedCursor);
    expect(duplicate.effects).toEqual([]);
    expect(duplicate.warnings).toEqual([
      expect.objectContaining({ code: "cursor_duplicate" }),
    ]);

    const gap = reduceRuntimeState(
      state,
      {
        kind: "event.received",
        event: uiEvent("message.appended", { cursor: "cursor-gap" }),
      },
      { compareCursor: cursorOrder("gap") },
    );

    expect(gap.state.lastAppliedCursor).toBe(state.lastAppliedCursor);
    expect(gap.state.sync.kind).toBe("resyncing");
    expect(gap.effects).toEqual([
      {
        kind: "resync",
        page: "main",
        reason: "Event cursor gap before cursor-gap.",
      },
    ]);
    expect(gap.warnings).toEqual([
      expect.objectContaining({ code: "cursor_gap" }),
    ]);
  });

  it("handles unsupported events without crashing and resyncs when visible state may be affected", () => {
    const state = loadedMainState("s3-draft-ready");

    const harmless = reduceRuntimeState(state, {
      kind: "event.received",
      event: uiEvent("unknown.backend_event", {
        cursor: "cursor-unknown-harmless",
      }),
    });

    expect(harmless.effects).toEqual([]);
    expect(harmless.state.lastAppliedCursor).toBe("cursor-unknown-harmless");
    expect(harmless.warnings).toEqual([
      expect.objectContaining({ code: "event_unsupported" }),
    ]);

    const visible = reduceRuntimeState(state, {
      kind: "event.received",
      event: uiEvent("unknown.backend_event", {
        cursor: "cursor-unknown-visible",
        taskNodeIds: ["task-implementation"],
      }),
    });

    expect(visible.state.sync).toEqual({
      kind: "resyncing",
      reason: "Unsupported visible event unknown.backend_event.",
    });
    expect(visible.effects).toEqual([
      {
        kind: "resync",
        page: "main",
        reason: "Unsupported visible event unknown.backend_event.",
      },
    ]);
  });

  it("replaces snapshots after resync and restarts events from the fresh cursor", () => {
    const state = loadedMainState("s11-stale-snapshot");
    const freshSnapshot = mainSnapshot("s8-completed");

    const { state: resyncing } = reduceRuntimeState(state, {
      kind: "resync.started",
      reason: "manual refresh",
    });
    const { state: refreshed, effects } = reduceRuntimeState(resyncing, {
      kind: "resync.finished",
      snapshot: freshSnapshot,
    });

    expect(refreshed.snapshot).toBe(freshSnapshot);
    expect(refreshed.sync).toEqual({ kind: "idle" });
    expect(refreshed.lastAppliedCursor).toBe(freshSnapshot.cursor);
    expect(effects).toEqual([
      { kind: "restart_events", cursor: freshSnapshot.cursor },
    ]);
  });
});

function loadedMainState(stateId: Parameters<typeof getMainPageMockSnapshot>[0]) {
  return reduceRuntimeState(createInitialRuntimeState("main"), {
    kind: "snapshot.loaded",
    page: "main",
    snapshot: mainSnapshot(stateId),
  }).state as RuntimeState<MainPageSnapshot>;
}

function mainSnapshot(
  stateId: Parameters<typeof getMainPageMockSnapshot>[0],
): MainPageSnapshot {
  return getMainPageMockSnapshot(stateId).snapshot;
}

function confirmationById(
  state: RuntimeState<MainPageSnapshot>,
  confirmationId: ConfirmationId | undefined,
) {
  return state.snapshot?.pendingConfirmations.find(
    (confirmation) => confirmation.id === confirmationId,
  );
}

function requiredActiveAskId(state: RuntimeState<MainPageSnapshot>): AskId {
  const askId = state.snapshot?.activeAsk?.id;
  if (!askId) {
    throw new Error("Expected mock snapshot to include an active ASK.");
  }

  return askId;
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

function commandResult(commandId: CommandId): CommandResult {
  return {
    affectedObjects: [],
    affectedTaskRefs: [],
    commandId,
    debugRefs: {},
    emittedMessageIds: [],
    message: "Command accepted.",
    objectRefs: [],
    publishedTaskIds: [],
    status: "accepted",
  };
}

function apiError(code: ApiError["code"], message: string): ApiError {
  return {
    code,
    details: {},
    message,
    retryable: true,
  };
}
