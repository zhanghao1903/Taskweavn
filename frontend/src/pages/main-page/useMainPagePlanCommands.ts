import { useMutation } from "@tanstack/react-query";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type { WorkspaceId } from "../../shared/api/types";
import { handleCommandResponse } from "./runtime/commandRefresh";
import type { MainPageAdapter } from "./runtime/adapter";

type SnapshotRefetch = () => Promise<unknown>;

type SetTaskTreeCommandFailure = (
  message: string | null,
  recoveryActions?: ProductRecoveryAction[],
) => void;

export type PublishTaskTreeContext = {
  sessionId: string;
  taskTreeId: string | null;
};

export type ArchivePlanContext = {
  expectedVersion?: number | null;
  planId: string;
  sessionId: string;
};

export type UseMainPagePlanCommandsOptions = {
  activeWorkspaceId: WorkspaceId | null;
  adapter: MainPageAdapter;
  onArchivePlanSucceeded: () => void;
  refetchSnapshot: SnapshotRefetch;
  setTaskTreeCommandFailure: SetTaskTreeCommandFailure;
  setUiNotice: (notice: string | null) => void;
};

export function useMainPagePlanCommands({
  activeWorkspaceId,
  adapter,
  onArchivePlanSucceeded,
  refetchSnapshot,
  setTaskTreeCommandFailure,
  setUiNotice,
}: UseMainPagePlanCommandsOptions) {
  const publishTaskTreeMutation = useMutation({
    mutationFn: async ({
      sessionId,
      taskTreeId,
    }: {
      sessionId: string;
      taskTreeId: string;
    }) =>
      adapter.publishTaskTree({
        commandId: `publish-task-tree-${Date.now()}`,
        sessionId,
        payload: {
          taskTreeId,
          startImmediately: true,
        },
      }, activeWorkspaceId),
    onError: () => {
      setTaskTreeCommandFailure("Publish failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Publish was rejected.",
      );

      if (result.errorMessage) {
        setTaskTreeCommandFailure(
          result.errorMessage,
          result.recoveryActions,
        );
        return;
      }

      setTaskTreeCommandFailure(null);
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  const archivePlanMutation = useMutation({
    mutationFn: async ({
      expectedVersion,
      planId,
      sessionId,
    }: ArchivePlanContext) =>
      adapter.archivePlan(
        sessionId,
        planId,
        {
          commandId: `archive-plan-${planId}-${Date.now()}`,
          expectedVersion,
          sessionId,
          payload: {
            reason: "user requested archive",
          },
        },
        activeWorkspaceId,
      ),
    onError: () => {
      setTaskTreeCommandFailure("Archive plan failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Archive plan was rejected.",
      );

      if (result.errorMessage) {
        setTaskTreeCommandFailure(
          result.errorMessage,
          result.recoveryActions,
        );
        return;
      }

      onArchivePlanSucceeded();
      setTaskTreeCommandFailure(null);
      setUiNotice("Plan archived.");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  return {
    archivePlanMutation,
    publishTaskTreeMutation,
  };
}
