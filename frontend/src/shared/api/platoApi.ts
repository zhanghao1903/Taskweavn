import type {
  CommandRequest,
  CommandResponse,
  ConfirmationId,
  EventCursor,
  MainPageSnapshot,
  QueryResponse,
  SessionId,
  TaskNodeId,
  UiEvent,
} from "./types";
import { ApiClient } from "./client";
import type { ApiClientOptions } from "./client";

export type CreateSessionPayload = {
  projectId: string;
  workflowId: string;
  name?: string;
  initialInput?: string;
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
  getSessionSnapshot(
    sessionId: SessionId,
  ): Promise<QueryResponse<MainPageSnapshot>>;
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
    type: "message",
    listener: (event: { data: string }) => void,
  ): void;
  close(): void;
};

export type EventSourceFactory = (url: string) => EventSourceLike;

export type HttpPlatoApiOptions = ApiClientOptions & {
  eventSourceFactory?: EventSourceFactory;
};

export function createHttpPlatoApi(options: HttpPlatoApiOptions): PlatoApi {
  const client = new ApiClient(options);
  const eventSourceFactory =
    options.eventSourceFactory ?? createDefaultEventSource;

  return {
    getSessionSnapshot(sessionId) {
      return client.getJson<QueryResponse<MainPageSnapshot>>(
        `/api/v1/sessions/${segment(sessionId)}/snapshot`,
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
      const source = eventSourceFactory(
        `${client.baseUrl}/api/v1/sessions/${segment(sessionId)}/events${query}`,
      );

      source.addEventListener("message", (event) => {
        onEvent(JSON.parse(event.data) as UiEvent);
      });

      return () => source.close();
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
