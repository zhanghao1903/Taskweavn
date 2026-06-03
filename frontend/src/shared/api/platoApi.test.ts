import { describe, expect, it, vi } from "vitest";

import { createHttpPlatoApi } from "./platoApi";
import type {
  AppendTaskInputPayload,
  EventSourceLike,
  ResolveConfirmationPayload,
} from "./platoApi";
import type {
  CommandRequest,
  CommandResponse,
  MainPageSnapshot,
  UiEvent,
} from "./types";
import type { FetchFn } from "./client";

describe("createHttpPlatoApi", () => {
  it("loads a session snapshot through the documented endpoint", async () => {
    const fetcher = vi.fn<FetchFn>(async () =>
      jsonResponse({
        cursor: "cursor-1",
        data: { session: { id: "session-1" } } as MainPageSnapshot,
        error: null,
        generatedAt: "2026-05-17T10:00:00+08:00",
        ok: true,
        requestId: "query-1",
      }),
    );
    const api = createHttpPlatoApi({
      baseUrl: "https://plato.test/",
      fetcher,
    });

    await expect(api.getSessionSnapshot("session 1")).resolves.toMatchObject({
      data: {
        session: {
          id: "session-1",
        },
      },
      ok: true,
    });
    expect(fetcher).toHaveBeenCalledWith(
      "https://plato.test/api/v1/sessions/session%201/snapshot",
      expect.objectContaining({
        method: "GET",
      }),
    );
  });

  it("posts command requests to session and task endpoints", async () => {
    const calls: Array<{
      body: unknown;
      method: string | undefined;
      url: string;
    }> = [];
    const fetcher = vi.fn<FetchFn>(async (input, init) => {
      calls.push({
        body: init?.body ? JSON.parse(String(init.body)) : null,
        method: init?.method,
        url: String(input),
      });

      return jsonResponse(acceptedCommandResponse("command-1"));
    });
    const api = createHttpPlatoApi({
      baseUrl: "https://plato.test",
      fetcher,
    });
    const taskRequest: CommandRequest<AppendTaskInputPayload> = {
      commandId: "command-task",
      sessionId: "session/1",
      payload: {
        content: "Use warmer typography.",
        mode: "guidance",
      },
    };
    const confirmationRequest: CommandRequest<ResolveConfirmationPayload> = {
      commandId: "command-confirm",
      sessionId: "session/1",
      payload: {
        value: "confirmed",
      },
    };

    await api.appendTaskInput("session/1", "task node", taskRequest);
    await api.resolveConfirmation(
      "session/1",
      "confirmation#1",
      confirmationRequest,
    );

    expect(calls).toEqual([
      {
        body: taskRequest,
        method: "POST",
        url: "https://plato.test/api/v1/sessions/session%2F1/tasks/task%20node/input",
      },
      {
        body: confirmationRequest,
        method: "POST",
        url: "https://plato.test/api/v1/sessions/session%2F1/confirmations/confirmation%231/respond",
      },
    ]);
  });

  it("sends session lifecycle requests to documented endpoints", async () => {
    const calls: Array<{
      body: unknown;
      method: string | undefined;
      url: string;
    }> = [];
    const fetcher = vi.fn<FetchFn>(async (input, init) => {
      calls.push({
        body: init?.body ? JSON.parse(String(init.body)) : null,
        method: init?.method,
        url: String(input),
      });

      return jsonResponse({
        ok: true,
        data: {
          sessionId: "session-1",
        },
        error: null,
      });
    });
    const api = createHttpPlatoApi({
      baseUrl: "https://plato.test",
      fetcher,
    });

    await api.listSessions();
    await api.createSession({ name: "New session" });
    await api.renameSession("session 1", { name: "Renamed" });
    await api.deleteSession("session 1");

    expect(calls).toEqual([
      {
        body: null,
        method: "GET",
        url: "https://plato.test/api/v1/sessions",
      },
      {
        body: { name: "New session" },
        method: "POST",
        url: "https://plato.test/api/v1/sessions",
      },
      {
        body: { name: "Renamed" },
        method: "PATCH",
        url: "https://plato.test/api/v1/sessions/session%201",
      },
      {
        body: {},
        method: "POST",
        url: "https://plato.test/api/v1/sessions/session%201/delete",
      },
    ]);
  });

  it("patches TaskNode updates and publishes TaskTrees", async () => {
    const calls: string[] = [];
    const fetcher = vi.fn<FetchFn>(async (input, init) => {
      calls.push(`${init?.method ?? "GET"} ${String(input)}`);

      return jsonResponse(acceptedCommandResponse("command-2"));
    });
    const api = createHttpPlatoApi({
      baseUrl: "https://plato.test",
      fetcher,
    });

    await api.updateTaskNode("session-1", "task-1", {
      commandId: "command-update",
      sessionId: "session-1",
      payload: {
        summary: "Updated summary",
      },
    });
    await api.publishTaskTree({
      commandId: "command-publish",
      sessionId: "session-1",
      payload: {
        startImmediately: true,
        taskTreeId: "task-tree-1",
      },
    });
    await api.retryTask("session-1", "task-1", {
      commandId: "command-retry",
      sessionId: "session-1",
      payload: {
        instruction: "Try the safer path",
        startImmediately: true,
      },
    });
    await api.stopTask("session-1", "task-1", {
      commandId: "command-stop",
      sessionId: "session-1",
      payload: {
        reason: "user requested stop",
      },
    });

    expect(calls).toEqual([
      "PATCH https://plato.test/api/v1/sessions/session-1/tasks/task-1",
      "POST https://plato.test/api/v1/sessions/session-1/task-tree/publish",
      "POST https://plato.test/api/v1/sessions/session-1/tasks/task-1/retry",
      "POST https://plato.test/api/v1/sessions/session-1/tasks/task-1/stop",
    ]);
  });

  it("loads Audit Page query resources through documented endpoint candidates", async () => {
    const calls: string[] = [];
    const fetcher = vi.fn<FetchFn>(async (input, init) => {
      calls.push(`${init?.method ?? "GET"} ${String(input)}`);

      return jsonResponse({
        data: null,
        error: null,
        generatedAt: "2026-05-24T10:00:00Z",
        ok: true,
        requestId: "audit-query",
      });
    });
    const api = createHttpPlatoApi({
      baseUrl: "https://plato.test",
      fetcher,
    });

    await api.getAuditSnapshot({
      entry: "from_task",
      filter: "risks",
      includeDetail: true,
      limit: 50,
      recordId: "record 1",
      sessionId: "session/1",
      taskNodeId: "task 1",
    });
    await api.listAuditRecords({
      filter: "files",
      includeHiddenReasons: true,
      kind: "file_change",
      sessionId: "session/1",
      taskNodeId: "task 1",
    });
    await api.getAuditRecordDetail({
      includeEvidence: true,
      recordId: "record 1",
      sessionId: "session/1",
    });
    await api.getEvidenceDetail({
      evidenceId: "evidence 1",
      includeSanitizedPayload: false,
      sessionId: "session/1",
    });

    expect(calls).toEqual([
      "GET https://plato.test/api/v1/sessions/session%2F1/tasks/task%201/audit?entry=from_task&filter=risks&includeDetail=true&limit=50&recordId=record+1",
      "GET https://plato.test/api/v1/sessions/session%2F1/tasks/task%201/audit/records?filter=files&includeHiddenReasons=true&kind=file_change",
      "GET https://plato.test/api/v1/sessions/session%2F1/audit/records/record%201?includeEvidence=true",
      "GET https://plato.test/api/v1/sessions/session%2F1/audit/evidence/evidence%201?includeSanitizedPayload=false",
    ]);
  });

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

function acceptedCommandResponse(commandId: string): CommandResponse {
  return {
    error: null,
    ok: true,
    refresh: {
      affectedTaskRefs: [],
      affectedScopes: [],
      suggestedQueries: [],
      waitForEvents: true,
    },
    requestId: `request-${commandId}`,
    result: {
      affectedTaskRefs: [],
      affectedObjects: [],
      commandId,
      debugRefs: {},
      emittedMessageIds: [],
      message: "accepted",
      objectRefs: [],
      publishedTaskIds: [],
      status: "accepted",
    },
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    headers: {
      "Content-Type": "application/json",
    },
    status,
  });
}
