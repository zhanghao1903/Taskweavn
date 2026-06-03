import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CommandResponse, UiEvent } from "../../shared/api/types";
import type {
  LoadMainPageSnapshot,
  MainPageAdapter,
  RetryTaskCommand,
  StopTaskCommand,
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

  it("submits a manual retry command for the selected failed task", async () => {
    const retryTask = vi.fn<RetryTaskCommand>(async (sessionId, taskNodeId, request) =>
      acceptedCommandResponse({
        commandId: request.commandId,
        sessionId,
        taskNodeId,
      }),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    const { result } = renderMainPageController({
      adapter: testAdapter({
        loadSnapshot,
        retryTask,
      }),
      initialStateId: "s13-command-failed",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe(
        "s13-command-failed",
      );
    });

    act(() => {
      result.current.actions.retryTask({
        sessionId: "session-website-plan",
        taskNodeId: "task-implementation",
      });
    });

    await waitFor(() => {
      expect(retryTask).toHaveBeenCalledWith(
        "session-website-plan",
        "task-implementation",
        expect.objectContaining({
          sessionId: "session-website-plan",
          payload: { startImmediately: true },
        }),
      );
    });
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });

    expect(result.current.taskTreeCommandError).toBe(null);
  });

  it("submits a stop command for an active task", async () => {
    const stopTask = vi.fn<StopTaskCommand>(async (sessionId, taskNodeId, request) =>
      acceptedCommandResponse({
        commandId: request.commandId,
        sessionId,
        taskNodeId,
      }),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    const { result } = renderMainPageController({
      adapter: testAdapter({
        loadSnapshot,
        stopTask,
      }),
      initialStateId: "s6-running",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s6-running");
    });

    act(() => {
      result.current.actions.stopTask({
        sessionId: "session-website-plan",
        taskNodeId: "task-implementation",
      });
    });

    await waitFor(() => {
      expect(stopTask).toHaveBeenCalledWith(
        "session-website-plan",
        "task-implementation",
        expect.objectContaining({
          sessionId: "session-website-plan",
          payload: { reason: "user requested stop" },
        }),
      );
    });
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });

    expect(result.current.taskTreeCommandError).toBe(null);
    expect(result.current.uiNotice).toBe("Stop requested.");
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
    act(() => {
      result.current.actions.changeSessionDialogDraft("New session");
    });
    act(() => {
      result.current.actions.submitSessionDialog();
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
    expect(result.current.sessionDialog.mode).toBe("idle");
  });

  it("cancels and validates session create before calling the adapter", async () => {
    const createSession = vi.fn(async () => ({
      sessionId: "session-new",
    }));
    const { result } = renderMainPageController({
      adapter: testAdapter({
        createSession,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.createSession();
    });
    act(() => {
      result.current.actions.cancelSessionDialog();
    });

    expect(result.current.sessionDialog.mode).toBe("idle");
    expect(createSession).not.toHaveBeenCalled();

    act(() => {
      result.current.actions.createSession();
    });
    act(() => {
      result.current.actions.changeSessionDialogDraft("   ");
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    expect(createSession).not.toHaveBeenCalled();
    expect(result.current.sessionDialog).toMatchObject({
      error: "Session name must not be empty.",
      mode: "create",
    });
  });

  it("keeps the create flow open with pending and error states", async () => {
    const createSession = vi.fn(
      () =>
        new Promise<never>((_resolve, reject) => {
          setTimeout(() => reject(new Error("create failed")), 0);
        }),
    );
    const { result } = renderMainPageController({
      adapter: testAdapter({
        createSession,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.createSession();
    });
    act(() => {
      result.current.actions.changeSessionDialogDraft("New session");
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    await waitFor(() => {
      expect(result.current.isCreatingSession).toBe(true);
    });

    await waitFor(() => {
      expect(result.current.sessionDialog).toMatchObject({
        error: "New session command failed. Please retry.",
        mode: "create",
      });
    });
  });

  it("validates and submits session rename inline", async () => {
    const renameSession = vi.fn(async () => ({
      session: {
        id: "session-website-plan",
        name: "Renamed session",
      },
    }));
    const { result } = renderMainPageController({
      adapter: testAdapter({
        renameSession,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.snapshot.session.name).toBe(
        "Personal website plan",
      );
    });

    const activeSession = result.current.snapshotData?.snapshot.session;
    if (!activeSession) {
      throw new Error("Expected active session.");
    }

    act(() => {
      result.current.actions.renameSession(activeSession);
    });
    act(() => {
      result.current.actions.changeSessionDialogDraft("");
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    expect(renameSession).not.toHaveBeenCalled();
    expect(result.current.sessionDialog).toMatchObject({
      error: "Session name must not be empty.",
      mode: "rename",
    });

    act(() => {
      result.current.actions.changeSessionDialogDraft("Renamed session");
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    await waitFor(() => {
      expect(renameSession).toHaveBeenCalledWith({
        name: "Renamed session",
        sessionId: "session-website-plan",
      });
    });
    expect(result.current.sessionDialog.mode).toBe("idle");
  });

  it("keeps the rename flow open on command errors", async () => {
    const renameSession = vi.fn(async () => {
      throw new Error("rename failed");
    });
    const { result } = renderMainPageController({
      adapter: testAdapter({
        renameSession,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.snapshot.session.id).toBe(
        "session-website-plan",
      );
    });

    const activeSession = result.current.snapshotData?.snapshot.session;
    if (!activeSession) {
      throw new Error("Expected active session.");
    }

    act(() => {
      result.current.actions.renameSession(activeSession);
    });
    act(() => {
      result.current.actions.changeSessionDialogDraft("Renamed session");
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    await waitFor(() => {
      expect(result.current.sessionDialog).toMatchObject({
        error: "Rename session command failed. Please retry.",
        mode: "rename",
      });
    });
  });

  it("cancels and confirms session delete inline", async () => {
    const deleteSession = vi.fn(async () => ({
      deletedSessionId: "session-website-plan",
      nextSessionId: "session-next",
    }));
    const { result } = renderMainPageController({
      adapter: testAdapter({
        deleteSession,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.snapshot.session.id).toBe(
        "session-website-plan",
      );
    });

    const activeSession = result.current.snapshotData?.snapshot.session;
    if (!activeSession) {
      throw new Error("Expected active session.");
    }

    act(() => {
      result.current.actions.deleteSession(activeSession);
    });
    act(() => {
      result.current.actions.cancelSessionDialog();
    });

    expect(deleteSession).not.toHaveBeenCalled();
    expect(result.current.sessionDialog.mode).toBe("idle");

    act(() => {
      result.current.actions.deleteSession(activeSession);
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    await waitFor(() => {
      expect(deleteSession).toHaveBeenCalledWith("session-website-plan");
    });
    expect(result.current.activeSessionId).toBe("session-next");
    expect(result.current.sessionDialog.mode).toBe("idle");
  });

  it("keeps the delete confirmation open during pending and error states", async () => {
    const deleteSession = vi.fn(
      () =>
        new Promise<never>((_resolve, reject) => {
          setTimeout(() => reject(new Error("delete failed")), 0);
        }),
    );
    const { result } = renderMainPageController({
      adapter: testAdapter({
        deleteSession,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.snapshot.session.id).toBe(
        "session-website-plan",
      );
    });

    const activeSession = result.current.snapshotData?.snapshot.session;
    if (!activeSession) {
      throw new Error("Expected active session.");
    }

    act(() => {
      result.current.actions.deleteSession(activeSession);
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    await waitFor(() => {
      expect(result.current.isDeletingSession).toBe(true);
    });

    await waitFor(() => {
      expect(result.current.sessionDialog).toMatchObject({
        error: "Delete session command failed. Please retry.",
        mode: "delete",
      });
    });
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

  it("ignores duplicate runtime event cursors from finite SSE reconnects", async () => {
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

    const event = messageAppendedEvent("session-website-plan");
    act(() => {
      emitEvent?.(event);
      emitEvent?.(event);
    });

    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
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

function acceptedCommandResponse({
  commandId,
  taskNodeId,
}: {
  commandId: string;
  sessionId: string;
  taskNodeId: string;
}): CommandResponse {
  return {
    requestId: `request-${commandId}`,
    ok: true,
    result: {
      commandId,
      status: "accepted",
      message: "accepted",
      affectedTaskRefs: [{ kind: "published", id: taskNodeId }],
      objectRefs: [],
      affectedObjects: [],
      emittedMessageIds: [],
      publishedTaskIds: [`retry-${taskNodeId}`],
      debugRefs: {},
    },
    error: null,
    refresh: {
      waitForEvents: false,
      suggestedQueries: ["session.snapshot"],
      affectedTaskRefs: [{ kind: "published", id: taskNodeId }],
      affectedScopes: [],
    },
  };
}
