import { useState } from "react";

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
import {
  useMainPageCommandActions,
  type MainPageCommandActions,
} from "./useMainPageCommandActions";
import { useMainPageCommandErrorState } from "./useMainPageCommandErrorState";
import { useMainPageInputRuntimeState } from "./useMainPageInputRuntimeState";
import {
  useMainPageSessionIdentityAdoption,
  useMainPageSessionIdentityState,
} from "./useMainPageSessionIdentityState";
import { useMainPageUiNoticeState } from "./useMainPageUiNoticeState";
import { useMainPageCommandMutations } from "./useMainPageCommandMutations";
import { useMainPageEventSubscription } from "./useMainPageEventSubscription";
import {
  useMainPageSessionLifecycle,
  type SessionLifecycleDialog,
} from "./useMainPageSessionLifecycle";
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
  actions: MainPageCommandActions & {
    cancelSessionDialog: () => void;
    changeSessionDialogDraft: (draftName: string) => void;
    changeInputDraft: (draft: string) => void;
    createSession: (workspaceId?: WorkspaceId | null) => void;
    deleteSession: (session: SessionSummary) => void;
    renameSession: (session: SessionSummary) => void;
    selectSession: (session: SessionSummary, currentSessionId: string) => void;
    selectTaskPlan: () => void;
    selectTask: (nodeId: TaskNodeId) => void;
    showFileChanges: () => void;
    showResult: () => void;
    submitSessionDialog: () => void;
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
    reconcileRuntimeInputSubmit,
    rejectRuntimeInputSubmit,
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
    executionAskError,
    executionAskRecoveryActions,
    isAnsweringAsk: commandActions.pending.isAnsweringAsk,
    isCancellingAsk: commandActions.pending.isCancellingAsk,
    isDeferringAsk: commandActions.pending.isDeferringAsk,
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
