import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import type {
  AnswerAuthoringAskItemPayload,
  ProductRecoveryAction,
  WorkspaceCatalogResult,
} from "../../shared/api/platoApi";
import type {
  ConfirmationActionView,
  AskId,
  MainPageSnapshot,
  RuntimeInputRouteRequest,
  RuntimeInputRouteResult,
  SessionActivityItemView,
  SessionSummary,
  TaskNodeId,
  WorkspaceId,
} from "../../shared/api/types";
import { productRecoveryActionsFromApiError } from "../../shared/api/productErrors";
import {
  summarizeCommandResponse,
  summarizeMainPageSnapshot,
  summarizeUiEvent,
} from "../../shared/api/traceSummary";
import {
  createFrontendLogger,
  summarizeLoggableError,
  toLoggableError,
} from "../../shared/logging/frontendLogger";
import type {
  DetailOverride,
  EventConnectionStatus,
  InputTarget,
  MainPageSelectionTarget,
} from "./mainPageUiTypes";
import type { MainPageInputCommandMode } from "./mainPageViewModel";
import type { MainPageStateId } from "./mockPlatoApi";
import type {
  MainPageAdapter,
  MainPageRuntimeSnapshot,
} from "./runtime/adapter";
import {
  mainPageSnapshotIdentity,
  mainPageSnapshotQueryKey,
} from "./runtime/adapter";
import { handleCommandResponse } from "./runtime/commandRefresh";
import { resyncEventKey, routeMainPageEvent } from "./runtime/eventRouter";

const mainPageLogger = createFrontendLogger("main-page");

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

export type SessionLifecycleDialog =
  | {
      mode: "idle";
    }
  | {
      draftName: string;
      error: string | null;
      mode: "create";
    }
  | {
      draftName: string;
      error: string | null;
      mode: "rename";
      session: SessionSummary;
    }
  | {
      error: string | null;
      mode: "delete";
      session: SessionSummary;
    };

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
  isRepairingAuthoringState: boolean;
  isRenamingSession: boolean;
  isRetryingTask: boolean;
  isStoppingTask: boolean;
  isResolvingConfirmation: boolean;
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
  const [confirmationError, setConfirmationError] = useState<string | null>(
    null,
  );
  const [confirmationRecoveryActions, setConfirmationRecoveryActions] =
    useState<ProductRecoveryAction[]>([]);
  const [authoringAskError, setAuthoringAskError] = useState<string | null>(
    null,
  );
  const [authoringAskRecoveryActions, setAuthoringAskRecoveryActions] =
    useState<ProductRecoveryAction[]>([]);
  const [executionAskError, setExecutionAskError] = useState<string | null>(
    null,
  );
  const [executionAskRecoveryActions, setExecutionAskRecoveryActions] =
    useState<ProductRecoveryAction[]>([]);
  const [inputDraft, setInputDraft] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [inputRecoveryActions, setInputRecoveryActions] = useState<
    ProductRecoveryAction[]
  >([]);
  const [taskTreeCommandError, setTaskTreeCommandError] = useState<string | null>(
    null,
  );
  const [
    taskTreeCommandRecoveryActions,
    setTaskTreeCommandRecoveryActions,
  ] = useState<ProductRecoveryAction[]>([]);
  const [uiNotice, setUiNotice] = useState<string | null>(null);
  const [runtimeActivityItems, setRuntimeActivityItems] = useState<
    SessionActivityItemView[]
  >([]);
  const [sessionDialog, setSessionDialog] = useState<SessionLifecycleDialog>({
    mode: "idle",
  });
  const [eventError, setEventError] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(
    adapter.sessionId,
  );
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<WorkspaceId | null>(
    adapter.workspaceId ?? null,
  );
  const [eventConnectionStatus, setEventConnectionStatus] =
    useState<EventConnectionStatus>("disconnected");

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
  const lastEventCursorRef = useRef<string | null>(null);
  const lastResyncEventKeyRef = useRef<string | null>(null);
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

  function refetchWorkspaceCatalog() {
    if (adapter.loadWorkspaceCatalog === undefined) {
      return;
    }
    void workspaceCatalogQuery.refetch();
  }

  function setConfirmationCommandError(
    message: string | null,
    recoveryActions: ProductRecoveryAction[] = [],
  ) {
    setConfirmationError(message);
    setConfirmationRecoveryActions(message === null ? [] : recoveryActions);
  }

  function setAuthoringAskCommandError(
    message: string | null,
    recoveryActions: ProductRecoveryAction[] = [],
  ) {
    setAuthoringAskError(message);
    setAuthoringAskRecoveryActions(message === null ? [] : recoveryActions);
  }

  function setExecutionAskCommandError(
    message: string | null,
    recoveryActions: ProductRecoveryAction[] = [],
  ) {
    setExecutionAskError(message);
    setExecutionAskRecoveryActions(message === null ? [] : recoveryActions);
  }

  function setInputCommandError(
    message: string | null,
    recoveryActions: ProductRecoveryAction[] = [],
  ) {
    setInputError(message);
    setInputRecoveryActions(message === null ? [] : recoveryActions);
  }

  function setTaskTreeCommandFailure(
    message: string | null,
    recoveryActions: ProductRecoveryAction[] = [],
  ) {
    setTaskTreeCommandError(message);
    setTaskTreeCommandRecoveryActions(
      message === null ? [] : recoveryActions,
    );
  }

  function clearCommandRecoveryActions() {
    setAuthoringAskRecoveryActions([]);
    setConfirmationRecoveryActions([]);
    setExecutionAskRecoveryActions([]);
    setInputRecoveryActions([]);
    setTaskTreeCommandRecoveryActions([]);
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
      adapter.resolveConfirmation(sessionId, confirmation.id, {
        commandId: `resolve-${confirmation.id}-${decision}`,
        sessionId,
        payload: {
          value: decision,
        },
      }, activeWorkspaceId),
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
      adapter.answerAuthoringAskBatch(sessionId, rawTaskId, {
        commandId: `answer-authoring-asks-${rawTaskId}-${Date.now()}`,
        sessionId,
        payload: {
          answers,
        },
      }, activeWorkspaceId),
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
      adapter.repairAuthoringState({
        commandId: `repair-authoring-state-${Date.now()}`,
        sessionId,
        payload: {
          reason: "dirty_authoring_state",
        },
      }, activeWorkspaceId),
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
      adapter.answerAsk(sessionId, askId, {
        commandId: `answer-ask-${askId}-${Date.now()}`,
        sessionId,
        payload: {
          selectedOptionIds,
          text: text ?? null,
        },
      }, activeWorkspaceId),
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
      adapter.deferAsk(sessionId, askId, {
        commandId: `defer-ask-${askId}-${Date.now()}`,
        sessionId,
        payload: {
          reason: reason ?? null,
        },
      }, activeWorkspaceId),
    onError: () => {
      setExecutionAskCommandError("Defer failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Defer was rejected.",
      );

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
      adapter.cancelAsk(sessionId, askId, {
        commandId: `cancel-ask-${askId}-${Date.now()}`,
        sessionId,
        payload: {
          reason,
        },
      }, activeWorkspaceId),
    onError: () => {
      setExecutionAskCommandError("Cancel failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Cancel was rejected.",
      );

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
        return adapter.appendTaskInput(sessionId, taskNodeId, {
          commandId,
          sessionId,
          payload: {
            content,
            mode: "guidance",
          },
        }, activeWorkspaceId);
      }

      if (mode === "generate_task_tree") {
        return adapter.generateTaskTree({
          commandId: `generate-task-tree-${Date.now()}`,
          sessionId,
          payload: {
            prompt: content,
          },
        }, activeWorkspaceId);
      }

      return adapter.appendSessionInput({
        commandId,
        sessionId,
        payload: {
          content,
          mode: "global_guidance",
        },
      }, activeWorkspaceId);
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
      if (adapter.routeRuntimeInput === undefined) {
        throw new Error("Runtime input router is unavailable.");
      }

      return adapter.routeRuntimeInput(
        buildRuntimeInputRouteRequest({
          content,
          mode: runtimeInputModeFor(content, mode),
          sessionId,
          snapshot: snapshotDataRef.current?.snapshot ?? null,
          target,
          taskNodeId,
        }),
        activeWorkspaceId,
      );
    },
    onError: () => {
      setInputCommandError("Question routing failed. Please retry.");
    },
    onSuccess: (response) => {
      if (!response.ok || response.data === null) {
        setInputCommandError(
          response.error?.message ?? "Question could not be answered.",
          productRecoveryActionsFromApiError(response.error),
        );
        return;
      }

      const routeResult = response.data;
      if (routeResult.commandResponse !== null && routeResult.commandResponse !== undefined) {
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
        if (runtimeActivity !== null) {
          setRuntimeActivityItems((items) =>
            prependRuntimeActivityItem(items, runtimeActivity),
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
      adapter.publishTaskTree({
        commandId: `publish-task-tree-${Date.now()}`,
        sessionId,
        payload: {
          taskTreeId,
          startImmediately: true,
        },
      }, activeWorkspaceId),
    onError: () => {
      setTaskTreeCommandFailure("Publish failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Publish was rejected.",
      );

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

  const retryTaskMutation = useMutation({
    mutationFn: async ({
      sessionId,
      taskNodeId,
    }: {
      sessionId: string;
      taskNodeId: TaskNodeId;
    }) =>
      adapter.retryTask(sessionId, taskNodeId, {
        commandId: `retry-task-${taskNodeId}-${Date.now()}`,
        sessionId,
        payload: {
          startImmediately: true,
        },
      }, activeWorkspaceId),
    onError: () => {
      setTaskTreeCommandFailure("Retry failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Retry was rejected.",
      );

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
      mainPageLogger.info("command.stop.submit", {
        commandId,
        sessionId,
        taskNodeId,
      });
      return adapter.stopTask(sessionId, taskNodeId, {
        commandId,
        sessionId,
        payload: {
          reason: "user requested stop",
        },
      }, activeWorkspaceId);
    },
    onError: (error) => {
      mainPageLogger.error("command.stop.failed", {
        error: toLoggableError(error),
      });
      setTaskTreeCommandFailure("Stop failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Stop was rejected.",
      );
      mainPageLogger.info("command.stop.result", {
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
        mainPageLogger.info("snapshot.refetch.request", {
          reason: "stop_command_refresh",
        });
        void refetchSnapshot()
          .then((queryResult) => {
            mainPageLogger.info("snapshot.refetch.result", {
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
            mainPageLogger.error("snapshot.refetch.failed", {
              error: toLoggableError(error),
              reason: "stop_command_refresh",
            });
          });
      }
    },
  });

  const createSessionMutation = useMutation({
    mutationFn: async ({
      name,
      workspaceId,
    }: {
      name: string;
      workspaceId: WorkspaceId | null;
    }) =>
      adapter.createSession(
        {
          name,
        },
        workspaceId,
      ),
    onError: () => {
      setSessionDialogError("Create session failed. Please retry.");
    },
    onSuccess: (result) => {
      const nextSessionId = result.sessionId ?? result.session?.id ?? null;
      if (nextSessionId === null) {
        setSessionDialogError("Created session was unavailable. Please retry.");
        return;
      }

      if (result.session?.workspaceId) {
        setActiveWorkspaceId(result.session.workspaceId);
      }
      setActiveSessionId(nextSessionId);
      setUiNotice(`Created session ${result.session?.name ?? nextSessionId}.`);
      setSessionDialog({ mode: "idle" });
      refetchWorkspaceCatalog();
    },
  });

  const renameSessionMutation = useMutation({
    mutationFn: async ({
      name,
      sessionId,
      workspaceId,
    }: {
      name: string;
      sessionId: string;
      workspaceId: WorkspaceId | null;
    }) =>
      adapter.renameSession({
        name,
        sessionId,
      }, workspaceId),
    onError: () => {
      setSessionDialogError("Rename session failed. Please retry.");
    },
    onSuccess: (result) => {
      setUiNotice(`Renamed session to ${result.session?.name ?? "new name"}.`);
      setSessionDialog({ mode: "idle" });
      refetchWorkspaceCatalog();
      void refetchSnapshot();
    },
  });

  const deleteSessionMutation = useMutation({
    mutationFn: async ({
      sessionId,
      workspaceId,
    }: {
      sessionId: string;
      workspaceId: WorkspaceId | null;
    }) => adapter.deleteSession(sessionId, workspaceId),
    onError: () => {
      setSessionDialogError("Delete session failed. Please retry.");
    },
    onSuccess: (result) => {
      const nextSessionId = result.nextSessionId ?? null;
      setActiveSessionId(nextSessionId);
      setUiNotice("Session deleted.");
      setSessionDialog({ mode: "idle" });
      refetchWorkspaceCatalog();
    },
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
    setAuthoringAskError(null);
    setExecutionAskError(null);
    setConfirmationError(null);
    setInputDraft("");
    setInputError(null);
    setTaskTreeCommandError(null);
    clearCommandRecoveryActions();
    setUiNotice(null);
    setSessionDialog({ mode: "idle" });
    setEventError(null);
    lastEventCursorRef.current = null;
    lastResyncEventKeyRef.current = null;
  }, [snapshotIdentity]);

  useEffect(() => {
    if (!snapshotData) {
      return undefined;
    }

    mainPageLogger.info("events.subscribe.start", {
      runtimeKind: adapter.runtimeKind,
      sessionId: snapshotData.snapshot.session.id,
    });

    let active = true;
    setEventConnectionStatus("connected");

    let unsubscribe: (() => void) | null = null;
    try {
      unsubscribe = adapter.subscribeSessionEvents(
        snapshotData.snapshot.session.id,
        snapshotData.snapshot.cursor,
        (event) => {
          mainPageLogger.debug("events.received", {
            ...summarizeUiEvent(event),
          });

          if (event.cursor === lastEventCursorRef.current) {
            mainPageLogger.info("events.cursor.duplicate_ignored", {
              event: summarizeUiEvent(event),
            });
            return;
          }
          lastEventCursorRef.current = event.cursor;

          const nextResyncEventKey = resyncEventKey(event);
          if (nextResyncEventKey !== null) {
            if (nextResyncEventKey === lastResyncEventKeyRef.current) {
              mainPageLogger.info("events.resync.duplicate_ignored", {
                event: summarizeUiEvent(event),
              });
              return;
            }
            lastResyncEventKeyRef.current = nextResyncEventKey;
          }

          const action = routeMainPageEvent(event);
          mainPageLogger.info("events.route", {
            action,
            event: summarizeUiEvent(event),
          });
          if (action.kind === "ignore") {
            return;
          }

          if (action.errorMessage) {
            setEventError(action.errorMessage);
          }
          setEventConnectionStatus(action.status);
          mainPageLogger.info("snapshot.refetch.request", {
            event: summarizeUiEvent(event),
            reason: "event",
          });
          void refetchSnapshot()
            .then((queryResult) => {
              mainPageLogger.info("snapshot.refetch.result", {
                event: summarizeUiEvent(event),
                hasData: queryResult.data !== undefined,
                reason: "event",
                snapshot:
                  queryResult.data === undefined
                    ? null
                    : summarizeMainPageSnapshot(queryResult.data.snapshot),
                status: queryResult.status,
              });
            })
            .catch((error) => {
              mainPageLogger.error("snapshot.refetch.failed", {
                error: toLoggableError(error),
                event: summarizeUiEvent(event),
                reason: "event",
              });
            })
            .finally(() => {
              if (active) {
                setEventConnectionStatus("connected");
              }
            });
        },
        activeWorkspaceId,
      );
    } catch (error) {
      mainPageLogger.error("events.subscribe.failed", {
        error: toLoggableError(error),
        runtimeKind: adapter.runtimeKind,
        sessionId: snapshotData.snapshot.session.id,
      });
      setEventConnectionStatus("disconnected");
      setEventError(
        error instanceof Error
          ? `Event stream unavailable: ${error.message}`
          : "Event stream unavailable.",
      );
    }

    return () => {
      active = false;
      mainPageLogger.info("events.subscribe.stop", {
        runtimeKind: adapter.runtimeKind,
        sessionId: snapshotData.snapshot.session.id,
      });
      unsubscribe?.();
    };
  }, [activeWorkspaceId, adapter, refetchSnapshot, snapshotData]);

  function handleStateChange(nextStateId: MainPageStateId) {
    setStateId(nextStateId);
    setSelectedTaskNodeId(null);
    setSelectionTarget("auto");
    setDetailOverride("auto");
    setAuthoringAskError(null);
    setExecutionAskError(null);
    setConfirmationError(null);
    setInputDraft("");
    setInputError(null);
    setTaskTreeCommandError(null);
    clearCommandRecoveryActions();
    setUiNotice(null);
    setSessionDialog({ mode: "idle" });
    setEventError(null);
    resolveConfirmationMutation.reset();
    answerAuthoringAskBatchMutation.reset();
    repairAuthoringStateMutation.reset();
    answerAskMutation.reset();
    deferAskMutation.reset();
    cancelAskMutation.reset();
    inputMutation.reset();
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

    setSessionDialog({
      draftName: "New session",
      error: null,
      mode: "create",
    });
  }

  function handleRenameSession(session: SessionSummary) {
    setSessionDialog({
      draftName: session.name,
      error: null,
      mode: "rename",
      session,
    });
  }

  function handleDeleteSession(session: SessionSummary) {
    setSessionDialog({
      error: null,
      mode: "delete",
      session,
    });
  }

  function handleSessionDialogDraftChange(draftName: string) {
    setSessionDialog((current) => {
      if (current.mode !== "create" && current.mode !== "rename") {
        return current;
      }

      return {
        ...current,
        draftName,
        error: null,
      };
    });
  }

  function handleSessionDialogCancel() {
    if (
      createSessionMutation.isPending ||
      renameSessionMutation.isPending ||
      deleteSessionMutation.isPending
    ) {
      return;
    }

    setSessionDialog({ mode: "idle" });
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

  function setSessionDialogError(message: string) {
    setSessionDialog((current) => {
      if (current.mode === "idle") {
        return current;
      }

      return {
        ...current,
        error: message,
      };
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

    setInputCommandError(null);
    setUiNotice(null);
    if (adapter.routeRuntimeInput !== undefined) {
      runtimeInputMutation.mutate({
        content,
        mode,
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
    isInputSubmitting: inputMutation.isPending || runtimeInputMutation.isPending,
    isPublishingTaskTree: publishTaskTreeMutation.isPending,
    isRepairingAuthoringState: repairAuthoringStateMutation.isPending,
    isRenamingSession: renameSessionMutation.isPending,
    isRetryingTask: retryTaskMutation.isPending,
    isStoppingTask: stopTaskMutation.isPending,
    isResolvingConfirmation: resolveConfirmationMutation.isPending,
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
      cancelSessionDialog: handleSessionDialogCancel,
      cancelAsk: handleCancelAsk,
      changeSessionDialogDraft: handleSessionDialogDraftChange,
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

function shouldRouteReadOnlyQuestion(content: string): boolean {
  const trimmed = content.trim();
  if (!trimmed) {
    return false;
  }

  if (trimmed.includes("?") || trimmed.includes("？")) {
    return true;
  }

  const lower = trimmed.toLowerCase();
  const englishQuestionPrefixes = [
    "what ",
    "why ",
    "how ",
    "where ",
    "when ",
    "who ",
    "which ",
    "can ",
    "could ",
    "should ",
    "is ",
    "are ",
    "do ",
    "does ",
    "did ",
  ];
  if (englishQuestionPrefixes.some((prefix) => lower.startsWith(prefix))) {
    return true;
  }

  return [
    "什么",
    "为什么",
    "为何",
    "如何",
    "怎么",
    "是否",
    "吗",
    "哪",
    "能不能",
  ].some((marker) => trimmed.includes(marker));
}

function buildRuntimeInputRouteRequest({
  content,
  mode,
  sessionId,
  snapshot,
  target,
  taskNodeId,
}: {
  content: string;
  mode: RuntimeInputRouteRequest["mode"];
  sessionId: string;
  snapshot: MainPageSnapshot | null;
  target: InputTarget;
  taskNodeId: TaskNodeId | null;
}): RuntimeInputRouteRequest {
  const activePlan = snapshot?.activePlan ?? null;
  const scopeKind =
    target === "task" && taskNodeId !== null
      ? "task"
      : target === "plan" && activePlan !== null
        ? "plan"
        : "session";

  return {
    commandId: `route-input-${Date.now()}`,
    sessionId,
    content,
    mode,
    selection: {
      scopeKind,
      planId: scopeKind === "session" ? null : activePlan?.id ?? null,
      taskNodeId: scopeKind === "task" ? taskNodeId : null,
      refs: [],
    },
    clientState: {
      activeAskId: snapshot?.activeAsk?.id ?? null,
      activeConfirmationId: snapshot?.pendingConfirmations[0]?.id ?? null,
    },
  };
}

function runtimeInputModeFor(
  content: string,
  mode: MainPageInputCommandMode,
): NonNullable<RuntimeInputRouteRequest["mode"]> {
  if (shouldRouteReadOnlyQuestion(content)) {
    return "ask";
  }

  if (mode === "generate_task_tree") {
    return "change";
  }

  if (
    mode === "append_plan_input" ||
    mode === "append_session_input" ||
    mode === "append_task_input"
  ) {
    return "guide";
  }

  return "auto";
}

function runtimeInputNotice(result: RuntimeInputRouteResult): string {
  const answer = result.inquiryResult?.answer;
  const message =
    answer === null || answer === undefined
      ? result.outcome.userMessage
      : answer.title
        ? `${answer.title}: ${answer.body}`
        : answer.body;

  return compactNotice(message);
}

function runtimeInputActivity(
  result: RuntimeInputRouteResult,
): SessionActivityItemView | null {
  return result.activity ?? result.inquiryResult?.activity ?? null;
}

function prependRuntimeActivityItem(
  items: SessionActivityItemView[],
  item: SessionActivityItemView,
): SessionActivityItemView[] {
  return [item, ...items.filter((candidate) => candidate.id !== item.id)].slice(
    0,
    20,
  );
}

function compactNotice(message: string): string {
  const maxLength = 360;
  if (message.length <= maxLength) {
    return message;
  }

  return `${message.slice(0, maxLength - 3)}...`;
}
