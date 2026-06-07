import { describe, expect, it, vi } from "vitest";

import type {
  AnswerAskPayload,
  AnswerAuthoringAskBatchPayload,
  AppendSessionInputPayload,
  AppendTaskInputPayload,
  CancelAskPayload,
  DeferAskPayload,
  GenerateTaskTreePayload,
  PublishTaskTreePayload,
  ResolveConfirmationPayload,
  SessionLifecycleResult,
  SessionListResult,
  StopTaskPayload,
  UpdateTaskNodePayload,
} from "../../shared/api/platoApi";
import type {
  CommandRequest,
  CommandResponse,
  MainPageSnapshot,
  QueryResponse,
  UiEvent,
} from "../../shared/api/types";
import { productRecoveryActionsFromUnknown } from "../../shared/api/productErrors";
import {
  createHttpMainPageAdapter,
  type HttpMainPageApi,
} from "./httpMainPageAdapter";
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

  it("loads an explicitly selected session id", async () => {
    const snapshot = getMainPageMockSnapshot("s3-draft-ready").snapshot;
    const api = stubPlatoApi(snapshot);
    const adapter = createHttpMainPageAdapter({
      api,
      sessionId: "initial-session",
    });

    await adapter.loadSnapshot("s3-draft-ready", "selected-session");

    expect(api.getSessionSnapshot).toHaveBeenCalledWith("selected-session");
  });

  it("bootstraps from the session list when no startup session is configured", async () => {
    const snapshot = getMainPageMockSnapshot("s3-draft-ready").snapshot;
    const api = stubPlatoApi(snapshot);
    const adapter = createHttpMainPageAdapter({
      api,
    });

    await adapter.loadSnapshot("s3-draft-ready");

    expect(api.listSessions).toHaveBeenCalled();
    expect(api.createSession).not.toHaveBeenCalled();
    expect(api.getSessionSnapshot).toHaveBeenCalledWith(snapshot.session.id);
  });

  it("reports an empty workspace without creating a session implicitly", async () => {
    const snapshot = getMainPageMockSnapshot("s3-draft-ready").snapshot;
    const api = stubPlatoApi(snapshot);
    api.listSessions.mockResolvedValueOnce(
      lifecycleResponse({ sessions: [] }),
    );
    const adapter = createHttpMainPageAdapter({
      api,
    });

    await expect(adapter.loadSnapshot("s3-draft-ready")).rejects.toThrow(
      "No Plato sessions exist yet",
    );

    expect(api.createSession).not.toHaveBeenCalled();
    expect(api.getSessionSnapshot).not.toHaveBeenCalled();
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
    const answerAskRequest: CommandRequest<AnswerAskPayload> = {
      commandId: "answer-ask",
      sessionId: snapshot.session.id,
      payload: {
        selectedOptionIds: ["vercel"],
      },
    };
    const answerAuthoringAskBatchRequest: CommandRequest<AnswerAuthoringAskBatchPayload> =
      {
        commandId: "answer-authoring-ask",
        sessionId: snapshot.session.id,
        payload: {
          answers: [
            {
              askId: "raw-ask-1",
              value: "Use React.",
            },
          ],
        },
      };
    const deferAskRequest: CommandRequest<DeferAskPayload> = {
      commandId: "defer-ask",
      sessionId: snapshot.session.id,
      payload: {
        reason: "Need more context.",
      },
    };
    const cancelAskRequest: CommandRequest<CancelAskPayload> = {
      commandId: "cancel-ask",
      sessionId: snapshot.session.id,
      payload: {
        reason: "No longer needed.",
      },
    };
    const generateRequest: CommandRequest<GenerateTaskTreePayload> = {
      commandId: "generate-tree",
      sessionId: snapshot.session.id,
      payload: {
        prompt: "Plan a small website.",
      },
    };
    const updateRequest: CommandRequest<UpdateTaskNodePayload> = {
      commandId: "update-task",
      sessionId: snapshot.session.id,
      payload: {
        title: "Smaller task",
      },
    };
    const publishRequest: CommandRequest<PublishTaskTreePayload> = {
      commandId: "publish-tree",
      sessionId: snapshot.session.id,
      payload: {
        taskTreeId: snapshot.taskTree?.id ?? "task-tree",
        startImmediately: true,
      },
    };
    const stopRequest: CommandRequest<StopTaskPayload> = {
      commandId: "stop-task",
      sessionId: snapshot.session.id,
      payload: {
        reason: "user requested stop",
      },
    };
    const eventHandler = vi.fn<(event: UiEvent) => void>();

    await adapter.appendSessionInput(sessionRequest);
    await adapter.appendTaskInput(snapshot.session.id, "task-implementation", taskRequest);
    await adapter.generateTaskTree(generateRequest);
    await adapter.updateTaskNode(
      snapshot.session.id,
      "task-implementation",
      updateRequest,
    );
    await adapter.publishTaskTree(publishRequest);
    await adapter.stopTask(snapshot.session.id, "task-implementation", stopRequest);
    await adapter.createSession({ name: "New session" });
    await adapter.renameSession({
      name: "Renamed",
      sessionId: snapshot.session.id,
    });
    await adapter.deleteSession(snapshot.session.id);
    await adapter.resolveConfirmation(
      snapshot.session.id,
      "confirmation-1",
      confirmationRequest,
    );
    await adapter.answerAsk(snapshot.session.id, "ask-1", answerAskRequest);
    await adapter.answerAuthoringAskBatch(
      snapshot.session.id,
      "raw-task-1",
      answerAuthoringAskBatchRequest,
    );
    await adapter.deferAsk(snapshot.session.id, "ask-1", deferAskRequest);
    await adapter.cancelAsk(snapshot.session.id, "ask-1", cancelAskRequest);
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
    expect(api.generateTaskTree).toHaveBeenCalledWith(generateRequest);
    expect(api.updateTaskNode).toHaveBeenCalledWith(
      snapshot.session.id,
      "task-implementation",
      updateRequest,
    );
    expect(api.publishTaskTree).toHaveBeenCalledWith(publishRequest);
    expect(api.stopTask).toHaveBeenCalledWith(
      snapshot.session.id,
      "task-implementation",
      stopRequest,
    );
    expect(api.createSession).toHaveBeenCalledWith({ name: "New session" });
    expect(api.renameSession).toHaveBeenCalledWith(snapshot.session.id, {
      name: "Renamed",
    });
    expect(api.deleteSession).toHaveBeenCalledWith(snapshot.session.id);
    expect(api.resolveConfirmation).toHaveBeenCalledWith(
      snapshot.session.id,
      "confirmation-1",
      confirmationRequest,
    );
    expect(api.answerAsk).toHaveBeenCalledWith(
      snapshot.session.id,
      "ask-1",
      answerAskRequest,
    );
    expect(api.answerAuthoringAskBatch).toHaveBeenCalledWith(
      snapshot.session.id,
      "raw-task-1",
      answerAuthoringAskBatchRequest,
    );
    expect(api.deferAsk).toHaveBeenCalledWith(
      snapshot.session.id,
      "ask-1",
      deferAskRequest,
    );
    expect(api.cancelAsk).toHaveBeenCalledWith(
      snapshot.session.id,
      "ask-1",
      cancelAskRequest,
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
        details: {
          recoveryActions: ["refresh_snapshot", "export_diagnostics"],
        },
      },
      generatedAt: "2026-05-17T10:20:00+08:00",
    });
    const adapter = createHttpMainPageAdapter({
      api,
      sessionId: snapshot.session.id,
    });

    const loadError = await adapter
      .loadSnapshot("s1-empty")
      .then(() => null, (error: unknown) => error);

    expect(loadError).toMatchObject({
      message: "projection unavailable",
    });
    expect(productRecoveryActionsFromUnknown(loadError)).toEqual([
      "refresh_snapshot",
      "export_diagnostics",
    ]);
  });
});

function stubPlatoApi(snapshot: MainPageSnapshot) {
  const response = acceptedCommandResponse("accepted");
  return {
    listSessions: vi.fn(async () =>
      lifecycleResponse({ sessions: snapshot.sessions }),
    ),
    createSession: vi.fn(async () => lifecycleResponse({ sessionId: "new-session" })),
    getSessionSnapshot: vi.fn(async () => snapshotResponse(snapshot)),
    renameSession: vi.fn(async () =>
      lifecycleResponse({ sessionId: snapshot.session.id }),
    ),
    deleteSession: vi.fn(async () => lifecycleResponse({ nextSessionId: null })),
    appendSessionInput: vi.fn(async () => response),
    generateTaskTree: vi.fn(async () => response),
    updateTaskNode: vi.fn(async () => response),
    appendTaskInput: vi.fn(async () => response),
    publishTaskTree: vi.fn(async () => response),
    retryTask: vi.fn(async () => response),
    stopTask: vi.fn(async () => response),
    resolveConfirmation: vi.fn(async () => response),
    answerAsk: vi.fn(async () => response),
    answerAuthoringAskBatch: vi.fn(async () => response),
    deferAsk: vi.fn(async () => response),
    cancelAsk: vi.fn(async () => response),
    subscribeSessionEvents: vi.fn(() => () => undefined),
  } satisfies HttpMainPageApi;
}

function lifecycleResponse<T extends SessionLifecycleResult | SessionListResult>(
  data: T,
): QueryResponse<T> {
  return {
    requestId: "request-session-lifecycle",
    ok: true,
    data,
    error: null,
    generatedAt: "2026-05-17T10:20:00+08:00",
  };
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
      objectRefs: [],
      affectedObjects: [],
      emittedMessageIds: [],
      publishedTaskIds: [],
      debugRefs: {},
    },
    error: null,
    refresh: {
      waitForEvents: true,
      suggestedQueries: [],
      affectedTaskRefs: [],
      affectedScopes: [],
    },
  };
}
