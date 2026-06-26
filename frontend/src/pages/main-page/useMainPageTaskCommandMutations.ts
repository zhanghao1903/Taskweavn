import { useMutation } from "@tanstack/react-query";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type { TaskNodeId, WorkspaceId } from "../../shared/api/types";
import {
  summarizeCommandResponse,
  summarizeMainPageSnapshot,
} from "../../shared/api/traceSummary";
import {
  createFrontendLogger,
  toLoggableError,
} from "../../shared/logging/frontendLogger";
import { handleCommandResponse } from "./runtime/commandRefresh";
import type {
  MainPageAdapter,
  MainPageRuntimeSnapshot,
} from "./runtime/adapter";

const mainPageTaskCommandLogger = createFrontendLogger("main-page");

type SnapshotRefetchResult = {
  data?: MainPageRuntimeSnapshot;
  status: string;
};

type CommandErrorSetter = (
  message: string | null,
  recoveryActions?: ProductRecoveryAction[],
) => void;

export type RetryTaskContext = {
  sessionId: string;
  taskNodeId: TaskNodeId;
};

export type StopTaskContext = {
  sessionId: string;
  taskNodeId: TaskNodeId;
};

export type UseMainPageTaskCommandMutationsOptions = {
  activeWorkspaceId: WorkspaceId | null;
  adapter: MainPageAdapter;
  refetchSnapshot: () => Promise<SnapshotRefetchResult>;
  setTaskTreeCommandFailure: CommandErrorSetter;
  setUiNotice: (notice: string | null) => void;
};

export function useMainPageTaskCommandMutations({
  activeWorkspaceId,
  adapter,
  refetchSnapshot,
  setTaskTreeCommandFailure,
  setUiNotice,
}: UseMainPageTaskCommandMutationsOptions) {
  const retryTaskMutation = useMutation({
    mutationFn: async ({ sessionId, taskNodeId }: RetryTaskContext) =>
      adapter.retryTask(
        sessionId,
        taskNodeId,
        {
          commandId: `retry-task-${taskNodeId}-${Date.now()}`,
          sessionId,
          payload: {
            startImmediately: true,
          },
        },
        activeWorkspaceId,
      ),
    onError: () => {
      setTaskTreeCommandFailure("Retry failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(response, "Retry was rejected.");

      if (result.errorMessage) {
        setTaskTreeCommandFailure(
          result.errorMessage,
          result.recoveryActions,
        );
        return;
      }

      setTaskTreeCommandFailure(null);
      setUiNotice("Retry queued.");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  const stopTaskMutation = useMutation({
    mutationFn: async ({ sessionId, taskNodeId }: StopTaskContext) => {
      const commandId = `stop-task-${taskNodeId}-${Date.now()}`;
      mainPageTaskCommandLogger.info("command.stop.submit", {
        commandId,
        sessionId,
        taskNodeId,
      });
      return adapter.stopTask(
        sessionId,
        taskNodeId,
        {
          commandId,
          sessionId,
          payload: {
            reason: "user requested stop",
          },
        },
        activeWorkspaceId,
      );
    },
    onError: (error) => {
      mainPageTaskCommandLogger.error("command.stop.failed", {
        error: toLoggableError(error),
      });
      setTaskTreeCommandFailure("Stop failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(response, "Stop was rejected.");
      mainPageTaskCommandLogger.info("command.stop.result", {
        ...summarizeCommandResponse(response),
        shouldRefetch: result.shouldRefetch,
      });

      if (result.errorMessage) {
        setTaskTreeCommandFailure(
          result.errorMessage,
          result.recoveryActions,
        );
        return;
      }

      setTaskTreeCommandFailure(null);
      setUiNotice("Stop requested.");
      if (result.shouldRefetch) {
        mainPageTaskCommandLogger.info("snapshot.refetch.request", {
          reason: "stop_command_refresh",
        });
        void refetchSnapshot()
          .then((queryResult) => {
            mainPageTaskCommandLogger.info("snapshot.refetch.result", {
              hasData: queryResult.data !== undefined,
              reason: "stop_command_refresh",
              snapshot:
                queryResult.data === undefined
                  ? null
                  : summarizeMainPageSnapshot(queryResult.data.snapshot),
              status: queryResult.status,
            });
          })
          .catch((error) => {
            mainPageTaskCommandLogger.error("snapshot.refetch.failed", {
              error: toLoggableError(error),
              reason: "stop_command_refresh",
            });
          });
      }
    },
  });

  return {
    retryTaskMutation,
    stopTaskMutation,
  };
}
