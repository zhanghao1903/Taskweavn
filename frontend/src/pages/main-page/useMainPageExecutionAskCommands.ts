import { useMutation } from "@tanstack/react-query";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type { AskId, WorkspaceId } from "../../shared/api/types";
import { handleCommandResponse } from "./runtime/commandRefresh";
import type { MainPageAdapter } from "./runtime/adapter";

type SnapshotRefetchResult = {
  status: string;
};

type SetExecutionAskCommandError = (
  message: string | null,
  recoveryActions?: ProductRecoveryAction[],
) => void;

export type AnswerExecutionAskContext = {
  askId: AskId;
  selectedOptionIds: string[];
  sessionId: string;
  text?: string | null;
};

export type DeferExecutionAskContext = {
  askId: AskId;
  reason?: string | null;
  sessionId: string;
};

export type CancelExecutionAskContext = {
  askId: AskId;
  reason: string;
  sessionId: string;
};

export type UseMainPageExecutionAskCommandsOptions = {
  activeWorkspaceId: WorkspaceId | null;
  adapter: MainPageAdapter;
  refetchSnapshot: () => Promise<SnapshotRefetchResult>;
  setExecutionAskCommandError: SetExecutionAskCommandError;
  setUiNotice: (notice: string | null) => void;
};

export function useMainPageExecutionAskCommands({
  activeWorkspaceId,
  adapter,
  refetchSnapshot,
  setExecutionAskCommandError,
  setUiNotice,
}: UseMainPageExecutionAskCommandsOptions) {
  const answerAskMutation = useMutation({
    mutationFn: async ({
      askId,
      selectedOptionIds,
      sessionId,
      text,
    }: AnswerExecutionAskContext) =>
      adapter.answerAsk(sessionId, askId, {
        commandId: `answer-ask-${askId}-${Date.now()}`,
        sessionId,
        payload: {
          selectedOptionIds,
          text: text ?? null,
        },
      }, activeWorkspaceId),
    onError: () => {
      setExecutionAskCommandError("Answer submission failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Answer submission was rejected.",
      );

      if (result.errorMessage) {
        setExecutionAskCommandError(
          result.errorMessage,
          result.recoveryActions,
        );
        if (result.shouldRefetch) {
          void refetchSnapshot();
        }
        return;
      }

      setExecutionAskCommandError(null);
      setUiNotice("Answer submitted.");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  const deferAskMutation = useMutation({
    mutationFn: async ({ askId, reason, sessionId }: DeferExecutionAskContext) =>
      adapter.deferAsk(sessionId, askId, {
        commandId: `defer-ask-${askId}-${Date.now()}`,
        sessionId,
        payload: {
          reason: reason ?? null,
        },
      }, activeWorkspaceId),
    onError: () => {
      setExecutionAskCommandError("Defer failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Defer was rejected.",
      );

      if (result.errorMessage) {
        setExecutionAskCommandError(
          result.errorMessage,
          result.recoveryActions,
        );
        return;
      }

      setExecutionAskCommandError(null);
      setUiNotice("Question deferred.");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  const cancelAskMutation = useMutation({
    mutationFn: async ({ askId, reason, sessionId }: CancelExecutionAskContext) =>
      adapter.cancelAsk(sessionId, askId, {
        commandId: `cancel-ask-${askId}-${Date.now()}`,
        sessionId,
        payload: {
          reason,
        },
      }, activeWorkspaceId),
    onError: () => {
      setExecutionAskCommandError("Cancel failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Cancel was rejected.",
      );

      if (result.errorMessage) {
        setExecutionAskCommandError(
          result.errorMessage,
          result.recoveryActions,
        );
        return;
      }

      setExecutionAskCommandError(null);
      setUiNotice("Question cancelled.");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  return {
    answerAskMutation,
    cancelAskMutation,
    deferAskMutation,
  };
}
