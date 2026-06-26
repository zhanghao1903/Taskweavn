import { useMutation } from "@tanstack/react-query";
import type { Dispatch, SetStateAction } from "react";

import { productRecoveryActionsFromApiError } from "../../shared/api/productErrors";
import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type {
  RuntimeInputMode,
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
  setActiveRuntimeInputMode: (mode: RuntimeInputMode | null) => void;
  setInputCommandError: CommandErrorSetter;
  setInputDraft: (draft: string) => void;
  setRuntimeActivityItems: Dispatch<
    SetStateAction<SessionActivityItemView[]>
  >;
  setUiNotice: (notice: string | null) => void;
};

export function useMainPageRuntimeInputMutation({
  activeWorkspaceId,
  adapter,
  getSnapshotData,
  refetchSnapshot,
  setActiveRuntimeInputMode,
  setInputCommandError,
  setInputDraft,
  setRuntimeActivityItems,
  setUiNotice,
}: UseMainPageRuntimeInputMutationOptions) {
  return useMutation({
    mutationFn: async ({
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
        content,
        mode: routeMode,
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
    onError: () => {
      setInputCommandError("Question routing failed. Please retry.");
    },
    onSettled: () => {
      setActiveRuntimeInputMode(null);
    },
    onSuccess: ({ request, response }) => {
      if (!response.ok || response.data === null) {
        setInputCommandError(
          response.error?.message ?? "Question could not be answered.",
          productRecoveryActionsFromApiError(response.error),
        );
        return;
      }

      const routeResult = response.data;
      if (
        routeResult.commandResponse !== null &&
        routeResult.commandResponse !== undefined
      ) {
        const commandResult = handleCommandResponse(
          routeResult.commandResponse,
          "Runtime input command was rejected.",
        );

        if (commandResult.errorMessage) {
          setInputCommandError(
            commandResult.errorMessage,
            commandResult.recoveryActions,
          );
          return;
        }

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
        const runtimeActivity = runtimeInputActivity(routeResult);
        const runtimeActivities = [
          runtimeInputUserActivity(request, routeResult),
          ...(runtimeActivity === null ? [] : [runtimeActivity]),
        ];
        if (runtimeActivities.length > 0) {
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

      setInputCommandError(
        routeResult.outcome.userMessage,
        routeResult.outcome.recoveryActions,
      );
    },
  });
}
