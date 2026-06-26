import { useMutation } from "@tanstack/react-query";

import type {
  AnswerAuthoringAskItemPayload,
  ProductRecoveryAction,
} from "../../shared/api/platoApi";
import type { WorkspaceId } from "../../shared/api/types";
import { handleCommandResponse } from "./runtime/commandRefresh";
import type { MainPageAdapter } from "./runtime/adapter";

type SnapshotRefetch = () => Promise<unknown>;

type SetAuthoringAskCommandError = (
  message: string | null,
  recoveryActions?: ProductRecoveryAction[],
) => void;

export type AnswerAuthoringAskBatchContext = {
  answers: AnswerAuthoringAskItemPayload[];
  rawTaskId: string;
  sessionId: string;
};

export type RepairAuthoringStateContext = {
  sessionId: string;
};

export type UseMainPageAuthoringCommandsOptions = {
  activeWorkspaceId: WorkspaceId | null;
  adapter: MainPageAdapter;
  refetchSnapshot: SnapshotRefetch;
  setAuthoringAskCommandError: SetAuthoringAskCommandError;
  setTaskTreeCommandError: (message: string | null) => void;
  setUiNotice: (notice: string | null) => void;
};

export function useMainPageAuthoringCommands({
  activeWorkspaceId,
  adapter,
  refetchSnapshot,
  setAuthoringAskCommandError,
  setTaskTreeCommandError,
  setUiNotice,
}: UseMainPageAuthoringCommandsOptions) {
  const answerAuthoringAskBatchMutation = useMutation({
    mutationFn: async ({
      answers,
      rawTaskId,
      sessionId,
    }: AnswerAuthoringAskBatchContext) =>
      adapter.answerAuthoringAskBatch(sessionId, rawTaskId, {
        commandId: `answer-authoring-asks-${rawTaskId}-${Date.now()}`,
        sessionId,
        payload: {
          answers,
        },
      }, activeWorkspaceId),
    onError: () => {
      setAuthoringAskCommandError("Answer submission failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Answer submission was rejected.",
      );

      if (result.errorMessage) {
        setAuthoringAskCommandError(
          result.errorMessage,
          result.recoveryActions,
        );
        return;
      }

      setAuthoringAskCommandError(null);
      setUiNotice("Authoring answers submitted.");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  const repairAuthoringStateMutation = useMutation({
    mutationFn: async ({ sessionId }: RepairAuthoringStateContext) =>
      adapter.repairAuthoringState({
        commandId: `repair-authoring-state-${Date.now()}`,
        sessionId,
        payload: {
          reason: "dirty_authoring_state",
        },
      }, activeWorkspaceId),
    onError: () => {
      setTaskTreeCommandError("Authoring repair failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Authoring repair was rejected.",
      );

      if (result.errorMessage) {
        setTaskTreeCommandError(result.errorMessage);
        return;
      }

      setTaskTreeCommandError(null);
      setUiNotice("Authoring state repaired.");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  return {
    answerAuthoringAskBatchMutation,
    repairAuthoringStateMutation,
  };
}
