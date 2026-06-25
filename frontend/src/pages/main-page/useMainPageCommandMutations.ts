import { useMutation } from "@tanstack/react-query";
import type { Dispatch, SetStateAction } from "react";

import type {
  AnswerAuthoringAskItemPayload,
  ProductRecoveryAction,
} from "../../shared/api/platoApi";
import { productRecoveryActionsFromApiError } from "../../shared/api/productErrors";
import type {
  AskId,
  ConfirmationActionView,
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
import {
  buildRuntimeInputRouteRequest,
  prependRuntimeActivityItems,
  runtimeInputActivity,
  runtimeInputNotice,
  runtimeInputUserActivity,
} from "./mainPageRuntimeInput";
import type { MainPageInputCommandMode } from "./mainPageViewModel";
import { handleCommandResponse } from "./runtime/commandRefresh";
import type {
  MainPageAdapter,
  MainPageRuntimeSnapshot,
} from "./runtime/adapter";

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

export type ConfirmationDecisionContext = {
  confirmation: ConfirmationActionView | undefined;
  decision: string;
  sessionId: string;
};

export type AnswerAuthoringAskBatchContext = {
  answers: AnswerAuthoringAskItemPayload[];
  rawTaskId: string;
  sessionId: string;
};

export type RepairAuthoringStateContext = {
  sessionId: string;
};

export type AnswerExecutionAskContext = {
  askId: AskId;
  selectedOptionIds: string[];
  sessionId: string;
  text?: string | null;
};

export type DeferExecutionAskContext = {
  askId: AskId;
  reason?: string | null;
  sessionId: string;
};

export type CancelExecutionAskContext = {
  askId: AskId;
  reason: string;
  sessionId: string;
};

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
  const resolveConfirmationMutation = useMutation({
    mutationFn: async ({
      confirmation,
      decision,
      sessionId,
    }: {
      confirmation: ConfirmationActionView;
      decision: string;
      sessionId: string;
    }) =>
      adapter.resolveConfirmation(
        sessionId,
        confirmation.id,
        {
          commandId: `resolve-${confirmation.id}-${decision}`,
          sessionId,
          payload: {
            value: decision,
          },
        },
        activeWorkspaceId,
      ),
    onError: () => {
      setConfirmationCommandError("Confirmation failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Confirmation was rejected.",
      );

      if (result.errorMessage) {
        setConfirmationCommandError(
          result.errorMessage,
          result.recoveryActions,
        );
        return;
      }

      setConfirmationCommandError(null);
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  const answerAuthoringAskBatchMutation = useMutation({
    mutationFn: async ({
      answers,
      rawTaskId,
      sessionId,
    }: AnswerAuthoringAskBatchContext) =>
      adapter.answerAuthoringAskBatch(
        sessionId,
        rawTaskId,
        {
          commandId: `answer-authoring-asks-${rawTaskId}-${Date.now()}`,
          sessionId,
          payload: {
            answers,
          },
        },
        activeWorkspaceId,
      ),
    onError: () => {
      setAuthoringAskCommandError("Answer submission failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Answer submission was rejected.",
      );

      if (result.errorMessage) {
        setAuthoringAskCommandError(
          result.errorMessage,
          result.recoveryActions,
        );
        return;
      }

      setAuthoringAskCommandError(null);
      setUiNotice("Authoring answers submitted.");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  const repairAuthoringStateMutation = useMutation({
    mutationFn: async ({ sessionId }: RepairAuthoringStateContext) =>
      adapter.repairAuthoringState(
        {
          commandId: `repair-authoring-state-${Date.now()}`,
          sessionId,
          payload: {
            reason: "dirty_authoring_state",
          },
        },
        activeWorkspaceId,
      ),
    onError: () => {
      setTaskTreeCommandError("Authoring repair failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Authoring repair was rejected.",
      );

      if (result.errorMessage) {
        setTaskTreeCommandError(result.errorMessage);
        return;
      }

      setTaskTreeCommandError(null);
      setUiNotice("Authoring state repaired.");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  const answerAskMutation = useMutation({
    mutationFn: async ({
      askId,
      selectedOptionIds,
      sessionId,
      text,
    }: AnswerExecutionAskContext) =>
      adapter.answerAsk(
        sessionId,
        askId,
        {
          commandId: `answer-ask-${askId}-${Date.now()}`,
          sessionId,
          payload: {
            selectedOptionIds,
            text: text ?? null,
          },
        },
        activeWorkspaceId,
      ),
    onError: () => {
      setExecutionAskCommandError("Answer submission failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Answer submission was rejected.",
      );

      if (result.errorMessage) {
        setExecutionAskCommandError(
          result.errorMessage,
          result.recoveryActions,
        );
        if (result.shouldRefetch) {
          void refetchSnapshot();
        }
        return;
      }

      setExecutionAskCommandError(null);
      setUiNotice("Answer submitted.");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  const deferAskMutation = useMutation({
    mutationFn: async ({ askId, reason, sessionId }: DeferExecutionAskContext) =>
      adapter.deferAsk(
        sessionId,
        askId,
        {
          commandId: `defer-ask-${askId}-${Date.now()}`,
          sessionId,
          payload: {
            reason: reason ?? null,
          },
        },
        activeWorkspaceId,
      ),
    onError: () => {
      setExecutionAskCommandError("Defer failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(response, "Defer was rejected.");

      if (result.errorMessage) {
        setExecutionAskCommandError(
          result.errorMessage,
          result.recoveryActions,
        );
        return;
      }

      setExecutionAskCommandError(null);
      setUiNotice("Question deferred.");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });

  const cancelAskMutation = useMutation({
    mutationFn: async ({ askId, reason, sessionId }: CancelExecutionAskContext) =>
      adapter.cancelAsk(
        sessionId,
        askId,
        {
          commandId: `cancel-ask-${askId}-${Date.now()}`,
          sessionId,
          payload: {
            reason,
          },
        },
        activeWorkspaceId,
      ),
    onError: () => {
      setExecutionAskCommandError("Cancel failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(response, "Cancel was rejected.");

      if (result.errorMessage) {
        setExecutionAskCommandError(
          result.errorMessage,
          result.recoveryActions,
        );
        return;
      }

      setExecutionAskCommandError(null);
      setUiNotice("Question cancelled.");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
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

  const runtimeInputMutation = useMutation({
    mutationFn: async ({
      content,
      routeMode,
      sessionId,
      target,
      taskNodeId,
    }: {
      content: string;
      routeMode: RuntimeInputMode;
      sessionId: string;
      target: InputTarget;
      taskNodeId: TaskNodeId | null;
    }) => {
      if (adapter.routeRuntimeInput === undefined) {
        throw new Error("Runtime input router is unavailable.");
      }

      const request = buildRuntimeInputRouteRequest({
        content,
        mode: routeMode,
        sessionId,
        snapshot: getSnapshotData()?.snapshot ?? null,
        target,
        taskNodeId,
      });
      const response = await adapter.routeRuntimeInput(
        request,
        activeWorkspaceId,
      );
      return { request, response };
    },
    onError: () => {
      setInputCommandError("Question routing failed. Please retry.");
    },
    onSettled: () => {
      setActiveRuntimeInputMode(null);
    },
    onSuccess: ({ request, response }) => {
      if (!response.ok || response.data === null) {
        setInputCommandError(
          response.error?.message ?? "Question could not be answered.",
          productRecoveryActionsFromApiError(response.error),
        );
        return;
      }

      const routeResult = response.data;
      if (
        routeResult.commandResponse !== null &&
        routeResult.commandResponse !== undefined
      ) {
        const commandResult = handleCommandResponse(
          routeResult.commandResponse,
          "Runtime input command was rejected.",
        );

        if (commandResult.errorMessage) {
          setInputCommandError(
            commandResult.errorMessage,
            commandResult.recoveryActions,
          );
          return;
        }

        setInputCommandError(null);
        setInputDraft("");
        setUiNotice(routeResult.outcome.userMessage);
        if (commandResult.shouldRefetch) {
          void refetchSnapshot();
        }
        return;
      }

      if (
        routeResult.outcome.status === "answered" ||
        routeResult.outcome.status === "dispatched"
      ) {
        const runtimeActivity = runtimeInputActivity(routeResult);
        const runtimeActivities = [
          runtimeInputUserActivity(request, routeResult),
          ...(runtimeActivity === null ? [] : [runtimeActivity]),
        ];
        if (runtimeActivities.length > 0) {
          setRuntimeActivityItems((items) =>
            prependRuntimeActivityItems(items, runtimeActivities),
          );
        }
        setInputCommandError(null);
        setInputDraft("");
        setUiNotice(runtimeInputNotice(routeResult));
        void refetchSnapshot();
        return;
      }

      setInputCommandError(
        routeResult.outcome.userMessage,
        routeResult.outcome.recoveryActions,
      );
    },
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
