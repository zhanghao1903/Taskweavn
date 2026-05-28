import type { PlatoApi } from "../../shared/api/platoApi";
import type {
  MainPageSnapshot,
  QueryResponse,
  SessionId,
} from "../../shared/api/types";
import {
  createFrontendLogger,
  summarizeLoggableError,
  toLoggableError,
} from "../../shared/logging/frontendLogger";
import type { MainPageAdapter } from "./runtime/adapter";
import { deriveMainPageMetadataFromSnapshot } from "./runtime/metadata";

export type HttpMainPageAdapterOptions = {
  api: PlatoApi;
  liveLabel?: string;
  sessionId?: SessionId | null;
  showStatePicker?: boolean;
};

export const NO_SESSION_AVAILABLE_MESSAGE =
  "No Plato sessions exist yet. Create a session to start.";

const adapterLogger = createFrontendLogger("main-page-http-adapter");

export function createHttpMainPageAdapter({
  api,
  liveLabel = "Live Session",
  sessionId,
  showStatePicker = false,
}: HttpMainPageAdapterOptions): MainPageAdapter {
  return {
    appendSessionInput(request) {
      return api.appendSessionInput(request);
    },
    appendTaskInput(nextSessionId, taskNodeId, request) {
      return api.appendTaskInput(nextSessionId, taskNodeId, request);
    },
    generateTaskTree(request) {
      return api.generateTaskTree(request);
    },
    async loadSnapshot(stateId, nextSessionId) {
      const activeSessionId = await resolveActiveSessionId(
        api,
        nextSessionId ?? sessionId,
      );
      adapterLogger.info("snapshot.load.start", {
        sessionId: activeSessionId,
        stateId,
      });

      try {
        const response = await api.getSessionSnapshot(activeSessionId);
        adapterLogger.debug("snapshot.load.response", {
          ok: response.ok,
          requestId: response.requestId,
          sessionId: activeSessionId,
          stateId,
        });

        const snapshot = unwrapSnapshot(response);
        const metadata = deriveMainPageMetadataFromSnapshot(snapshot, {
          id: stateId,
          label: liveLabel,
        });

        adapterLogger.info("snapshot.load.success", {
          ...summarizeSnapshot(snapshot),
          detailMode: metadata.detail.mode,
          sessionId: activeSessionId,
          stateId,
        });

        return {
          metadata,
          snapshot,
        };
      } catch (error) {
        adapterLogger.error(
          `snapshot.load.failed ${sessionId} -> ${summarizeLoggableError(
            error,
          )}`,
          {
            error: toLoggableError(error),
            sessionId: activeSessionId,
            stateId,
          },
        );
        throw error;
      }
    },
    async createSession(payload) {
      const response = await api.createSession(payload);
      return unwrapLifecycle(response);
    },
    async renameSession(payload) {
      const response = await api.renameSession(payload.sessionId, {
        name: payload.name,
      });
      return unwrapLifecycle(response);
    },
    async deleteSession(nextSessionId) {
      const response = await api.deleteSession(nextSessionId);
      return unwrapLifecycle(response);
    },
    resolveConfirmation(nextSessionId, confirmationId, request) {
      return api.resolveConfirmation(nextSessionId, confirmationId, request);
    },
    publishTaskTree(request) {
      return api.publishTaskTree(request);
    },
    runtimeKind: "http",
    sessionId: sessionId ?? null,
    showStatePicker,
    subscribeSessionEvents(nextSessionId, cursor, onEvent) {
      return api.subscribeSessionEvents(nextSessionId, cursor, onEvent);
    },
    updateTaskNode(nextSessionId, taskNodeId, request) {
      return api.updateTaskNode(nextSessionId, taskNodeId, request);
    },
  };
}

async function resolveActiveSessionId(
  api: PlatoApi,
  preferredSessionId: SessionId | null | undefined,
): Promise<SessionId> {
  if (preferredSessionId) {
    return preferredSessionId;
  }

  const sessions = unwrapLifecycle(await api.listSessions()).sessions;
  if (sessions.length > 0) {
    return sessions[0].id;
  }

  throw new Error(NO_SESSION_AVAILABLE_MESSAGE);
}

function summarizeSnapshot(snapshot: MainPageSnapshot) {
  return {
    confirmationCount: snapshot.pendingConfirmations.length,
    cursor: snapshot.cursor,
    messageCount: snapshot.messages.length,
    projectId: snapshot.project.id,
    sessionStatus: snapshot.session.status,
    taskNodeCount: snapshot.taskTree?.nodes.length ?? 0,
    taskTreeStatus: snapshot.taskTree?.status ?? null,
    workflowId: snapshot.workflow.id,
  };
}

function unwrapSnapshot(
  response: QueryResponse<MainPageSnapshot>,
): MainPageSnapshot {
  if (!response.ok || response.data === null) {
    throw new Error(response.error?.message ?? "Unable to load session snapshot.");
  }

  return response.data;
}

function unwrapLifecycle<T>(response: QueryResponse<T>): T {
  if (!response.ok || response.data === null) {
    throw new Error(response.error?.message ?? "Session command failed.");
  }

  return response.data;
}
