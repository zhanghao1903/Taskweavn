import { useMutation } from "@tanstack/react-query";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type {
  ConfirmationActionView,
  WorkspaceId,
} from "../../shared/api/types";
import { handleCommandResponse } from "./runtime/commandRefresh";
import type { MainPageAdapter } from "./runtime/adapter";

type SnapshotRefetchResult = {
  status: string;
};

type SetConfirmationCommandError = (
  message: string | null,
  recoveryActions?: ProductRecoveryAction[],
) => void;

export type ConfirmationDecisionContext = {
  confirmation: ConfirmationActionView | undefined;
  decision: string;
  sessionId: string;
};

export type UseMainPageConfirmationCommandsOptions = {
  activeWorkspaceId: WorkspaceId | null;
  adapter: MainPageAdapter;
  refetchSnapshot: () => Promise<SnapshotRefetchResult>;
  setConfirmationCommandError: SetConfirmationCommandError;
};

export function useMainPageConfirmationCommands({
  activeWorkspaceId,
  adapter,
  refetchSnapshot,
  setConfirmationCommandError,
}: UseMainPageConfirmationCommandsOptions) {
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
      adapter.resolveConfirmation(sessionId, confirmation.id, {
        commandId: `resolve-${confirmation.id}-${decision}`,
        sessionId,
        payload: {
          value: decision,
        },
      }, activeWorkspaceId),
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

  return {
    resolveConfirmationMutation,
  };
}
