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
  MainPageSelectionTarget,
} from "./mainPageUiTypes";
import type {
  MainPageAdapter,
  MainPageRuntimeSnapshot,
} from "./runtime/adapter";
import { useMainPageInputCommandMutation } from "./useMainPageInputCommandMutation";
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

export type { InputSubmitContext } from "./useMainPageInputCommandMutation";
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

  const inputMutation = useMainPageInputCommandMutation({
    activeWorkspaceId,
    adapter,
    refetchSnapshot,
    setInputCommandError,
    setInputDraft,
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
