import { useCallback, useState } from "react";

import type { RuntimeInputPendingClarification } from "../../shared/api/types";
import type { ExecutionAskConversationCommandState } from "./conversation-ask/conversationAskInteraction";
import type {
  MainPageController,
  UseMainPageControllerOptions,
} from "./mainPageControllerTypes";
import {
  useMainPageCommandActions,
  type MainPageCommandPendingState,
} from "./useMainPageCommandActions";
import {
  useMainPageCommandErrorState,
  type ExecutionAskCommandErrorsById,
} from "./useMainPageCommandErrorState";
import { useMainPageInputRuntimeState } from "./useMainPageInputRuntimeState";
import {
  useMainPageSessionIdentityAdoption,
  useMainPageSessionIdentityState,
} from "./useMainPageSessionIdentityState";
import { useMainPageUiNoticeState } from "./useMainPageUiNoticeState";
import { useMainPageCommandMutations } from "./useMainPageCommandMutations";
import { useMainPageEventSubscription } from "./useMainPageEventSubscription";
import { useMainPageSessionLifecycle } from "./useMainPageSessionLifecycle";
import { useMainPageSelectionState } from "./useMainPageSelectionState";
import { useMainPageSnapshotEffects } from "./useMainPageSnapshotEffects";
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
export type {
  MainPageController,
  UseMainPageControllerOptions,
} from "./mainPageControllerTypes";
export type { SessionLifecycleDialog } from "./useMainPageSessionLifecycle";

export function useMainPageController({
  adapter,
  initialStateId,
  initialTaskNodeId = null,
}: UseMainPageControllerOptions): MainPageController {
  const [stateId, setStateId] = useState(initialStateId);
  const [
    pendingRuntimeClarification,
    setPendingRuntimeClarification,
  ] = useState<RuntimeInputPendingClarification | null>(null);
  const clearPendingRuntimeClarification = useCallback(() => {
    setPendingRuntimeClarification(null);
  }, []);
  const { clearUiNotice, setUiNotice, uiNotice } = useMainPageUiNoticeState();
  const {
    authoringAskError,
    authoringAskRecoveryActions,
    confirmationError,
    confirmationRecoveryActions,
    executionAskErrorsById,
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
    acceptRuntimeInputSubmit,
    activeRuntimeInputMode,
    changeInputDraft,
    failRuntimeInputSubmit,
    hydrateRuntimeInputSnapshot,
    inputDraft,
    reconcileRuntimeInputSubmit,
    rejectRuntimeInputSubmit,
    resetInputDraft,
    runtimeActivityItems,
    setActiveRuntimeInputMode,
    setRuntimeActivityItems,
    startRuntimeInputSubmit,
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
  useMainPageSessionIdentityAdoption({
    adoptSessionId,
    adoptWorkspaceId,
    catalogWorkspaceId: workspaceCatalog?.currentWorkspaceId ?? null,
    snapshotSessionId: snapshotData?.snapshot.session.id ?? null,
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

  const commandMutations = useMainPageCommandMutations({
    activeWorkspaceId,
    adapter,
    getSnapshotData: () => snapshotDataRef.current,
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
    setInputDraft: changeInputDraft,
    setPendingRuntimeClarification,
    setRuntimeActivityItems,
    setSelectedTaskNodeId,
    setSelectionTarget,
    setTaskTreeCommandError,
    setTaskTreeCommandFailure,
    setUiNotice,
    startRuntimeInputSubmit,
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
  const commandActions = useMainPageCommandActions({
    clearEventError,
    clearPendingRuntimeClarification,
    commandMutations,
    inputDraft,
    resetCommandErrorState,
    resetInputDraft,
    resetSelection,
    resetSessionLifecycle,
    routeRuntimeInputAvailable: adapter.routeRuntimeInput !== undefined,
    setActiveRuntimeInputMode,
    setAuthoringAskCommandError,
    setConfirmationCommandError,
    setExecutionAskCommandError,
    setInputCommandError,
    setStateId,
    setTaskTreeCommandError,
    setTaskTreeCommandFailure,
    setUiNotice,
  });

  useMainPageSnapshotEffects({
    activeWorkspaceId,
    clearEventError,
    clearPendingRuntimeClarification,
    hydrateRuntimeInputSnapshot,
    initialTaskNodeIdRef,
    resetCommandErrorState,
    resetInputDraft,
    resetSelection,
    resetSessionDialog,
    setUiNotice,
    snapshotData,
    snapshotDataRef,
    snapshotIdentity,
  });
  const executionAskCommandStates = buildExecutionAskCommandStates(
    executionAskErrorsById,
    commandActions.pending,
  );
  const activeExecutionAskId =
    snapshotData?.snapshot.activeAsk?.id ?? null;
  const activeExecutionAskState =
    activeExecutionAskId === null
      ? null
      : executionAskCommandStates[activeExecutionAskId] ?? null;

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
    isAnsweringAuthoringAsk:
      commandActions.pending.isAnsweringAuthoringAsk,
    executionAskCommandStates,
    executionAskError: activeExecutionAskState?.commandError ?? null,
    executionAskRecoveryActions:
      activeExecutionAskState?.commandRecoveryActions ?? [],
    isAnsweringAsk: activeExecutionAskState?.isAnswering ?? false,
    isCancellingAsk: activeExecutionAskState?.isCancelling ?? false,
    isDeferringAsk: activeExecutionAskState?.isDeferring ?? false,
    isInputSubmitting: commandActions.pending.isInputSubmitting,
    isPublishingTaskTree: commandActions.pending.isPublishingTaskTree,
    isArchivingPlan: commandActions.pending.isArchivingPlan,
    isRepairingAuthoringState:
      commandActions.pending.isRepairingAuthoringState,
    isRenamingSession: sessionLifecycle.isRenamingSession,
    isRetryingTask: commandActions.pending.isRetryingTask,
    isStoppingTask: commandActions.pending.isStoppingTask,
    isResolvingConfirmation:
      commandActions.pending.isResolvingConfirmation,
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
      answerAuthoringAskBatch: commandActions.actions.answerAuthoringAskBatch,
      answerAsk: commandActions.actions.answerAsk,
      archivePlan: commandActions.actions.archivePlan,
      cancelSessionDialog: sessionLifecycle.actions.cancelSessionDialog,
      cancelAsk: commandActions.actions.cancelAsk,
      changeSessionDialogDraft:
        sessionLifecycle.actions.changeSessionDialogDraft,
      changeInputDraft,
      changeState: commandActions.actions.changeState,
      createSession: sessionLifecycle.actions.createSession,
      deleteSession: sessionLifecycle.actions.deleteSession,
      repairAuthoringState: commandActions.actions.repairAuthoringState,
      deferAsk: commandActions.actions.deferAsk,
      renameSession: sessionLifecycle.actions.renameSession,
      resolveConfirmation: commandActions.actions.resolveConfirmation,
      retryTask: commandActions.actions.retryTask,
      stopTask: commandActions.actions.stopTask,
      selectSession,
      selectTaskPlan: selectionActions.selectTaskPlan,
      selectTask: selectionActions.selectTask,
      showFileChanges: selectionActions.showFileChanges,
      showResult: selectionActions.showResult,
      submitSessionDialog: sessionLifecycle.actions.submitSessionDialog,
      submitInput: commandActions.actions.submitInput,
      publishTaskTree: commandActions.actions.publishTaskTree,
    },
  };
}

function buildExecutionAskCommandStates(
  errorsByAskId: ExecutionAskCommandErrorsById,
  pending: MainPageCommandPendingState,
): Record<string, ExecutionAskConversationCommandState> {
  const askIds = new Set(Object.keys(errorsByAskId));
  for (const askId of [
    pending.answeringAskId,
    pending.cancellingAskId,
    pending.deferringAskId,
  ]) {
    if (askId !== null) {
      askIds.add(askId);
    }
  }

  return Object.fromEntries(
    [...askIds].map((askId) => {
      const error = errorsByAskId[askId];
      return [
        askId,
        {
          askId,
          commandError: error?.message ?? null,
          commandRecoveryActions: error?.recoveryActions ?? [],
          isAnswering: pending.answeringAskId === askId,
          isCancelling: pending.cancellingAskId === askId,
          isDeferring: pending.deferringAskId === askId,
        },
      ];
    }),
  );
}
