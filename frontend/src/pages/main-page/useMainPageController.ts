import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

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
import {
  summarizeMainPageSnapshot,
} from "../../shared/api/traceSummary";
import {
  createFrontendLogger,
  summarizeLoggableError,
  toLoggableError,
} from "../../shared/logging/frontendLogger";
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
  mainPageSnapshotIdentity,
  mainPageSnapshotQueryKey,
} from "./runtime/adapter";
import {
  useMainPageAuthoringCommands,
  type AnswerAuthoringAskBatchContext,
  type RepairAuthoringStateContext,
} from "./useMainPageAuthoringCommands";
import {
  useMainPageConfirmationCommands,
  type ConfirmationDecisionContext,
} from "./useMainPageConfirmationCommands";
import { useMainPageCommandState } from "./useMainPageCommandState";
import { useMainPageEventSubscription } from "./useMainPageEventSubscription";
import {
  useMainPageExecutionAskCommands,
  type AnswerExecutionAskContext,
  type CancelExecutionAskContext,
  type DeferExecutionAskContext,
} from "./useMainPageExecutionAskCommands";
import {
  useMainPagePlanCommands,
  type ArchivePlanContext,
  type PublishTaskTreeContext,
} from "./useMainPagePlanCommands";
import {
  useMainPageRuntimeInputCommands,
  type InputSubmitContext,
} from "./useMainPageRuntimeInputCommands";
import {
  useMainPageSessionDialogState,
  type SessionLifecycleDialog,
} from "./useMainPageSessionDialogState";
import { useMainPageSessionLifecycleCommands } from "./useMainPageSessionLifecycleCommands";
import {
  useMainPageTaskLifecycleCommands,
  type RetryTaskContext,
  type StopTaskContext,
} from "./useMainPageTaskLifecycleCommands";

const mainPageLogger = createFrontendLogger("main-page");

export type {
  AnswerAuthoringAskBatchContext,
  RepairAuthoringStateContext,
} from "./useMainPageAuthoringCommands";
export type { ConfirmationDecisionContext } from "./useMainPageConfirmationCommands";
export type {
  AnswerExecutionAskContext,
  CancelExecutionAskContext,
  DeferExecutionAskContext,
} from "./useMainPageExecutionAskCommands";
export type {
  ArchivePlanContext,
  PublishTaskTreeContext,
} from "./useMainPagePlanCommands";
export type { InputSubmitContext } from "./useMainPageRuntimeInputCommands";
export type { SessionLifecycleDialog } from "./useMainPageSessionDialogState";
export type {
  RetryTaskContext,
  StopTaskContext,
} from "./useMainPageTaskLifecycleCommands";

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
  const [selectedTaskNodeId, setSelectedTaskNodeId] =
    useState<TaskNodeId | null>(null);
  const [selectionTarget, setSelectionTarget] =
    useState<MainPageSelectionTarget>("auto");
  const [detailOverride, setDetailOverride] =
    useState<DetailOverride>("auto");
  const [inputDraft, setInputDraft] = useState("");
  const [uiNotice, setUiNotice] = useState<string | null>(null);
  const [runtimeActivityItems, setRuntimeActivityItems] = useState<
    SessionActivityItemView[]
  >([]);
  const [activeRuntimeInputMode, setActiveRuntimeInputMode] =
    useState<RuntimeInputMode | null>(null);
  const {
    authoringAskError,
    authoringAskRecoveryActions,
    clearCommandState,
    confirmationError,
    confirmationRecoveryActions,
    executionAskError,
    executionAskRecoveryActions,
    inputError,
    inputRecoveryActions,
    setAuthoringAskCommandError,
    setConfirmationCommandError,
    setExecutionAskCommandError,
    setInputCommandError,
    setTaskTreeCommandError,
    setTaskTreeCommandFailure,
    taskTreeCommandError,
    taskTreeCommandRecoveryActions,
  } = useMainPageCommandState();
  const {
    changeSessionDialogDraft,
    closeSessionDialog,
    openCreateSessionDialog,
    openDeleteSessionDialog,
    openRenameSessionDialog,
    sessionDialog,
    setSessionDialogError,
  } = useMainPageSessionDialogState();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(
    adapter.sessionId,
  );
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<WorkspaceId | null>(
    adapter.workspaceId ?? null,
  );
  const workspaceCatalogQuery = useQuery({
    enabled: adapter.loadWorkspaceCatalog !== undefined,
    queryKey: ["main-page", "workspaces", adapter.runtimeKind],
    queryFn: () => {
      if (adapter.loadWorkspaceCatalog === undefined) {
        throw new Error("Workspace catalog is unavailable.");
      }
      return adapter.loadWorkspaceCatalog();
    },
  });
  const workspaceCatalog = workspaceCatalogQuery.data ?? null;

  const snapshotQuery = useQuery({
    queryKey: mainPageSnapshotQueryKey(
      adapter,
      stateId,
      activeSessionId,
      activeWorkspaceId,
    ),
    queryFn: () => adapter.loadSnapshot(stateId, activeSessionId, activeWorkspaceId),
  });
  const snapshotData = snapshotQuery.data;
  const snapshotDataRef = useRef(snapshotData);
  const initialTaskNodeIdRef = useRef<TaskNodeId | null>(initialTaskNodeId);
  snapshotDataRef.current = snapshotData;
  const snapshotIdentity = snapshotData
    ? mainPageSnapshotIdentity(
        adapter,
        stateId,
        snapshotData,
        activeSessionId,
        activeWorkspaceId,
      )
    : null;
  const refetchSnapshot = snapshotQuery.refetch;
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

  function refetchWorkspaceCatalog() {
    if (adapter.loadWorkspaceCatalog === undefined) {
      return;
    }
    void workspaceCatalogQuery.refetch();
  }

  useEffect(() => {
    if (!snapshotData || activeSessionId !== null) {
      return;
    }
    setActiveSessionId(snapshotData.snapshot.session.id);
  }, [activeSessionId, snapshotData]);

  useEffect(() => {
    if (activeWorkspaceId !== null || workspaceCatalog === null) {
      return;
    }
    setActiveWorkspaceId(workspaceCatalog.currentWorkspaceId);
  }, [activeWorkspaceId, workspaceCatalog]);

  useEffect(() => {
    setRuntimeActivityItems([]);
  }, [activeSessionId, activeWorkspaceId]);

  useEffect(() => {
    if (!snapshotQuery.isError) {
      return;
    }

    mainPageLogger.error(
      `snapshot.query.failed ${stateId} -> ${summarizeLoggableError(
        snapshotQuery.error,
      )}`,
      {
        error: toLoggableError(snapshotQuery.error),
        runtimeKind: adapter.runtimeKind,
        stateId,
      },
    );
  }, [adapter.runtimeKind, snapshotQuery.error, snapshotQuery.isError, stateId]);

  useEffect(() => {
    if (!snapshotData) {
      return;
    }

    mainPageLogger.info("snapshot.query.data", {
      ...summarizeMainPageSnapshot(snapshotData.snapshot),
      activeSessionId,
      runtimeKind: adapter.runtimeKind,
      stateId,
    });
  }, [activeSessionId, adapter.runtimeKind, snapshotData, stateId]);

  const {
    resolveConfirmationMutation,
  } = useMainPageConfirmationCommands({
    activeWorkspaceId,
    adapter,
    refetchSnapshot,
    setConfirmationCommandError,
  });

  const {
    answerAuthoringAskBatchMutation,
    repairAuthoringStateMutation,
  } = useMainPageAuthoringCommands({
    activeWorkspaceId,
    adapter,
    refetchSnapshot,
    setAuthoringAskCommandError,
    setTaskTreeCommandError,
    setUiNotice,
  });

  const {
    answerAskMutation,
    cancelAskMutation,
    deferAskMutation,
  } = useMainPageExecutionAskCommands({
    activeWorkspaceId,
    adapter,
    refetchSnapshot,
    setExecutionAskCommandError,
    setUiNotice,
  });

  const {
    isInputSubmitting,
    resetInputCommands,
    submitInput,
  } = useMainPageRuntimeInputCommands({
    activeWorkspaceId,
    adapter,
    getSnapshot: () => snapshotDataRef.current,
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
  } = useMainPagePlanCommands({
    activeWorkspaceId,
    adapter,
    onArchivePlanSucceeded: () => {
      setSelectedTaskNodeId(null);
      setSelectionTarget("auto");
      setDetailOverride("auto");
    },
    refetchSnapshot,
    setTaskTreeCommandFailure,
    setUiNotice,
  });

  const {
    retryTaskMutation,
    stopTaskMutation,
  } = useMainPageTaskLifecycleCommands({
    activeWorkspaceId,
    adapter,
    refetchSnapshot,
    setTaskTreeCommandFailure,
    setUiNotice,
  });

  const {
    createSessionMutation,
    deleteSessionMutation,
    renameSessionMutation,
  } = useMainPageSessionLifecycleCommands({
    adapter,
    closeSessionDialog,
    refetchSnapshot,
    refetchWorkspaceCatalog,
    setActiveSessionId,
    setActiveWorkspaceId,
    setSessionDialogError,
    setUiNotice,
  });

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
    setSelectedTaskNodeId(nextSelectedTaskNodeId);
    setSelectionTarget("auto");
    setDetailOverride("auto");
    setInputDraft("");
    clearCommandState();
    setUiNotice(null);
    closeSessionDialog();
    clearEventError();
  }, [clearCommandState, clearEventError, closeSessionDialog, snapshotIdentity]);

  function handleStateChange(nextStateId: MainPageStateId) {
    setStateId(nextStateId);
    setSelectedTaskNodeId(null);
    setSelectionTarget("auto");
    setDetailOverride("auto");
    setInputDraft("");
    clearCommandState();
    setUiNotice(null);
    closeSessionDialog();
    clearEventError();
    resolveConfirmationMutation.reset();
    answerAuthoringAskBatchMutation.reset();
    repairAuthoringStateMutation.reset();
    answerAskMutation.reset();
    deferAskMutation.reset();
    cancelAskMutation.reset();
    resetInputCommands();
    publishTaskTreeMutation.reset();
    createSessionMutation.reset();
    renameSessionMutation.reset();
    deleteSessionMutation.reset();
  }

  function selectTask(nodeId: TaskNodeId) {
    setSelectedTaskNodeId(nodeId);
    setSelectionTarget("task");
    setDetailOverride("auto");
    setUiNotice(null);
  }

  function selectTaskPlan() {
    setSelectedTaskNodeId(null);
    setSelectionTarget("plan");
    setDetailOverride("auto");
    setUiNotice(null);
  }

  function handleSessionSelect(
    session: SessionSummary,
    currentSessionId: string,
  ) {
    const nextWorkspaceId = session.workspaceId ?? activeWorkspaceId;
    if (session.id === currentSessionId && nextWorkspaceId === activeWorkspaceId) {
      setUiNotice("This session is already open.");
      return;
    }

    setActiveWorkspaceId(nextWorkspaceId ?? null);
    setActiveSessionId(session.id);
  }

  function handleCreateSession(workspaceId?: WorkspaceId | null) {
    const targetWorkspaceId = workspaceId ?? activeWorkspaceId;
    if (targetWorkspaceId !== activeWorkspaceId) {
      setActiveWorkspaceId(targetWorkspaceId ?? null);
    }
    if (!snapshotDataRef.current) {
      createSessionMutation.mutate({
        name: "New session",
        workspaceId: targetWorkspaceId ?? null,
      });
      return;
    }

    openCreateSessionDialog();
  }

  function handleRenameSession(session: SessionSummary) {
    openRenameSessionDialog(session);
  }

  function handleDeleteSession(session: SessionSummary) {
    openDeleteSessionDialog(session);
  }

  function handleSessionDialogCancel() {
    if (
      createSessionMutation.isPending ||
      renameSessionMutation.isPending ||
      deleteSessionMutation.isPending
    ) {
      return;
    }

    closeSessionDialog();
  }

  function handleSessionDialogSubmit() {
    if (sessionDialog.mode === "idle") {
      return;
    }

    if (sessionDialog.mode === "delete") {
      setUiNotice(null);
      deleteSessionMutation.mutate({
        sessionId: sessionDialog.session.id,
        workspaceId: sessionDialog.session.workspaceId ?? activeWorkspaceId,
      });
      return;
    }

    const trimmed = sessionDialog.draftName.trim();
    if (!trimmed) {
      setSessionDialogError("Session name must not be empty.");
      return;
    }

    setUiNotice(null);

    if (sessionDialog.mode === "create") {
      createSessionMutation.mutate({
        name: trimmed,
        workspaceId: activeWorkspaceId,
      });
      return;
    }

    renameSessionMutation.mutate({
      name: trimmed,
      sessionId: sessionDialog.session.id,
      workspaceId: sessionDialog.session.workspaceId ?? activeWorkspaceId,
    });
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

    submitInput({
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
    isCreatingSession: createSessionMutation.isPending,
    isDeletingSession: deleteSessionMutation.isPending,
    isAnsweringAuthoringAsk: answerAuthoringAskBatchMutation.isPending,
    executionAskError,
    executionAskRecoveryActions,
    isAnsweringAsk: answerAskMutation.isPending,
    isCancellingAsk: cancelAskMutation.isPending,
    isDeferringAsk: deferAskMutation.isPending,
    isInputSubmitting,
    isPublishingTaskTree: publishTaskTreeMutation.isPending,
    isArchivingPlan: archivePlanMutation.isPending,
    isRepairingAuthoringState: repairAuthoringStateMutation.isPending,
    isRenamingSession: renameSessionMutation.isPending,
    isRetryingTask: retryTaskMutation.isPending,
    isStoppingTask: stopTaskMutation.isPending,
    isResolvingConfirmation: resolveConfirmationMutation.isPending,
    activeRuntimeInputMode,
    selectionTarget,
    sessionDialog,
    isSnapshotError: snapshotQuery.isError,
    isSnapshotPending: snapshotQuery.isPending,
    selectedTaskNodeId,
    snapshotData,
    snapshotError: snapshotQuery.error,
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
      cancelSessionDialog: handleSessionDialogCancel,
      cancelAsk: handleCancelAsk,
      changeSessionDialogDraft,
      changeInputDraft: setInputDraft,
      changeState: handleStateChange,
      createSession: handleCreateSession,
      deleteSession: handleDeleteSession,
      repairAuthoringState: handleRepairAuthoringState,
      deferAsk: handleDeferAsk,
      renameSession: handleRenameSession,
      resolveConfirmation: handleConfirmationDecision,
      retryTask: handleRetryTask,
      stopTask: handleStopTask,
      selectSession: handleSessionSelect,
      selectTaskPlan,
      selectTask,
      showFileChanges: () => setDetailOverride("fileChanges"),
      showResult: () => setDetailOverride("result"),
      submitSessionDialog: handleSessionDialogSubmit,
      submitInput: handleInputSubmit,
      publishTaskTree: handlePublishTaskTree,
    },
  };
}
