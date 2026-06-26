import { useMutation } from "@tanstack/react-query";
import type { Dispatch, SetStateAction } from "react";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type {
  RuntimeInputMode,
  SessionActivityItemView,
  TaskNodeId,
  WorkspaceId,
} from "../../shared/api/types";
import {
  summarizeCommandResponse,
  summarizeMainPageSnapshot,
} from "../../shared/api/traceSummary";
import {
  createFrontendLogger,
  toLoggableError,
} from "../../shared/logging/frontendLogger";
import type {
  DetailOverride,
  InputTarget,
  MainPageSelectionTarget,
} from "./mainPageUiTypes";
import type { MainPageInputCommandMode } from "./mainPageViewModel";
import { handleCommandResponse } from "./runtime/commandRefresh";
import type {
  MainPageAdapter,
  MainPageRuntimeSnapshot,
} from "./runtime/adapter";
import { useMainPageInteractionCommandMutations } from "./useMainPageInteractionCommandMutations";
import { useMainPageRuntimeInputMutation } from "./useMainPageRuntimeInputMutation";

const mainPageCommandLogger = createFrontendLogger("main-page");

type SnapshotRefetchResult = {
  data?: MainPageRuntimeSnapshot;
  status: string;
};

type CommandErrorSetter = (
  message: string | null,
  recoveryActions?: ProductRecoveryAction[],
) => void;

export type InputSubmitContext = {
  mode: MainPageInputCommandMode;
  sessionId: string;
  target: InputTarget;
  taskNodeId: TaskNodeId | null;
};

export type PublishTaskTreeContext = {
  sessionId: string;
  taskTreeId: string | null;
};

export type ArchivePlanContext = {
  expectedVersion?: number | null;
  planId: string;
  sessionId: string;
};

export type RetryTaskContext = {
  sessionId: string;
  taskNodeId: TaskNodeId;
};

export type StopTaskContext = {
  sessionId: string;
  taskNodeId: TaskNodeId;
};

export type {
  AnswerAuthoringAskBatchContext,
  AnswerExecutionAskContext,
  CancelExecutionAskContext,
  ConfirmationDecisionContext,
  DeferExecutionAskContext,
  RepairAuthoringStateContext,
} from "./useMainPageInteractionCommandMutations";

export type UseMainPageCommandMutationsOptions = {
  activeWorkspaceId: WorkspaceId | null;
  adapter: MainPageAdapter;
  getSnapshotData: () => MainPageRuntimeSnapshot | undefined;
  refetchSnapshot: () => Promise<SnapshotRefetchResult>;
  setActiveRuntimeInputMode: (mode: RuntimeInputMode | null) => void;
  setAuthoringAskCommandError: CommandErrorSetter;
  setConfirmationCommandError: CommandErrorSetter;
  setDetailOverride: (override: DetailOverride) => void;
  setExecutionAskCommandError: CommandErrorSetter;
  setInputCommandError: CommandErrorSetter;
  setInputDraft: (draft: string) => void;
  setRuntimeActivityItems: Dispatch<
    SetStateAction<SessionActivityItemView[]>
  >;
  setSelectedTaskNodeId: (taskNodeId: TaskNodeId | null) => void;
  setSelectionTarget: (target: MainPageSelectionTarget) => void;
  setTaskTreeCommandError: (message: string | null) => void;
  setTaskTreeCommandFailure: CommandErrorSetter;
  setUiNotice: (notice: string | null) => void;
};

export function useMainPageCommandMutations({
  activeWorkspaceId,
  adapter,
  getSnapshotData,
  refetchSnapshot,
  setActiveRuntimeInputMode,
  setAuthoringAskCommandError,
  setConfirmationCommandError,
  setDetailOverride,
  setExecutionAskCommandError,
  setInputCommandError,
  setInputDraft,
  setRuntimeActivityItems,
  setSelectedTaskNodeId,
  setSelectionTarget,
  setTaskTreeCommandError,
  setTaskTreeCommandFailure,
  setUiNotice,
}: UseMainPageCommandMutationsOptions) {
  const {
    answerAskMutation,
    answerAuthoringAskBatchMutation,
    cancelAskMutation,
    deferAskMutation,
    repairAuthoringStateMutation,
    resolveConfirmationMutation,
  } = useMainPageInteractionCommandMutations({
    activeWorkspaceId,
    adapter,
    refetchSnapshot,
    setAuthoringAskCommandError,
    setConfirmationCommandError,
    setExecutionAskCommandError,
    setTaskTreeCommandError,
    setUiNotice,
  });

  const inputMutation = useMutation({
    mutationFn: async ({
      content,
      mode,
      sessionId,
      target,
      taskNodeId,
    }: {
      content: string;
      mode: MainPageInputCommandMode;
      sessionId: string;
      target: InputTarget;
      taskNodeId: TaskNodeId | null;
    }) => {
      const commandId = `append-${target}-${Date.now()}`;

      if (mode === "append_task_input" && taskNodeId) {
        return adapter.appendTaskInput(
          sessionId,
          taskNodeId,
          {
            commandId,
            sessionId,
            payload: {
              content,
              mode: "guidance",
            },
          },
          activeWorkspaceId,
        );
      }

      if (mode === "generate_task_tree") {
        return adapter.generateTaskTree(
          {
            commandId: `generate-task-tree-${Date.now()}`,
            sessionId,
            payload: {
              prompt: content,
            },
          },
          activeWorkspaceId,
        );
      }

      return adapter.appendSessionInput(
        {
          commandId,
          sessionId,
          payload: {
            content,
            mode: "global_guidance",
          },
        },
        activeWorkspaceId,
      );
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

  const runtimeInputMutation = useMainPageRuntimeInputMutation({
    activeWorkspaceId,
    adapter,
    getSnapshotData,
    refetchSnapshot,
    setActiveRuntimeInputMode,
    setInputCommandError,
    setInputDraft,
    setRuntimeActivityItems,
    setUiNotice,
  });

  const publishTaskTreeMutation = useMutation({
    mutationFn: async ({
      sessionId,
      taskTreeId,
    }: {
      sessionId: string;
      taskTreeId: string;
    }) =>
      adapter.publishTaskTree(
        {
          commandId: `publish-task-tree-${Date.now()}`,
          sessionId,
          payload: {
            taskTreeId,
            startImmediately: true,
          },
        },
        activeWorkspaceId,
      ),
    onError: () => {
      setTaskTreeCommandFailure("Publish failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(response, "Publish was rejected.");

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

      setSelectedTaskNodeId(null);
      setSelectionTarget("auto");
      setDetailOverride("auto");
      setTaskTreeCommandFailure(null);
      setUiNotice("Plan archived.");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  const retryTaskMutation = useMutation({
    mutationFn: async ({
      sessionId,
      taskNodeId,
    }: {
      sessionId: string;
      taskNodeId: TaskNodeId;
    }) =>
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
    mutationFn: async ({
      sessionId,
      taskNodeId,
    }: {
      sessionId: string;
      taskNodeId: TaskNodeId;
    }) => {
      const commandId = `stop-task-${taskNodeId}-${Date.now()}`;
      mainPageCommandLogger.info("command.stop.submit", {
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
      mainPageCommandLogger.error("command.stop.failed", {
        error: toLoggableError(error),
      });
      setTaskTreeCommandFailure("Stop failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(response, "Stop was rejected.");
      mainPageCommandLogger.info("command.stop.result", {
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
        mainPageCommandLogger.info("snapshot.refetch.request", {
          reason: "stop_command_refresh",
        });
        void refetchSnapshot()
          .then((queryResult) => {
            mainPageCommandLogger.info("snapshot.refetch.result", {
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
            mainPageCommandLogger.error("snapshot.refetch.failed", {
              error: toLoggableError(error),
              reason: "stop_command_refresh",
            });
          });
      }
    },
  });

  return {
    answerAskMutation,
    answerAuthoringAskBatchMutation,
    archivePlanMutation,
    cancelAskMutation,
    deferAskMutation,
    inputMutation,
    publishTaskTreeMutation,
    repairAuthoringStateMutation,
    resolveConfirmationMutation,
    retryTaskMutation,
    runtimeInputMutation,
    stopTaskMutation,
  };
}
