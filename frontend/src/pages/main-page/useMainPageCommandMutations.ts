import { useMutation } from "@tanstack/react-query";
import type { Dispatch, SetStateAction } from "react";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type {
  RuntimeInputMode,
  SessionActivityItemView,
  TaskNodeId,
  WorkspaceId,
} from "../../shared/api/types";
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
import { useMainPagePlanCommandMutations } from "./useMainPagePlanCommandMutations";
import { useMainPageRuntimeInputMutation } from "./useMainPageRuntimeInputMutation";
import { useMainPageTaskCommandMutations } from "./useMainPageTaskCommandMutations";

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

export type {
  AnswerAuthoringAskBatchContext,
  AnswerExecutionAskContext,
  CancelExecutionAskContext,
  ConfirmationDecisionContext,
  DeferExecutionAskContext,
  RepairAuthoringStateContext,
} from "./useMainPageInteractionCommandMutations";
export type {
  ArchivePlanContext,
  PublishTaskTreeContext,
} from "./useMainPagePlanCommandMutations";
export type {
  RetryTaskContext,
  StopTaskContext,
} from "./useMainPageTaskCommandMutations";

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

  const {
    archivePlanMutation,
    publishTaskTreeMutation,
  } = useMainPagePlanCommandMutations({
    activeWorkspaceId,
    adapter,
    refetchSnapshot,
    setDetailOverride,
    setSelectedTaskNodeId,
    setSelectionTarget,
    setTaskTreeCommandFailure,
    setUiNotice,
  });

  const {
    retryTaskMutation,
    stopTaskMutation,
  } = useMainPageTaskCommandMutations({
    activeWorkspaceId,
    adapter,
    refetchSnapshot,
    setTaskTreeCommandFailure,
    setUiNotice,
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
