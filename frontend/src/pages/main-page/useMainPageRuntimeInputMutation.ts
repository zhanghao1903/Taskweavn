import { useMutation } from "@tanstack/react-query";
import type { Dispatch, SetStateAction } from "react";

import { productRecoveryActionsFromApiError } from "../../shared/api/productErrors";
import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type {
  RuntimeInputMode,
  RuntimeInputPendingClarification,
  SessionActivityItemView,
  TaskNodeId,
  WorkspaceId,
} from "../../shared/api/types";
import type { InputTarget } from "./mainPageUiTypes";
import {
  buildRuntimeInputRouteRequest,
  prependRuntimeActivityItems,
  runtimeInputActivity,
  runtimeInputNotice,
  runtimeInputUserActivity,
} from "./mainPageRuntimeInput";
import { handleCommandResponse } from "./runtime/commandRefresh";
import type {
  MainPageAdapter,
  MainPageRuntimeSnapshot,
} from "./runtime/adapter";

type SnapshotRefetchResult = {
  data?: MainPageRuntimeSnapshot;
  status: string;
};

type CommandErrorSetter = (
  message: string | null,
  recoveryActions?: ProductRecoveryAction[],
) => void;

export type RuntimeInputMutationContext = {
  commandId: string;
  content: string;
  routeMode: RuntimeInputMode;
  sessionId: string;
  target: InputTarget;
  taskNodeId: TaskNodeId | null;
};

export type UseMainPageRuntimeInputMutationOptions = {
  activeWorkspaceId: WorkspaceId | null;
  adapter: MainPageAdapter;
  getSnapshotData: () => MainPageRuntimeSnapshot | undefined;
  refetchSnapshot: () => Promise<SnapshotRefetchResult>;
  acceptRuntimeInputSubmit: (commandId: string) => void;
  failRuntimeInputSubmit: (context: {
    commandId: string;
    message: string;
    recoveryActions: ProductRecoveryAction[];
  }) => void;
  pendingRuntimeClarification: RuntimeInputPendingClarification | null;
  reconcileRuntimeInputSubmit: (commandId: string) => void;
  rejectRuntimeInputSubmit: (context: {
    commandId: string;
    message: string;
    recoveryActions: ProductRecoveryAction[];
  }) => void;
  setActiveRuntimeInputMode: (mode: RuntimeInputMode | null) => void;
  setInputCommandError: CommandErrorSetter;
  setInputDraft: (draft: string) => void;
  setPendingRuntimeClarification: (
    clarification: RuntimeInputPendingClarification | null,
  ) => void;
  setRuntimeActivityItems: Dispatch<
    SetStateAction<SessionActivityItemView[]>
  >;
  setUiNotice: (notice: string | null) => void;
  startRuntimeInputSubmit: (context: {
    body: string;
    commandId: string;
    createdAt: string;
    scope: {
      scopeKind: "session" | "plan" | "task";
      planId: string | null;
      taskNodeId: TaskNodeId | null;
    };
    sessionId: string;
    workspaceId: WorkspaceId | null;
  }) => void;
};

export function useMainPageRuntimeInputMutation({
  activeWorkspaceId,
  adapter,
  getSnapshotData,
  refetchSnapshot,
  acceptRuntimeInputSubmit,
  failRuntimeInputSubmit,
  pendingRuntimeClarification,
  reconcileRuntimeInputSubmit,
  rejectRuntimeInputSubmit,
  setActiveRuntimeInputMode,
  setInputCommandError,
  setInputDraft,
  setPendingRuntimeClarification,
  setRuntimeActivityItems,
  setUiNotice,
  startRuntimeInputSubmit,
}: UseMainPageRuntimeInputMutationOptions) {
  return useMutation({
    mutationFn: async ({
      commandId,
      content,
      routeMode,
      sessionId,
      target,
      taskNodeId,
    }: RuntimeInputMutationContext) => {
      if (adapter.routeRuntimeInput === undefined) {
        throw new Error("Runtime input router is unavailable.");
      }

      const request = buildRuntimeInputRouteRequest({
        commandId,
        content,
        mode: routeMode,
        pendingClarification: pendingRuntimeClarification,
        sessionId,
        snapshot: getSnapshotData()?.snapshot ?? null,
        target,
        taskNodeId,
      });
      const response = await adapter.routeRuntimeInput(
        request,
        activeWorkspaceId,
      );
      return { request, response };
    },
    onError: (_error, variables) => {
      const message = "Question routing failed. Please retry.";
      failRuntimeInputSubmit({
        commandId: variables.commandId,
        message,
        recoveryActions: [],
      });
      setInputCommandError(message);
    },
    onMutate: ({
      commandId,
      content,
      routeMode,
      sessionId,
      target,
      taskNodeId,
    }) => {
      const request = buildRuntimeInputRouteRequest({
        commandId,
        content,
        mode: routeMode,
        pendingClarification: pendingRuntimeClarification,
        sessionId,
        snapshot: getSnapshotData()?.snapshot ?? null,
        target,
        taskNodeId,
      });

      startRuntimeInputSubmit({
        body: request.content,
        commandId: request.commandId,
        createdAt: new Date().toISOString(),
        scope: {
          planId: request.selection.planId ?? null,
          scopeKind: request.selection.scopeKind,
          taskNodeId: request.selection.taskNodeId ?? null,
        },
        sessionId: request.sessionId,
        workspaceId: activeWorkspaceId,
      });
    },
    onSettled: () => {
      setActiveRuntimeInputMode(null);
    },
    onSuccess: ({ request, response }) => {
      if (!response.ok || response.data === null) {
        const message =
          response.error?.message ?? "Question could not be answered.";
        const recoveryActions = productRecoveryActionsFromApiError(
          response.error,
        );
        rejectRuntimeInputSubmit({
          commandId: request.commandId,
          message,
          recoveryActions,
        });
        setInputCommandError(
          message,
          recoveryActions,
        );
        return;
      }

      const routeResult = response.data;
      if (
        routeResult.commandResponse !== null &&
        routeResult.commandResponse !== undefined
      ) {
        setPendingRuntimeClarification(null);
        const commandResult = handleCommandResponse(
          routeResult.commandResponse,
          "Runtime input command was rejected.",
        );

        if (commandResult.errorMessage) {
          rejectRuntimeInputSubmit({
            commandId: request.commandId,
            message: commandResult.errorMessage,
            recoveryActions: commandResult.recoveryActions,
          });
          setInputCommandError(
            commandResult.errorMessage,
            commandResult.recoveryActions,
          );
          return;
        }

        acceptRuntimeInputSubmit(request.commandId);
        reconcileRuntimeInputSubmit(request.commandId);
        setInputCommandError(null);
        setInputDraft("");
        setUiNotice(routeResult.outcome.userMessage);
        if (commandResult.shouldRefetch) {
          void refetchSnapshot();
        }
        return;
      }

      if (
        routeResult.outcome.status === "answered" ||
        routeResult.outcome.status === "dispatched"
      ) {
        setPendingRuntimeClarification(null);
        const runtimeActivity = runtimeInputActivity(routeResult);
        const runtimeActivities = [
          runtimeInputUserActivity(request, routeResult),
          ...(runtimeActivity === null ? [] : [runtimeActivity]),
        ];
        if (runtimeActivities.length > 0) {
          reconcileRuntimeInputSubmit(request.commandId);
          setRuntimeActivityItems((items) =>
            prependRuntimeActivityItems(items, runtimeActivities),
          );
        }
        setInputCommandError(null);
        setInputDraft("");
        setUiNotice(runtimeInputNotice(routeResult));
        void refetchSnapshot();
        return;
      }

      rejectRuntimeInputSubmit({
        commandId: request.commandId,
        message: routeResult.outcome.userMessage,
        recoveryActions: routeResult.outcome.recoveryActions,
      });
      setInputCommandError(
        routeResult.outcome.userMessage,
        routeResult.outcome.recoveryActions,
      );
      setPendingRuntimeClarification(
        routeResult.outcome.pendingClarification ?? null,
      );
    },
  });
}
