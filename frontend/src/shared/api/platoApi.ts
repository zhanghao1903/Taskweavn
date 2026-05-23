import type {
  CommandRequest,
  CommandResponse,
  ConfirmationId,
  EventCursor,
  MainPageSnapshot,
  QueryResponse,
  SessionId,
  SessionSummary,
  TaskNodeId,
  UiEvent,
  UiEventType,
} from "./types";
import { ApiClient } from "./client";
import type { ApiClientOptions } from "./client";
import {
  createFrontendLogger,
  toLoggableError,
} from "../logging/frontendLogger";

export type CreateSessionPayload = {
  name?: string;
  initialInput?: string;
};

export type RenameSessionPayload = {
  name: string;
};

export type SessionLifecycleResult = {
  deletedSessionId?: SessionId;
  nextSessionId?: SessionId | null;
  session?: Partial<SessionSummary> & { id: SessionId; name: string };
  sessionId?: SessionId;
};

export type SessionListResult = {
  sessions: SessionSummary[];
};

export type AppendSessionInputPayload = {
  content: string;
  mode: "global_guidance" | "generate_task_tree";
};

export type GenerateTaskTreePayload = {
  prompt: string;
  context?: Record<string, unknown>;
};

export type UpdateTaskNodePayload = {
  title?: string;
  summary?: string;
  fullIntent?: string;
  constraints?: string[];
  updateMode?: "node_fields" | "replace_children" | "replace_subtree";
  preserveRootId?: boolean;
};

export type AppendTaskInputPayload = {
  content: string;
  mode: "guidance" | "revision_request" | "clarification_answer";
};

export type PublishTaskTreePayload = {
  taskTreeId: string;
  startImmediately: boolean;
};

export type ResolveConfirmationPayload = {
  value: string;
  note?: string;
};

export type PlatoApi = {
  listSessions(): Promise<QueryResponse<SessionListResult>>;
  createSession(
    payload: CreateSessionPayload,
  ): Promise<QueryResponse<SessionLifecycleResult>>;
  getSessionSnapshot(
    sessionId: SessionId,
  ): Promise<QueryResponse<MainPageSnapshot>>;
  renameSession(
    sessionId: SessionId,
    payload: RenameSessionPayload,
  ): Promise<QueryResponse<SessionLifecycleResult>>;
  deleteSession(
    sessionId: SessionId,
  ): Promise<QueryResponse<SessionLifecycleResult>>;
  appendSessionInput(
    request: CommandRequest<AppendSessionInputPayload>,
  ): Promise<CommandResponse>;
  generateTaskTree(
    request: CommandRequest<GenerateTaskTreePayload>,
  ): Promise<CommandResponse>;
  updateTaskNode(
    sessionId: SessionId,
    taskNodeId: TaskNodeId,
    request: CommandRequest<UpdateTaskNodePayload>,
  ): Promise<CommandResponse>;
  appendTaskInput(
    sessionId: SessionId,
    taskNodeId: TaskNodeId,
    request: CommandRequest<AppendTaskInputPayload>,
  ): Promise<CommandResponse>;
  publishTaskTree(
    request: CommandRequest<PublishTaskTreePayload>,
  ): Promise<CommandResponse>;
  resolveConfirmation(
    sessionId: SessionId,
    confirmationId: ConfirmationId,
    request: CommandRequest<ResolveConfirmationPayload>,
  ): Promise<CommandResponse>;
  subscribeSessionEvents(
    sessionId: SessionId,
    cursor: EventCursor | null,
    onEvent: (event: UiEvent) => void,
  ): () => void;
};

export type EventSourceLike = {
  addEventListener(
    type: string,
    listener: (event: { data: string }) => void,
  ): void;
  close(): void;
};

export type EventSourceFactory = (url: string) => EventSourceLike;

export type HttpPlatoApiOptions = ApiClientOptions & {
  eventSourceFactory?: EventSourceFactory;
};

const uiEventTypes: UiEventType[] = [
  "session.status_changed",
  "session.resync_required",
  "task.tree.changed",
  "task.node.changed",
  "message.appended",
  "confirmation.created",
  "confirmation.resolved",
  "result.updated",
  "file_changes.updated",
  "audit.summary_updated",
  "command.completed",
  "command.failed",
];

const platoApiLogger = createFrontendLogger("plato-api");

export function createHttpPlatoApi(options: HttpPlatoApiOptions): PlatoApi {
  const client = new ApiClient(options);
  const eventSourceFactory =
    options.eventSourceFactory ?? createDefaultEventSource;

  return {
    listSessions() {
      return client.getJson<QueryResponse<SessionListResult>>("/api/v1/sessions");
    },
    createSession(payload) {
      return client.postJson<QueryResponse<SessionLifecycleResult>>(
        "/api/v1/sessions",
        payload,
      );
    },
    getSessionSnapshot(sessionId) {
      return client.getJson<QueryResponse<MainPageSnapshot>>(
        `/api/v1/sessions/${segment(sessionId)}/snapshot`,
      );
    },
    renameSession(sessionId, payload) {
      return client.patchJson<QueryResponse<SessionLifecycleResult>>(
        `/api/v1/sessions/${segment(sessionId)}`,
        payload,
      );
    },
    deleteSession(sessionId) {
      return client.postJson<QueryResponse<SessionLifecycleResult>>(
        `/api/v1/sessions/${segment(sessionId)}/delete`,
        {},
      );
    },
    appendSessionInput(request) {
      return client.postJson<CommandResponse>(
        `/api/v1/sessions/${segment(request.sessionId)}/input`,
        request,
      );
    },
    generateTaskTree(request) {
      return client.postJson<CommandResponse>(
        `/api/v1/sessions/${segment(request.sessionId)}/task-tree/generate`,
        request,
      );
    },
    updateTaskNode(sessionId, taskNodeId, request) {
      return client.patchJson<CommandResponse>(
        `/api/v1/sessions/${segment(sessionId)}/tasks/${segment(taskNodeId)}`,
        request,
      );
    },
    appendTaskInput(sessionId, taskNodeId, request) {
      return client.postJson<CommandResponse>(
        `/api/v1/sessions/${segment(sessionId)}/tasks/${segment(taskNodeId)}/input`,
        request,
      );
    },
    publishTaskTree(request) {
      return client.postJson<CommandResponse>(
        `/api/v1/sessions/${segment(request.sessionId)}/task-tree/publish`,
        request,
      );
    },
    resolveConfirmation(sessionId, confirmationId, request) {
      return client.postJson<CommandResponse>(
        `/api/v1/sessions/${segment(sessionId)}/confirmations/${segment(
          confirmationId,
        )}/respond`,
        request,
      );
    },
    subscribeSessionEvents(sessionId, cursor, onEvent) {
      const query = cursor === null ? "" : `?cursor=${segment(cursor)}`;
      const url = `${client.baseUrl}/api/v1/sessions/${segment(
        sessionId,
      )}/events${query}`;
      platoApiLogger.info("events.subscribe.start", {
        cursor,
        sessionId,
        url,
      });

      let source: EventSourceLike;
      try {
        source = eventSourceFactory(url);
      } catch (error) {
        platoApiLogger.error("events.subscribe.failed", {
          error: toLoggableError(error),
          sessionId,
          url,
        });
        throw error;
      }

      const handleEvent = (event: { data: string }) => {
        try {
          const parsed = JSON.parse(event.data) as UiEvent;
          platoApiLogger.debug("events.message", {
            eventId: parsed.eventId,
            eventType: parsed.eventType,
            sessionId: parsed.sessionId,
          });
          onEvent(parsed);
        } catch (error) {
          platoApiLogger.error("events.message.invalid", {
            error: toLoggableError(error),
            rawData: event.data,
            sessionId,
          });
        }
      };

      source.addEventListener("message", handleEvent);
      for (const eventType of uiEventTypes) {
        source.addEventListener(eventType, handleEvent);
      }

      return () => {
        platoApiLogger.info("events.subscribe.stop", {
          sessionId,
          url,
        });
        source.close();
      };
    },
  };
}

function segment(value: string): string {
  return encodeURIComponent(value);
}

function createDefaultEventSource(url: string): EventSourceLike {
  if (typeof EventSource === "undefined") {
    throw new Error("EventSource is not available in this environment.");
  }

  return new EventSource(url);
}
