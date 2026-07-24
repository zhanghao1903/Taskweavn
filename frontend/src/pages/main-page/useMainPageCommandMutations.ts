import type { Dispatch, SetStateAction } from "react";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type {
  RuntimeInputMode,
  RuntimeInputPendingClarification,
  SessionActivityItemView,
  TaskNodeId,
  WorkspaceId,
} from "../../shared/api/types";
import type {
  DetailOverride,
  MainPageSelectionTarget,
} from "./mainPageUiTypes";
import type { ExecutionAskCommandErrorSetter } from "./useMainPageCommandErrorState";
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
  acceptRuntimeInputSubmit: (commandId: string) => void;
  failRuntimeInputSubmit: (context: {
    commandId: string;
    message: string;
    recoveryActions: ProductRecoveryAction[];
  }) => void;
  pendingRuntimeClarification: RuntimeInputPendingClarification | null;
  reconcileRuntimeInputSubmit: (commandId: string) => void;
  rejectRuntimeInputSubmit: (context: {
    commandId: string;
    message: string;
    recoveryActions: ProductRecoveryAction[];
  }) => void;
  setActiveRuntimeInputMode: (mode: RuntimeInputMode | null) => void;
  setAuthoringAskCommandError: CommandErrorSetter;
  setConfirmationCommandError: CommandErrorSetter;
  setDetailOverride: (override: DetailOverride) => void;
  setExecutionAskCommandError: ExecutionAskCommandErrorSetter;
  setInputCommandError: CommandErrorSetter;
  setInputDraft: (draft: string) => void;
  setPendingRuntimeClarification: (
    clarification: RuntimeInputPendingClarification | null,
  ) => void;
  setRuntimeActivityItems: Dispatch<
    SetStateAction<SessionActivityItemView[]>
  >;
  setSelectedTaskNodeId: (taskNodeId: TaskNodeId | null) => void;
  setSelectionTarget: (target: MainPageSelectionTarget) => void;
  setTaskTreeCommandError: (message: string | null) => void;
  setTaskTreeCommandFailure: CommandErrorSetter;
  setUiNotice: (notice: string | null) => void;
  startRuntimeInputSubmit: (context: {
    body: string;
    commandId: string;
    createdAt: string;
    scope: {
      scopeKind: "session" | "plan" | "task";
      planId: string | null;
      taskNodeId: TaskNodeId | null;
    };
    sessionId: string;
    workspaceId: WorkspaceId | null;
  }) => void;
};

export function useMainPageCommandMutations({
  activeWorkspaceId,
  adapter,
  getSnapshotData,
  refetchSnapshot,
  acceptRuntimeInputSubmit,
  failRuntimeInputSubmit,
  pendingRuntimeClarification,
  reconcileRuntimeInputSubmit,
  rejectRuntimeInputSubmit,
  setActiveRuntimeInputMode,
  setAuthoringAskCommandError,
  setConfirmationCommandError,
  setDetailOverride,
  setExecutionAskCommandError,
  setInputCommandError,
  setInputDraft,
  setPendingRuntimeClarification,
  setRuntimeActivityItems,
  setSelectedTaskNodeId,
  setSelectionTarget,
  setTaskTreeCommandError,
  setTaskTreeCommandFailure,
  setUiNotice,
  startRuntimeInputSubmit,
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
    acceptRuntimeInputSubmit,
    failRuntimeInputSubmit,
    pendingRuntimeClarification,
    reconcileRuntimeInputSubmit,
    rejectRuntimeInputSubmit,
    setActiveRuntimeInputMode,
    setInputCommandError,
    setInputDraft,
    setPendingRuntimeClarification,
    setRuntimeActivityItems,
    setUiNotice,
    startRuntimeInputSubmit,
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

export type MainPageCommandMutations = ReturnType<
  typeof useMainPageCommandMutations
>;
