import { useMutation } from "@tanstack/react-query";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import { productRecoveryActionsFromApiError } from "../../shared/api/productErrors";
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
  runtimeInputModeFor,
  runtimeInputNotice,
  runtimeInputUserActivity,
} from "./mainPageRuntimeInput";
import type { MainPageInputCommandMode } from "./mainPageViewModel";
import { handleCommandResponse } from "./runtime/commandRefresh";
import type {
  MainPageAdapter,
  MainPageRuntimeSnapshot,
} from "./runtime/adapter";

type SnapshotRefetch = () => Promise<unknown>;

type SetInputCommandError = (
  message: string | null,
  recoveryActions?: ProductRecoveryAction[],
) => void;

export type InputSubmitContext = {
  mode: MainPageInputCommandMode;
  sessionId: string;
  target: InputTarget;
  taskNodeId: TaskNodeId | null;
};

type SubmitRuntimeInputContext = InputSubmitContext & {
  content: string;
};

export type UseMainPageRuntimeInputCommandsOptions = {
  activeWorkspaceId: WorkspaceId | null;
  adapter: MainPageAdapter;
  getSnapshot: () => MainPageRuntimeSnapshot | undefined;
  refetchSnapshot: SnapshotRefetch;
  setActiveRuntimeInputMode: (mode: RuntimeInputMode | null) => void;
  setInputCommandError: SetInputCommandError;
  setInputDraft: (draft: string) => void;
  setRuntimeActivityItems: (
    update: (items: SessionActivityItemView[]) => SessionActivityItemView[],
  ) => void;
  setUiNotice: (notice: string | null) => void;
};

export function useMainPageRuntimeInputCommands({
  activeWorkspaceId,
  adapter,
  getSnapshot,
  refetchSnapshot,
  setActiveRuntimeInputMode,
  setInputCommandError,
  setInputDraft,
  setRuntimeActivityItems,
  setUiNotice,
}: UseMainPageRuntimeInputCommandsOptions) {
  const inputMutation = useMutation({
    mutationFn: async ({
      content,
      mode,
      sessionId,
      target,
      taskNodeId,
    }: SubmitRuntimeInputContext) => {
      const commandId = `append-${target}-${Date.now()}`;

      if (mode === "append_task_input" && taskNodeId) {
        return adapter.appendTaskInput(sessionId, taskNodeId, {
          commandId,
          sessionId,
          payload: {
            content,
            mode: "guidance",
          },
        }, activeWorkspaceId);
      }

      if (mode === "generate_task_tree") {
        return adapter.generateTaskTree({
          commandId: `generate-task-tree-${Date.now()}`,
          sessionId,
          payload: {
            prompt: content,
          },
        }, activeWorkspaceId);
      }

      return adapter.appendSessionInput({
        commandId,
        sessionId,
        payload: {
          content,
          mode: "global_guidance",
        },
      }, activeWorkspaceId);
    },
    onError: () => {
      setInputCommandError("Input submission failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Input submission was rejected.",
      );

      if (result.errorMessage) {
        setInputCommandError(result.errorMessage, result.recoveryActions);
        return;
      }

      setInputCommandError(null);
      setInputDraft("");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  const runtimeInputMutation = useMutation({
    mutationFn: async ({
      content,
      routeMode,
      sessionId,
      target,
      taskNodeId,
    }: SubmitRuntimeInputContext & {
      routeMode: RuntimeInputMode;
    }) => {
      if (adapter.routeRuntimeInput === undefined) {
        throw new Error("Runtime input router is unavailable.");
      }

      const request = buildRuntimeInputRouteRequest({
        content,
        mode: routeMode,
        sessionId,
        snapshot: getSnapshot()?.snapshot ?? null,
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
      if (routeResult.commandResponse !== null && routeResult.commandResponse !== undefined) {
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

  function submitInput({
    content,
    mode,
    sessionId,
    target,
    taskNodeId,
  }: SubmitRuntimeInputContext) {
    setInputCommandError(null);
    setUiNotice(null);
    if (adapter.routeRuntimeInput !== undefined) {
      const routeMode = runtimeInputModeFor(content, mode);
      setActiveRuntimeInputMode(routeMode);
      runtimeInputMutation.mutate({
        content,
        mode,
        routeMode,
        sessionId,
        target,
        taskNodeId,
      });
      return;
    }

    inputMutation.mutate({
      content,
      mode,
      sessionId,
      target,
      taskNodeId,
    });
  }

  return {
    isInputSubmitting: inputMutation.isPending || runtimeInputMutation.isPending,
    resetInputCommands: () => {
      inputMutation.reset();
      runtimeInputMutation.reset();
    },
    submitInput,
  };
}
