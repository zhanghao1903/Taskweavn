import { useMutation } from "@tanstack/react-query";

import type {
  AnswerAuthoringAskItemPayload,
  ProductRecoveryAction,
} from "../../shared/api/platoApi";
import type {
  AskId,
  ConfirmationActionView,
  WorkspaceId,
} from "../../shared/api/types";
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

export type ConfirmationDecisionContext = {
  confirmation: ConfirmationActionView | undefined;
  decision: string;
  sessionId: string;
};

export type AnswerAuthoringAskBatchContext = {
  answers: AnswerAuthoringAskItemPayload[];
  rawTaskId: string;
  sessionId: string;
};

export type RepairAuthoringStateContext = {
  sessionId: string;
};

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

export type UseMainPageInteractionCommandMutationsOptions = {
  activeWorkspaceId: WorkspaceId | null;
  adapter: MainPageAdapter;
  refetchSnapshot: () => Promise<SnapshotRefetchResult>;
  setAuthoringAskCommandError: CommandErrorSetter;
  setConfirmationCommandError: CommandErrorSetter;
  setExecutionAskCommandError: CommandErrorSetter;
  setTaskTreeCommandError: (message: string | null) => void;
  setUiNotice: (notice: string | null) => void;
};

export function useMainPageInteractionCommandMutations({
  activeWorkspaceId,
  adapter,
  refetchSnapshot,
  setAuthoringAskCommandError,
  setConfirmationCommandError,
  setExecutionAskCommandError,
  setTaskTreeCommandError,
  setUiNotice,
}: UseMainPageInteractionCommandMutationsOptions) {
  const resolveConfirmationMutation = useMutation({
    mutationFn: async ({
      confirmation,
      decision,
      sessionId,
    }: {
      confirmation: ConfirmationActionView;
      decision: string;
      sessionId: string;
    }) =>
      adapter.resolveConfirmation(
        sessionId,
        confirmation.id,
        {
          commandId: `resolve-${confirmation.id}-${decision}`,
          sessionId,
          payload: {
            value: decision,
          },
        },
        activeWorkspaceId,
      ),
    onError: () => {
      setConfirmationCommandError("Confirmation failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Confirmation was rejected.",
      );

      if (result.errorMessage) {
        setConfirmationCommandError(
          result.errorMessage,
          result.recoveryActions,
        );
        return;
      }

      setConfirmationCommandError(null);
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  const answerAuthoringAskBatchMutation = useMutation({
    mutationFn: async ({
      answers,
      rawTaskId,
      sessionId,
    }: AnswerAuthoringAskBatchContext) =>
      adapter.answerAuthoringAskBatch(
        sessionId,
        rawTaskId,
        {
          commandId: `answer-authoring-asks-${rawTaskId}-${Date.now()}`,
          sessionId,
          payload: {
            answers,
          },
        },
        activeWorkspaceId,
      ),
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
      adapter.repairAuthoringState(
        {
          commandId: `repair-authoring-state-${Date.now()}`,
          sessionId,
          payload: {
            reason: "dirty_authoring_state",
          },
        },
        activeWorkspaceId,
      ),
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

  const answerAskMutation = useMutation({
    mutationFn: async ({
      askId,
      selectedOptionIds,
      sessionId,
      text,
    }: AnswerExecutionAskContext) =>
      adapter.answerAsk(
        sessionId,
        askId,
        {
          commandId: `answer-ask-${askId}-${Date.now()}`,
          sessionId,
          payload: {
            selectedOptionIds,
            text: text ?? null,
          },
        },
        activeWorkspaceId,
      ),
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
      adapter.deferAsk(
        sessionId,
        askId,
        {
          commandId: `defer-ask-${askId}-${Date.now()}`,
          sessionId,
          payload: {
            reason: reason ?? null,
          },
        },
        activeWorkspaceId,
      ),
    onError: () => {
      setExecutionAskCommandError("Defer failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(response, "Defer was rejected.");

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
      adapter.cancelAsk(
        sessionId,
        askId,
        {
          commandId: `cancel-ask-${askId}-${Date.now()}`,
          sessionId,
          payload: {
            reason,
          },
        },
        activeWorkspaceId,
      ),
    onError: () => {
      setExecutionAskCommandError("Cancel failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(response, "Cancel was rejected.");

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
    answerAuthoringAskBatchMutation,
    cancelAskMutation,
    deferAskMutation,
    repairAuthoringStateMutation,
    resolveConfirmationMutation,
  };
}
