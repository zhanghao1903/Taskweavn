import type { PlatoApi } from "../../shared/api/platoApi";
import { ApiResponseError } from "../../shared/api/productErrors";
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
import { summarizeMainPageSnapshot } from "../../shared/api/traceSummary";

export type HttpMainPageApi = Pick<
  PlatoApi,
  | "answerAsk"
  | "answerAuthoringAskBatch"
  | "appendSessionInput"
  | "appendTaskInput"
  | "cancelAsk"
  | "createSession"
  | "deferAsk"
  | "deleteSession"
  | "generateTaskTree"
  | "getSessionSnapshot"
  | "listSessions"
  | "publishTaskTree"
  | "repairAuthoringState"
  | "renameSession"
  | "resolveConfirmation"
  | "retryTask"
  | "stopTask"
  | "subscribeSessionEvents"
  | "updateTaskNode"
>;

export type HttpMainPageAdapterOptions = {
  api: HttpMainPageApi;
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
    answerAsk(nextSessionId, askId, request) {
      return api.answerAsk(nextSessionId, askId, request);
    },
    answerAuthoringAskBatch(nextSessionId, rawTaskId, request) {
      return api.answerAuthoringAskBatch(nextSessionId, rawTaskId, request);
    },
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
          ...summarizeMainPageSnapshot(snapshot),
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
    cancelAsk(nextSessionId, askId, request) {
      return api.cancelAsk(nextSessionId, askId, request);
    },
    deferAsk(nextSessionId, askId, request) {
      return api.deferAsk(nextSessionId, askId, request);
    },
    resolveConfirmation(nextSessionId, confirmationId, request) {
      return api.resolveConfirmation(nextSessionId, confirmationId, request);
    },
    publishTaskTree(request) {
      return api.publishTaskTree(request);
    },
    repairAuthoringState(request) {
      return api.repairAuthoringState(request);
    },
    retryTask(nextSessionId, taskNodeId, request) {
      return api.retryTask(nextSessionId, taskNodeId, request);
    },
    stopTask(nextSessionId, taskNodeId, request) {
      return api.stopTask(nextSessionId, taskNodeId, request);
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
  api: Pick<PlatoApi, "listSessions">,
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

function unwrapSnapshot(
  response: QueryResponse<MainPageSnapshot>,
): MainPageSnapshot {
  if (!response.ok || response.data === null) {
    if (response.error) {
      throw new ApiResponseError(
        response.error,
        "Unable to load session snapshot.",
      );
    }

    throw new Error("Unable to load session snapshot.");
  }

  return response.data;
}

function unwrapLifecycle<T>(response: QueryResponse<T>): T {
  if (!response.ok || response.data === null) {
    if (response.error) {
      throw new ApiResponseError(response.error, "Session command failed.");
    }

    throw new Error("Session command failed.");
  }

  return response.data;
}
