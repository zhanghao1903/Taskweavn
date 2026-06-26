import { useEffect, useState } from "react";

import type {
  ProductRecoveryAction,
  WorkspaceCatalogResult,
} from "../../shared/api/platoApi";
import type {
  RuntimeInputMode,
  SessionActivityItemView,
  SessionSummary,
  TaskNodeId,
  WorkspaceId,
} from "../../shared/api/types";
import type {
  DetailOverride,
  EventConnectionStatus,
  MainPageSelectionTarget,
} from "./mainPageUiTypes";
import type { MainPageStateId } from "./mockPlatoApi";
import type {
  MainPageAdapter,
  MainPageRuntimeSnapshot,
} from "./runtime/adapter";
import { useMainPageCommandErrorState } from "./useMainPageCommandErrorState";
import { useMainPageInputRuntimeState } from "./useMainPageInputRuntimeState";
import { useMainPageSessionIdentityState } from "./useMainPageSessionIdentityState";
import { useMainPageUiNoticeState } from "./useMainPageUiNoticeState";
import { runtimeInputModeFor } from "./mainPageRuntimeInput";
import {
  useMainPageCommandMutations,
  type AnswerAuthoringAskBatchContext,
  type AnswerExecutionAskContext,
  type ArchivePlanContext,
  type CancelExecutionAskContext,
  type ConfirmationDecisionContext,
  type DeferExecutionAskContext,
  type InputSubmitContext,
  type PublishTaskTreeContext,
  type RepairAuthoringStateContext,
  type RetryTaskContext,
  type StopTaskContext,
} from "./useMainPageCommandMutations";
import { useMainPageEventSubscription } from "./useMainPageEventSubscription";
import {
  useMainPageSessionLifecycle,
  type SessionLifecycleDialog,
} from "./useMainPageSessionLifecycle";
import { useMainPageSelectionState } from "./useMainPageSelectionState";
import { useMainPageSnapshotQuery } from "./useMainPageSnapshotQuery";

export type {
  AnswerAuthoringAskBatchContext,
  AnswerExecutionAskContext,
  ArchivePlanContext,
  CancelExecutionAskContext,
  ConfirmationDecisionContext,
  DeferExecutionAskContext,
  InputSubmitContext,
  PublishTaskTreeContext,
  RepairAuthoringStateContext,
  RetryTaskContext,
  StopTaskContext,
} from "./useMainPageCommandMutations";
export type { SessionLifecycleDialog } from "./useMainPageSessionLifecycle";

export type MainPageController = {
  activeSessionId: string | null;
  activeWorkspaceId: WorkspaceId | null;
  authoringAskError: string | null;
  authoringAskRecoveryActions: ProductRecoveryAction[];
  confirmationError: string | null;
  confirmationRecoveryActions: ProductRecoveryAction[];
  detailOverride: DetailOverride;
  eventConnectionStatus: EventConnectionStatus;
  eventError: string | null;
  inputDraft: string;
  inputError: string | null;
  inputRecoveryActions: ProductRecoveryAction[];
  isCreatingSession: boolean;
  isDeletingSession: boolean;
  isAnsweringAuthoringAsk: boolean;
  executionAskError: string | null;
  executionAskRecoveryActions: ProductRecoveryAction[];
  isAnsweringAsk: boolean;
  isCancellingAsk: boolean;
  isDeferringAsk: boolean;
  isInputSubmitting: boolean;
  isPublishingTaskTree: boolean;
  isArchivingPlan: boolean;
  isRepairingAuthoringState: boolean;
  isRenamingSession: boolean;
  isRetryingTask: boolean;
  isStoppingTask: boolean;
  isResolvingConfirmation: boolean;
  activeRuntimeInputMode: RuntimeInputMode | null;
  selectionTarget: MainPageSelectionTarget;
  sessionDialog: SessionLifecycleDialog;
  isSnapshotError: boolean;
  isSnapshotPending: boolean;
  selectedTaskNodeId: TaskNodeId | null;
  snapshotData: MainPageRuntimeSnapshot | undefined;
  snapshotError: unknown;
  stateId: MainPageStateId;
  taskTreeCommandError: string | null;
  taskTreeCommandRecoveryActions: ProductRecoveryAction[];
  uiNotice: string | null;
  runtimeActivityItems: SessionActivityItemView[];
  workspaceCatalog: WorkspaceCatalogResult | null;
  actions: {
    cancelSessionDialog: () => void;
    changeSessionDialogDraft: (draftName: string) => void;
    changeInputDraft: (draft: string) => void;
    changeState: (nextStateId: MainPageStateId) => void;
    createSession: (workspaceId?: WorkspaceId | null) => void;
    deleteSession: (session: SessionSummary) => void;
    answerAuthoringAskBatch: (context: AnswerAuthoringAskBatchContext) => void;
    archivePlan: (context: ArchivePlanContext) => void;
    repairAuthoringState: (context: RepairAuthoringStateContext) => void;
    answerAsk: (context: AnswerExecutionAskContext) => void;
    cancelAsk: (context: CancelExecutionAskContext) => void;
    deferAsk: (context: DeferExecutionAskContext) => void;
    renameSession: (session: SessionSummary) => void;
    resolveConfirmation: (context: ConfirmationDecisionContext) => void;
    retryTask: (context: RetryTaskContext) => void;
    stopTask: (context: StopTaskContext) => void;
    selectSession: (session: SessionSummary, currentSessionId: string) => void;
    selectTaskPlan: () => void;
    selectTask: (nodeId: TaskNodeId) => void;
    showFileChanges: () => void;
    showResult: () => void;
    submitSessionDialog: () => void;
    submitInput: (context: InputSubmitContext) => void;
    publishTaskTree: (context: PublishTaskTreeContext) => void;
  };
};

export type UseMainPageControllerOptions = {
  adapter: MainPageAdapter;
  initialStateId: MainPageStateId;
  initialTaskNodeId?: TaskNodeId | null;
};

export function useMainPageController({
  adapter,
  initialStateId,
  initialTaskNodeId = null,
}: UseMainPageControllerOptions): MainPageController {
  const [stateId, setStateId] = useState<MainPageStateId>(initialStateId);
  const { clearUiNotice, setUiNotice, uiNotice } = useMainPageUiNoticeState();
  const {
    authoringAskError,
    authoringAskRecoveryActions,
    confirmationError,
    confirmationRecoveryActions,
    executionAskError,
    executionAskRecoveryActions,
    inputError,
    inputRecoveryActions,
    resetCommandErrorState,
    setAuthoringAskCommandError,
    setConfirmationCommandError,
    setExecutionAskCommandError,
    setInputCommandError,
    setTaskTreeCommandError,
    setTaskTreeCommandFailure,
    taskTreeCommandError,
    taskTreeCommandRecoveryActions,
  } = useMainPageCommandErrorState();
  const {
    actions: selectionActions,
    detailOverride,
    resetSelection,
    selectedTaskNodeId,
    selectionTarget,
    setDetailOverride,
    setSelectedTaskNodeId,
    setSelectionTarget,
  } = useMainPageSelectionState(clearUiNotice);
  const {
    activeSessionId,
    activeWorkspaceId,
    adoptSessionId,
    adoptWorkspaceId,
    selectSession,
    setActiveSessionId,
    setActiveWorkspaceId,
  } = useMainPageSessionIdentityState({
    initialSessionId: adapter.sessionId,
    initialWorkspaceId: adapter.workspaceId ?? null,
    setUiNotice,
  });
  const {
    activeRuntimeInputMode,
    changeInputDraft,
    inputDraft,
    resetInputDraft,
    runtimeActivityItems,
    setActiveRuntimeInputMode,
    setRuntimeActivityItems,
  } = useMainPageInputRuntimeState({
    activeSessionId,
    activeWorkspaceId,
  });
  const {
    initialTaskNodeIdRef,
    isSnapshotError,
    isSnapshotPending,
    refetchSnapshot,
    refetchWorkspaceCatalog,
    snapshotData,
    snapshotDataRef,
    snapshotError,
    snapshotIdentity,
    workspaceCatalog,
  } = useMainPageSnapshotQuery({
    activeSessionId,
    activeWorkspaceId,
    adapter,
    initialTaskNodeId,
    stateId,
  });
  const {
    clearEventError,
    eventConnectionStatus,
    eventError,
  } = useMainPageEventSubscription({
    activeWorkspaceId,
    adapter,
    refetchSnapshot,
    resetKey: snapshotIdentity,
    snapshotData,
  });

  useEffect(() => {
    if (!snapshotData) {
      return;
    }
    adoptSessionId(snapshotData.snapshot.session.id);
  }, [adoptSessionId, snapshotData]);

  useEffect(() => {
    if (workspaceCatalog === null) {
      return;
    }
    adoptWorkspaceId(workspaceCatalog.currentWorkspaceId);
  }, [adoptWorkspaceId, workspaceCatalog]);

  const {
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
  } = useMainPageCommandMutations({
    activeWorkspaceId,
    adapter,
    getSnapshotData: () => snapshotDataRef.current,
    refetchSnapshot,
    setActiveRuntimeInputMode,
    setAuthoringAskCommandError,
    setConfirmationCommandError,
    setDetailOverride,
    setExecutionAskCommandError,
    setInputCommandError,
    setInputDraft: changeInputDraft,
    setRuntimeActivityItems,
    setSelectedTaskNodeId,
    setSelectionTarget,
    setTaskTreeCommandError,
    setTaskTreeCommandFailure,
    setUiNotice,
  });
  const sessionLifecycle = useMainPageSessionLifecycle({
    activeWorkspaceId,
    adapter,
    getSnapshotData: () => snapshotDataRef.current,
    refetchSnapshot,
    refetchWorkspaceCatalog,
    setActiveSessionId,
    setActiveWorkspaceId,
    setUiNotice,
  });
  const {
    resetSessionDialog,
    resetSessionLifecycle,
  } = sessionLifecycle;

  useEffect(() => {
    const currentSnapshot = snapshotDataRef.current;

    if (!currentSnapshot) {
      return;
    }

    const routeTaskNodeId = initialTaskNodeIdRef.current;
    const nextSelectedTaskNodeId =
      routeTaskNodeId !== null &&
      currentSnapshot.snapshot.taskTree?.nodes.some(
        (node) => node.id === routeTaskNodeId,
      )
        ? routeTaskNodeId
        : currentSnapshot.metadata.initialSelectedTaskNodeId;
    initialTaskNodeIdRef.current = null;
    resetSelection(nextSelectedTaskNodeId);
    resetInputDraft();
    resetCommandErrorState();
    setUiNotice(null);
    resetSessionDialog();
    clearEventError();
  }, [
    clearEventError,
    resetCommandErrorState,
    resetInputDraft,
    resetSessionDialog,
    resetSelection,
    snapshotIdentity,
  ]);

  function handleStateChange(nextStateId: MainPageStateId) {
    setStateId(nextStateId);
    resetSelection();
    resetInputDraft();
    resetCommandErrorState();
    setUiNotice(null);
    resetSessionLifecycle();
    clearEventError();
    resolveConfirmationMutation.reset();
    answerAuthoringAskBatchMutation.reset();
    repairAuthoringStateMutation.reset();
    answerAskMutation.reset();
    deferAskMutation.reset();
    cancelAskMutation.reset();
    inputMutation.reset();
    publishTaskTreeMutation.reset();
  }

  function handleInputSubmit({
    mode,
    sessionId,
    target,
    taskNodeId,
  }: InputSubmitContext) {
    const content = inputDraft.trim();

    if (!content) {
      return;
    }

    setInputCommandError(null);
    setUiNotice(null);
    if (adapter.routeRuntimeInput !== undefined) {
      const routeMode = runtimeInputModeFor(content, mode);
      setActiveRuntimeInputMode(routeMode);
      runtimeInputMutation.mutate({
        content,
        routeMode,
        sessionId,
        target,
        taskNodeId,
      });
      return;
    }

    inputMutation.mutate({
      content,
      mode,
      sessionId,
      target,
      taskNodeId,
    });
  }

  function handlePublishTaskTree({
    sessionId,
    taskTreeId,
  }: PublishTaskTreeContext) {
    if (taskTreeId === null) {
      setTaskTreeCommandFailure("No draft task plan is available to publish.");
      return;
    }

    setTaskTreeCommandFailure(null);
    setUiNotice(null);
    publishTaskTreeMutation.mutate({
      sessionId,
      taskTreeId,
    });
  }

  function handleArchivePlan(context: ArchivePlanContext) {
    setTaskTreeCommandFailure(null);
    setUiNotice(null);
    archivePlanMutation.mutate(context);
  }

  function handleConfirmationDecision({
    confirmation,
    decision,
    sessionId,
  }: ConfirmationDecisionContext) {
    if (!confirmation) {
      setConfirmationCommandError("No pending confirmation is available.");
      return;
    }

    setConfirmationCommandError(null);
    setUiNotice(null);
    resolveConfirmationMutation.mutate({
      confirmation,
      decision,
      sessionId,
    });
  }

  function handleAnswerAuthoringAskBatch({
    answers,
    rawTaskId,
    sessionId,
  }: AnswerAuthoringAskBatchContext) {
    if (answers.length === 0) {
      setAuthoringAskCommandError("Answer at least one authoring question.");
      return;
    }

    setAuthoringAskCommandError(null);
    setUiNotice(null);
    answerAuthoringAskBatchMutation.mutate({
      answers,
      rawTaskId,
      sessionId,
    });
  }

  function handleRepairAuthoringState({
    sessionId,
  }: RepairAuthoringStateContext) {
    setTaskTreeCommandError(null);
    setUiNotice(null);
    repairAuthoringStateMutation.mutate({
      sessionId,
    });
  }

  function handleAnswerAsk({
    askId,
    selectedOptionIds,
    sessionId,
    text,
  }: AnswerExecutionAskContext) {
    if (selectedOptionIds.length === 0 && !text?.trim()) {
      setExecutionAskCommandError("Answer the question before submitting.");
      return;
    }

    setExecutionAskCommandError(null);
    setUiNotice(null);
    answerAskMutation.mutate({
      askId,
      selectedOptionIds,
      sessionId,
      text,
    });
  }

  function handleDeferAsk({ askId, reason, sessionId }: DeferExecutionAskContext) {
    setExecutionAskCommandError(null);
    setUiNotice(null);
    deferAskMutation.mutate({
      askId,
      reason,
      sessionId,
    });
  }

  function handleCancelAsk({ askId, reason, sessionId }: CancelExecutionAskContext) {
    setExecutionAskCommandError(null);
    setUiNotice(null);
    cancelAskMutation.mutate({
      askId,
      reason,
      sessionId,
    });
  }

  function handleRetryTask({ sessionId, taskNodeId }: RetryTaskContext) {
    setTaskTreeCommandFailure(null);
    setUiNotice(null);
    retryTaskMutation.mutate({
      sessionId,
      taskNodeId,
    });
  }

  function handleStopTask({ sessionId, taskNodeId }: StopTaskContext) {
    setTaskTreeCommandFailure(null);
    setUiNotice(null);
    stopTaskMutation.mutate({
      sessionId,
      taskNodeId,
    });
  }

  return {
    activeSessionId,
    activeWorkspaceId,
    authoringAskError,
    authoringAskRecoveryActions,
    confirmationError,
    confirmationRecoveryActions,
    detailOverride,
    eventConnectionStatus,
    eventError,
    inputDraft,
    inputError,
    inputRecoveryActions,
    isCreatingSession: sessionLifecycle.isCreatingSession,
    isDeletingSession: sessionLifecycle.isDeletingSession,
    isAnsweringAuthoringAsk: answerAuthoringAskBatchMutation.isPending,
    executionAskError,
    executionAskRecoveryActions,
    isAnsweringAsk: answerAskMutation.isPending,
    isCancellingAsk: cancelAskMutation.isPending,
    isDeferringAsk: deferAskMutation.isPending,
    isInputSubmitting: inputMutation.isPending || runtimeInputMutation.isPending,
    isPublishingTaskTree: publishTaskTreeMutation.isPending,
    isArchivingPlan: archivePlanMutation.isPending,
    isRepairingAuthoringState: repairAuthoringStateMutation.isPending,
    isRenamingSession: sessionLifecycle.isRenamingSession,
    isRetryingTask: retryTaskMutation.isPending,
    isStoppingTask: stopTaskMutation.isPending,
    isResolvingConfirmation: resolveConfirmationMutation.isPending,
    activeRuntimeInputMode,
    selectionTarget,
    sessionDialog: sessionLifecycle.sessionDialog,
    isSnapshotError,
    isSnapshotPending,
    selectedTaskNodeId,
    snapshotData,
    snapshotError,
    stateId,
    taskTreeCommandError,
    taskTreeCommandRecoveryActions,
    uiNotice,
    runtimeActivityItems,
    workspaceCatalog,
    actions: {
      answerAuthoringAskBatch: handleAnswerAuthoringAskBatch,
      answerAsk: handleAnswerAsk,
      archivePlan: handleArchivePlan,
      cancelSessionDialog: sessionLifecycle.actions.cancelSessionDialog,
      cancelAsk: handleCancelAsk,
      changeSessionDialogDraft:
        sessionLifecycle.actions.changeSessionDialogDraft,
      changeInputDraft,
      changeState: handleStateChange,
      createSession: sessionLifecycle.actions.createSession,
      deleteSession: sessionLifecycle.actions.deleteSession,
      repairAuthoringState: handleRepairAuthoringState,
      deferAsk: handleDeferAsk,
      renameSession: sessionLifecycle.actions.renameSession,
      resolveConfirmation: handleConfirmationDecision,
      retryTask: handleRetryTask,
      stopTask: handleStopTask,
      selectSession,
      selectTaskPlan: selectionActions.selectTaskPlan,
      selectTask: selectionActions.selectTask,
      showFileChanges: selectionActions.showFileChanges,
      showResult: selectionActions.showResult,
      submitSessionDialog: sessionLifecycle.actions.submitSessionDialog,
      submitInput: handleInputSubmit,
      publishTaskTree: handlePublishTaskTree,
    },
  };
}
