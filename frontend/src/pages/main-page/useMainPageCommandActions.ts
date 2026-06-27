import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type { RuntimeInputMode } from "../../shared/api/types";
import type { MainPageStateId } from "./mockPlatoApi";
import {
  createRuntimeInputCommandId,
  runtimeInputModeFor,
} from "./mainPageRuntimeInput";
import type {
  AnswerAuthoringAskBatchContext,
  AnswerExecutionAskContext,
  ArchivePlanContext,
  CancelExecutionAskContext,
  ConfirmationDecisionContext,
  DeferExecutionAskContext,
  InputSubmitContext,
  MainPageCommandMutations,
  PublishTaskTreeContext,
  RepairAuthoringStateContext,
  RetryTaskContext,
  StopTaskContext,
} from "./useMainPageCommandMutations";

type CommandErrorSetter = (
  message: string | null,
  recoveryActions?: ProductRecoveryAction[],
) => void;

export type MainPageCommandActions = {
  answerAuthoringAskBatch: (context: AnswerAuthoringAskBatchContext) => void;
  answerAsk: (context: AnswerExecutionAskContext) => void;
  archivePlan: (context: ArchivePlanContext) => void;
  cancelAsk: (context: CancelExecutionAskContext) => void;
  changeState: (nextStateId: MainPageStateId) => void;
  deferAsk: (context: DeferExecutionAskContext) => void;
  publishTaskTree: (context: PublishTaskTreeContext) => void;
  repairAuthoringState: (context: RepairAuthoringStateContext) => void;
  resolveConfirmation: (context: ConfirmationDecisionContext) => void;
  retryTask: (context: RetryTaskContext) => void;
  stopTask: (context: StopTaskContext) => void;
  submitInput: (context: InputSubmitContext) => string | null;
};

export type MainPageCommandPendingState = {
  isAnsweringAuthoringAsk: boolean;
  isAnsweringAsk: boolean;
  isArchivingPlan: boolean;
  isCancellingAsk: boolean;
  isDeferringAsk: boolean;
  isInputSubmitting: boolean;
  isPublishingTaskTree: boolean;
  isRepairingAuthoringState: boolean;
  isResolvingConfirmation: boolean;
  isRetryingTask: boolean;
  isStoppingTask: boolean;
};

export type UseMainPageCommandActionsOptions = {
  clearEventError: () => void;
  commandMutations: MainPageCommandMutations;
  inputDraft: string;
  resetCommandErrorState: () => void;
  resetInputDraft: () => void;
  resetSelection: () => void;
  resetSessionLifecycle: () => void;
  routeRuntimeInputAvailable: boolean;
  setActiveRuntimeInputMode: (mode: RuntimeInputMode | null) => void;
  setAuthoringAskCommandError: CommandErrorSetter;
  setConfirmationCommandError: CommandErrorSetter;
  setExecutionAskCommandError: CommandErrorSetter;
  setInputCommandError: CommandErrorSetter;
  setStateId: (stateId: MainPageStateId) => void;
  setTaskTreeCommandError: (message: string | null) => void;
  setTaskTreeCommandFailure: CommandErrorSetter;
  setUiNotice: (notice: string | null) => void;
};

export function useMainPageCommandActions({
  clearEventError,
  commandMutations,
  inputDraft,
  resetCommandErrorState,
  resetInputDraft,
  resetSelection,
  resetSessionLifecycle,
  routeRuntimeInputAvailable,
  setActiveRuntimeInputMode,
  setAuthoringAskCommandError,
  setConfirmationCommandError,
  setExecutionAskCommandError,
  setInputCommandError,
  setStateId,
  setTaskTreeCommandError,
  setTaskTreeCommandFailure,
  setUiNotice,
}: UseMainPageCommandActionsOptions): {
  actions: MainPageCommandActions;
  pending: MainPageCommandPendingState;
} {
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
  } = commandMutations;

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
  }: InputSubmitContext): string | null {
    const content = inputDraft.trim();

    if (!content) {
      return null;
    }

    setInputCommandError(null);
    setUiNotice(null);
    if (routeRuntimeInputAvailable) {
      const commandId = createRuntimeInputCommandId();
      const routeMode = runtimeInputModeFor(content, mode);
      setActiveRuntimeInputMode(routeMode);
      runtimeInputMutation.mutate({
        commandId,
        content,
        routeMode,
        sessionId,
        target,
        taskNodeId,
      });
      return commandId;
    }

    inputMutation.mutate({
      content,
      mode,
      sessionId,
      target,
      taskNodeId,
    });
    return null;
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
    actions: {
      answerAuthoringAskBatch: handleAnswerAuthoringAskBatch,
      answerAsk: handleAnswerAsk,
      archivePlan: handleArchivePlan,
      cancelAsk: handleCancelAsk,
      changeState: handleStateChange,
      deferAsk: handleDeferAsk,
      publishTaskTree: handlePublishTaskTree,
      repairAuthoringState: handleRepairAuthoringState,
      resolveConfirmation: handleConfirmationDecision,
      retryTask: handleRetryTask,
      stopTask: handleStopTask,
      submitInput: handleInputSubmit,
    },
    pending: {
      isAnsweringAuthoringAsk: answerAuthoringAskBatchMutation.isPending,
      isAnsweringAsk: answerAskMutation.isPending,
      isArchivingPlan: archivePlanMutation.isPending,
      isCancellingAsk: cancelAskMutation.isPending,
      isDeferringAsk: deferAskMutation.isPending,
      isInputSubmitting:
        inputMutation.isPending || runtimeInputMutation.isPending,
      isPublishingTaskTree: publishTaskTreeMutation.isPending,
      isRepairingAuthoringState: repairAuthoringStateMutation.isPending,
      isResolvingConfirmation: resolveConfirmationMutation.isPending,
      isRetryingTask: retryTaskMutation.isPending,
      isStoppingTask: stopTaskMutation.isPending,
    },
  };
}
