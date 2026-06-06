import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import type { AnswerAuthoringAskItemPayload } from "../../shared/api/platoApi";
import type {
  ConfirmationActionView,
  AskId,
  SessionSummary,
  TaskNodeId,
} from "../../shared/api/types";
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
  authoringAskError: string | null;
  confirmationError: string | null;
  detailOverride: DetailOverride;
  eventConnectionStatus: EventConnectionStatus;
  eventError: string | null;
  inputDraft: string;
  inputError: string | null;
  isCreatingSession: boolean;
  isDeletingSession: boolean;
  isAnsweringAuthoringAsk: boolean;
  executionAskError: string | null;
  isAnsweringAsk: boolean;
  isCancellingAsk: boolean;
  isDeferringAsk: boolean;
  isInputSubmitting: boolean;
  isPublishingTaskTree: boolean;
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
  uiNotice: string | null;
  actions: {
    cancelSessionDialog: () => void;
    changeSessionDialogDraft: (draftName: string) => void;
    changeInputDraft: (draft: string) => void;
    changeState: (nextStateId: MainPageStateId) => void;
    createSession: () => void;
    deleteSession: (session: SessionSummary) => void;
    answerAuthoringAskBatch: (context: AnswerAuthoringAskBatchContext) => void;
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
};

export function useMainPageController({
  adapter,
  initialStateId,
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
  const [authoringAskError, setAuthoringAskError] = useState<string | null>(
    null,
  );
  const [executionAskError, setExecutionAskError] = useState<string | null>(
    null,
  );
  const [inputDraft, setInputDraft] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [taskTreeCommandError, setTaskTreeCommandError] = useState<string | null>(
    null,
  );
  const [uiNotice, setUiNotice] = useState<string | null>(null);
  const [sessionDialog, setSessionDialog] = useState<SessionLifecycleDialog>({
    mode: "idle",
  });
  const [eventError, setEventError] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(
    adapter.sessionId,
  );
  const [eventConnectionStatus, setEventConnectionStatus] =
    useState<EventConnectionStatus>("disconnected");

  const snapshotQuery = useQuery({
    queryKey: mainPageSnapshotQueryKey(adapter, stateId, activeSessionId),
    queryFn: () => adapter.loadSnapshot(stateId, activeSessionId),
  });
  const snapshotData = snapshotQuery.data;
  const snapshotDataRef = useRef(snapshotData);
  const lastEventCursorRef = useRef<string | null>(null);
  const lastResyncEventKeyRef = useRef<string | null>(null);
  snapshotDataRef.current = snapshotData;
  const snapshotIdentity = snapshotData
    ? mainPageSnapshotIdentity(adapter, stateId, snapshotData, activeSessionId)
    : null;
  const refetchSnapshot = snapshotQuery.refetch;

  useEffect(() => {
    if (!snapshotData || activeSessionId !== null) {
      return;
    }
    setActiveSessionId(snapshotData.snapshot.session.id);
  }, [activeSessionId, snapshotData]);

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
      }),
    onError: () => {
      setConfirmationError("Confirmation failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Confirmation was rejected.",
      );

      if (result.errorMessage) {
        setConfirmationError(result.errorMessage);
        return;
      }

      setConfirmationError(null);
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
      }),
    onError: () => {
      setAuthoringAskError("Answer submission failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Answer submission was rejected.",
      );

      if (result.errorMessage) {
        setAuthoringAskError(result.errorMessage);
        return;
      }

      setAuthoringAskError(null);
      setUiNotice("Authoring answers submitted.");
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
      }),
    onError: () => {
      setExecutionAskError("Answer submission failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Answer submission was rejected.",
      );

      if (result.errorMessage) {
        setExecutionAskError(result.errorMessage);
        if (result.shouldRefetch) {
          void refetchSnapshot();
        }
        return;
      }

      setExecutionAskError(null);
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
      }),
    onError: () => {
      setExecutionAskError("Defer failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Defer was rejected.",
      );

      if (result.errorMessage) {
        setExecutionAskError(result.errorMessage);
        return;
      }

      setExecutionAskError(null);
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
      }),
    onError: () => {
      setExecutionAskError("Cancel failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Cancel was rejected.",
      );

      if (result.errorMessage) {
        setExecutionAskError(result.errorMessage);
        return;
      }

      setExecutionAskError(null);
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
        });
      }

      if (mode === "generate_task_tree") {
        return adapter.generateTaskTree({
          commandId: `generate-task-tree-${Date.now()}`,
          sessionId,
          payload: {
            prompt: content,
          },
        });
      }

      return adapter.appendSessionInput({
        commandId,
        sessionId,
        payload: {
          content,
          mode: "global_guidance",
        },
      });
    },
    onError: () => {
      setInputError("Input submission failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Input submission was rejected.",
      );

      if (result.errorMessage) {
        setInputError(result.errorMessage);
        return;
      }

      setInputError(null);
      setInputDraft("");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
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
      }),
    onError: () => {
      setTaskTreeCommandError("Publish failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Publish was rejected.",
      );

      if (result.errorMessage) {
        setTaskTreeCommandError(result.errorMessage);
        return;
      }

      setTaskTreeCommandError(null);
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
      }),
    onError: () => {
      setTaskTreeCommandError("Retry failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Retry was rejected.",
      );

      if (result.errorMessage) {
        setTaskTreeCommandError(result.errorMessage);
        return;
      }

      setTaskTreeCommandError(null);
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
      });
    },
    onError: (error) => {
      mainPageLogger.error("command.stop.failed", {
        error: toLoggableError(error),
      });
      setTaskTreeCommandError("Stop failed. Please retry.");
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
        setTaskTreeCommandError(result.errorMessage);
        return;
      }

      setTaskTreeCommandError(null);
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
    mutationFn: async (name: string) =>
      adapter.createSession({
        name,
      }),
    onError: () => {
      setSessionDialogError("Create session failed. Please retry.");
    },
    onSuccess: (result) => {
      const nextSessionId = result.sessionId ?? result.session?.id ?? null;
      if (nextSessionId === null) {
        setSessionDialogError("Created session was unavailable. Please retry.");
        return;
      }

      setActiveSessionId(nextSessionId);
      setUiNotice(`Created session ${result.session?.name ?? nextSessionId}.`);
      setSessionDialog({ mode: "idle" });
    },
  });

  const renameSessionMutation = useMutation({
    mutationFn: async ({
      name,
      sessionId,
    }: {
      name: string;
      sessionId: string;
    }) =>
      adapter.renameSession({
        name,
        sessionId,
      }),
    onError: () => {
      setSessionDialogError("Rename session failed. Please retry.");
    },
    onSuccess: (result) => {
      setUiNotice(`Renamed session to ${result.session?.name ?? "new name"}.`);
      setSessionDialog({ mode: "idle" });
      void refetchSnapshot();
    },
  });

  const deleteSessionMutation = useMutation({
    mutationFn: async (sessionId: string) => adapter.deleteSession(sessionId),
    onError: () => {
      setSessionDialogError("Delete session failed. Please retry.");
    },
    onSuccess: (result) => {
      const nextSessionId = result.nextSessionId ?? null;
      setActiveSessionId(nextSessionId);
      setUiNotice("Session deleted.");
      setSessionDialog({ mode: "idle" });
    },
  });

  useEffect(() => {
    const currentSnapshot = snapshotDataRef.current;

    if (!currentSnapshot) {
      return;
    }

    setSelectedTaskNodeId(currentSnapshot.metadata.initialSelectedTaskNodeId);
    setSelectionTarget("auto");
    setDetailOverride("auto");
    setAuthoringAskError(null);
    setExecutionAskError(null);
    setConfirmationError(null);
    setInputDraft("");
    setInputError(null);
    setTaskTreeCommandError(null);
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
  }, [adapter, refetchSnapshot, snapshotData]);

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
    setUiNotice(null);
    setSessionDialog({ mode: "idle" });
    setEventError(null);
    resolveConfirmationMutation.reset();
    answerAuthoringAskBatchMutation.reset();
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
    if (session.id === currentSessionId) {
      setUiNotice("This session is already open.");
      return;
    }

    setActiveSessionId(session.id);
  }

  function handleCreateSession() {
    if (!snapshotDataRef.current) {
      createSessionMutation.mutate("New session");
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
      deleteSessionMutation.mutate(sessionDialog.session.id);
      return;
    }

    const trimmed = sessionDialog.draftName.trim();
    if (!trimmed) {
      setSessionDialogError("Session name must not be empty.");
      return;
    }

    setUiNotice(null);

    if (sessionDialog.mode === "create") {
      createSessionMutation.mutate(trimmed);
      return;
    }

    renameSessionMutation.mutate({
      name: trimmed,
      sessionId: sessionDialog.session.id,
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

    setInputError(null);
    setUiNotice(null);
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
      setTaskTreeCommandError("No draft task plan is available to publish.");
      return;
    }

    setTaskTreeCommandError(null);
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
      setConfirmationError("No pending confirmation is available.");
      return;
    }

    setConfirmationError(null);
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
      setAuthoringAskError("Answer at least one authoring question.");
      return;
    }

    setAuthoringAskError(null);
    setUiNotice(null);
    answerAuthoringAskBatchMutation.mutate({
      answers,
      rawTaskId,
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
      setExecutionAskError("Answer the question before submitting.");
      return;
    }

    setExecutionAskError(null);
    setUiNotice(null);
    answerAskMutation.mutate({
      askId,
      selectedOptionIds,
      sessionId,
      text,
    });
  }

  function handleDeferAsk({ askId, reason, sessionId }: DeferExecutionAskContext) {
    setExecutionAskError(null);
    setUiNotice(null);
    deferAskMutation.mutate({
      askId,
      reason,
      sessionId,
    });
  }

  function handleCancelAsk({ askId, reason, sessionId }: CancelExecutionAskContext) {
    setExecutionAskError(null);
    setUiNotice(null);
    cancelAskMutation.mutate({
      askId,
      reason,
      sessionId,
    });
  }

  function handleRetryTask({ sessionId, taskNodeId }: RetryTaskContext) {
    setTaskTreeCommandError(null);
    setUiNotice(null);
    retryTaskMutation.mutate({
      sessionId,
      taskNodeId,
    });
  }

  function handleStopTask({ sessionId, taskNodeId }: StopTaskContext) {
    setTaskTreeCommandError(null);
    setUiNotice(null);
    stopTaskMutation.mutate({
      sessionId,
      taskNodeId,
    });
  }

  return {
    activeSessionId,
    authoringAskError,
    confirmationError,
    detailOverride,
    eventConnectionStatus,
    eventError,
    inputDraft,
    inputError,
    isCreatingSession: createSessionMutation.isPending,
    isDeletingSession: deleteSessionMutation.isPending,
    isAnsweringAuthoringAsk: answerAuthoringAskBatchMutation.isPending,
    executionAskError,
    isAnsweringAsk: answerAskMutation.isPending,
    isCancellingAsk: cancelAskMutation.isPending,
    isDeferringAsk: deferAskMutation.isPending,
    isInputSubmitting: inputMutation.isPending,
    isPublishingTaskTree: publishTaskTreeMutation.isPending,
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
    uiNotice,
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
