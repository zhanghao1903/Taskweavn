import type { PlatoApi } from "../../shared/api/platoApi";
import { ApiResponseError } from "../../shared/api/productErrors";
import type {
  MainPageSnapshot,
  QueryResponse,
  SessionId,
  WorkspaceId,
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
  | "archivePlan"
  | "cancelAsk"
  | "createSession"
  | "deferAsk"
  | "deleteSession"
  | "exportDiagnosticBundle"
  | "generateTaskTree"
  | "getSessionActivity"
  | "getSessionSnapshot"
  | "getTokenUsageSummary"
  | "listWorkspaces"
  | "listSessions"
  | "publishTaskTree"
  | "repairAuthoringState"
  | "renameSession"
  | "resolveConfirmation"
  | "retryTask"
  | "routeRuntimeInput"
  | "stopTask"
  | "subscribeSessionEvents"
  | "updateTaskNode"
>;

export type HttpMainPageAdapterOptions = {
  api: HttpMainPageApi;
  liveLabel?: string;
  sessionId?: SessionId | null;
  showStatePicker?: boolean;
  workspaceId?: WorkspaceId | null;
};

export const NO_SESSION_AVAILABLE_MESSAGE =
  "No Plato sessions exist yet. Create a session to start.";

const adapterLogger = createFrontendLogger("main-page-http-adapter");

export function createHttpMainPageAdapter({
  api,
  liveLabel = "Live Session",
  sessionId,
  showStatePicker = false,
  workspaceId = null,
}: HttpMainPageAdapterOptions): MainPageAdapter {
  function workspaceOptions(nextWorkspaceId?: WorkspaceId | null) {
    const resolvedWorkspaceId = nextWorkspaceId ?? workspaceId ?? null;
    return resolvedWorkspaceId === null
      ? undefined
      : { workspaceId: resolvedWorkspaceId };
  }

  return {
    answerAsk(nextSessionId, askId, request, nextWorkspaceId) {
      return api.answerAsk(
        nextSessionId,
        askId,
        request,
        workspaceOptions(nextWorkspaceId),
      );
    },
    answerAuthoringAskBatch(nextSessionId, rawTaskId, request, nextWorkspaceId) {
      return api.answerAuthoringAskBatch(
        nextSessionId,
        rawTaskId,
        request,
        workspaceOptions(nextWorkspaceId),
      );
    },
    appendSessionInput(request, nextWorkspaceId) {
      return api.appendSessionInput(request, workspaceOptions(nextWorkspaceId));
    },
    appendTaskInput(nextSessionId, taskNodeId, request, nextWorkspaceId) {
      return api.appendTaskInput(
        nextSessionId,
        taskNodeId,
        request,
        workspaceOptions(nextWorkspaceId),
      );
    },
    archivePlan(nextSessionId, planId, request, nextWorkspaceId) {
      return api.archivePlan(
        nextSessionId,
        planId,
        request,
        workspaceOptions(nextWorkspaceId),
      );
    },
    generateTaskTree(request, nextWorkspaceId) {
      return api.generateTaskTree(request, workspaceOptions(nextWorkspaceId));
    },
    async loadSnapshot(stateId, nextSessionId, nextWorkspaceId) {
      const activeSessionId = await resolveActiveSessionId(
        api,
        nextSessionId ?? sessionId,
        nextWorkspaceId ?? workspaceId,
      );
      adapterLogger.info("snapshot.load.start", {
        sessionId: activeSessionId,
        stateId,
        workspaceId: nextWorkspaceId ?? workspaceId ?? null,
      });

      try {
        const response = await api.getSessionSnapshot(
          activeSessionId,
          workspaceOptions(nextWorkspaceId),
        );
        adapterLogger.debug("snapshot.load.response", {
          ok: response.ok,
          requestId: response.requestId,
          sessionId: activeSessionId,
          stateId,
          workspaceId: nextWorkspaceId ?? workspaceId ?? null,
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
          workspaceId: nextWorkspaceId ?? workspaceId ?? null,
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
            workspaceId: nextWorkspaceId ?? workspaceId ?? null,
          },
        );
        throw error;
      }
    },
    async createSession(payload, nextWorkspaceId) {
      const response = await api.createSession(
        payload,
        workspaceOptions(nextWorkspaceId),
      );
      return unwrapLifecycle(response);
    },
    async renameSession(payload, nextWorkspaceId) {
      const response = await api.renameSession(
        payload.sessionId,
        {
          name: payload.name,
        },
        workspaceOptions(nextWorkspaceId),
      );
      return unwrapLifecycle(response);
    },
    async deleteSession(nextSessionId, nextWorkspaceId) {
      const response = await api.deleteSession(
        nextSessionId,
        workspaceOptions(nextWorkspaceId),
      );
      return unwrapLifecycle(response);
    },
    async exportDiagnosticBundle(nextSessionId, nextWorkspaceId) {
      const response = await api.exportDiagnosticBundle(
        nextSessionId,
        workspaceOptions(nextWorkspaceId),
      );
      return unwrapLifecycle(response);
    },
    cancelAsk(nextSessionId, askId, request, nextWorkspaceId) {
      return api.cancelAsk(
        nextSessionId,
        askId,
        request,
        workspaceOptions(nextWorkspaceId),
      );
    },
    deferAsk(nextSessionId, askId, request, nextWorkspaceId) {
      return api.deferAsk(
        nextSessionId,
        askId,
        request,
        workspaceOptions(nextWorkspaceId),
      );
    },
    resolveConfirmation(nextSessionId, confirmationId, request, nextWorkspaceId) {
      return api.resolveConfirmation(
        nextSessionId,
        confirmationId,
        request,
        workspaceOptions(nextWorkspaceId),
      );
    },
    async loadWorkspaceCatalog() {
      const response = await api.listWorkspaces();
      return unwrapLifecycle(response);
    },
    async loadTokenUsageSummary(request, nextWorkspaceId) {
      const response = await api.getTokenUsageSummary(
        request,
        workspaceOptions(nextWorkspaceId),
      );
      return unwrapLifecycle(response);
    },
    async loadSessionActivity(request, nextWorkspaceId) {
      const response = await api.getSessionActivity(
        request,
        workspaceOptions(nextWorkspaceId),
      );
      return unwrapLifecycle(response);
    },
    routeRuntimeInput(request, nextWorkspaceId) {
      return api.routeRuntimeInput(request, workspaceOptions(nextWorkspaceId));
    },
    publishTaskTree(request, nextWorkspaceId) {
      return api.publishTaskTree(request, workspaceOptions(nextWorkspaceId));
    },
    repairAuthoringState(request, nextWorkspaceId) {
      return api.repairAuthoringState(request, workspaceOptions(nextWorkspaceId));
    },
    retryTask(nextSessionId, taskNodeId, request, nextWorkspaceId) {
      return api.retryTask(
        nextSessionId,
        taskNodeId,
        request,
        workspaceOptions(nextWorkspaceId),
      );
    },
    stopTask(nextSessionId, taskNodeId, request, nextWorkspaceId) {
      return api.stopTask(
        nextSessionId,
        taskNodeId,
        request,
        workspaceOptions(nextWorkspaceId),
      );
    },
    runtimeKind: "http",
    sessionId: sessionId ?? null,
    showStatePicker,
    subscribeSessionEvents(nextSessionId, cursor, onEvent, nextWorkspaceId) {
      return api.subscribeSessionEvents(
        nextSessionId,
        cursor,
        onEvent,
        workspaceOptions(nextWorkspaceId),
      );
    },
    updateTaskNode(nextSessionId, taskNodeId, request, nextWorkspaceId) {
      return api.updateTaskNode(
        nextSessionId,
        taskNodeId,
        request,
        workspaceOptions(nextWorkspaceId),
      );
    },
    workspaceId,
  };
}

async function resolveActiveSessionId(
  api: Pick<PlatoApi, "listSessions">,
  preferredSessionId: SessionId | null | undefined,
  workspaceId: WorkspaceId | null | undefined,
): Promise<SessionId> {
  if (preferredSessionId) {
    return preferredSessionId;
  }

  const sessions = unwrapLifecycle(
    await api.listSessions(
      workspaceId === null || workspaceId === undefined
        ? undefined
        : { workspaceId },
    ),
  ).sessions;
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
