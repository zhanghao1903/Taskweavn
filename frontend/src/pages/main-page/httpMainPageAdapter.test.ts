import { describe, expect, it, vi } from "vitest";

import type {
  AppendSessionInputPayload,
  AppendTaskInputPayload,
  PlatoApi,
  ResolveConfirmationPayload,
} from "../../shared/api/platoApi";
import type {
  CommandRequest,
  CommandResponse,
  MainPageSnapshot,
  QueryResponse,
  UiEvent,
} from "../../shared/api/types";
import { createHttpMainPageAdapter } from "./httpMainPageAdapter";
import { getMainPageMockSnapshot } from "./mockPlatoApi";

describe("HTTP MainPage adapter bridge", () => {
  it("loads a live session snapshot and derives page metadata", async () => {
    const snapshot = getMainPageMockSnapshot("s7-confirmation").snapshot;
    const api = stubPlatoApi(snapshot);
    const adapter = createHttpMainPageAdapter({
      api,
      liveLabel: "Local live session",
      sessionId: snapshot.session.id,
    });

    const result = await adapter.loadSnapshot("s7-confirmation");

    expect(api.getSessionSnapshot).toHaveBeenCalledWith(snapshot.session.id);
    expect(result.snapshot).toBe(snapshot);
    expect(result.metadata.label).toBe("Local live session");
    expect(result.metadata.detail.mode).toBe("confirmation");
    expect(result.metadata.initialSelectedTaskNodeId).toBe(
      "task-visual-direction",
    );
  });

  it("delegates commands and event subscriptions to the Plato API", async () => {
    const snapshot = getMainPageMockSnapshot("s3-draft-ready").snapshot;
    const api = stubPlatoApi(snapshot);
    const adapter = createHttpMainPageAdapter({
      api,
      sessionId: snapshot.session.id,
    });
    const sessionRequest: CommandRequest<AppendSessionInputPayload> = {
      commandId: "append-session",
      sessionId: snapshot.session.id,
      payload: {
        content: "Make the plan smaller.",
        mode: "global_guidance",
      },
    };
    const taskRequest: CommandRequest<AppendTaskInputPayload> = {
      commandId: "append-task",
      sessionId: snapshot.session.id,
      payload: {
        content: "Use fewer files.",
        mode: "guidance",
      },
    };
    const confirmationRequest: CommandRequest<ResolveConfirmationPayload> = {
      commandId: "resolve-confirmation",
      sessionId: snapshot.session.id,
      payload: {
        value: "confirmed",
      },
    };
    const eventHandler = vi.fn<(event: UiEvent) => void>();

    await adapter.appendSessionInput(sessionRequest);
    await adapter.appendTaskInput(snapshot.session.id, "task-implementation", taskRequest);
    await adapter.resolveConfirmation(
      snapshot.session.id,
      "confirmation-1",
      confirmationRequest,
    );
    const unsubscribe = adapter.subscribeSessionEvents(
      snapshot.session.id,
      snapshot.cursor,
      eventHandler,
    );
    unsubscribe();

    expect(api.appendSessionInput).toHaveBeenCalledWith(sessionRequest);
    expect(api.appendTaskInput).toHaveBeenCalledWith(
      snapshot.session.id,
      "task-implementation",
      taskRequest,
    );
    expect(api.resolveConfirmation).toHaveBeenCalledWith(
      snapshot.session.id,
      "confirmation-1",
      confirmationRequest,
    );
    expect(api.subscribeSessionEvents).toHaveBeenCalledWith(
      snapshot.session.id,
      snapshot.cursor,
      eventHandler,
    );
  });

  it("turns failed snapshot responses into thrown load errors", async () => {
    const snapshot = getMainPageMockSnapshot("s1-empty").snapshot;
    const api = stubPlatoApi(snapshot);
    api.getSessionSnapshot.mockResolvedValueOnce({
      requestId: "request-failed",
      ok: false,
      data: null,
      error: {
        code: "internal_error",
        message: "projection unavailable",
        retryable: true,
        details: {},
      },
      generatedAt: "2026-05-17T10:20:00+08:00",
    });
    const adapter = createHttpMainPageAdapter({
      api,
      sessionId: snapshot.session.id,
    });

    await expect(adapter.loadSnapshot("s1-empty")).rejects.toThrow(
      "projection unavailable",
    );
  });
});

function stubPlatoApi(snapshot: MainPageSnapshot) {
  const response = acceptedCommandResponse("accepted");
  return {
    getSessionSnapshot: vi.fn(async () => snapshotResponse(snapshot)),
    appendSessionInput: vi.fn(async () => response),
    generateTaskTree: vi.fn(async () => response),
    updateTaskNode: vi.fn(async () => response),
    appendTaskInput: vi.fn(async () => response),
    publishTaskTree: vi.fn(async () => response),
    resolveConfirmation: vi.fn(async () => response),
    subscribeSessionEvents: vi.fn(() => () => undefined),
  } satisfies PlatoApi;
}

function snapshotResponse(
  snapshot: MainPageSnapshot,
): QueryResponse<MainPageSnapshot> {
  return {
    requestId: "request-snapshot",
    ok: true,
    data: snapshot,
    error: null,
    cursor: snapshot.cursor,
    generatedAt: snapshot.generatedAt,
  };
}

function acceptedCommandResponse(commandId: string): CommandResponse {
  return {
    requestId: `request-${commandId}`,
    ok: true,
    result: {
      commandId,
      status: "accepted",
      message: "accepted",
      affectedTaskRefs: [],
      emittedMessageIds: [],
      publishedTaskIds: [],
    },
    error: null,
    refresh: {
      waitForEvents: true,
      suggestedQueries: [],
      affectedTaskRefs: [],
    },
  };
}
