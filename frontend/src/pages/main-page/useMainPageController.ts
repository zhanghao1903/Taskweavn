import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import type {
  ConfirmationActionView,
  SessionSummary,
  TaskNodeId,
} from "../../shared/api/types";
import {
  createFrontendLogger,
  summarizeLoggableError,
  toLoggableError,
} from "../../shared/logging/frontendLogger";
import type {
  ConfirmationDecision,
  DetailOverride,
  EventConnectionStatus,
  InputTarget,
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

export type ConfirmationDecisionContext = {
  confirmation: ConfirmationActionView | undefined;
  decision: Exclude<ConfirmationDecision, null>;
  sessionId: string;
};

export type UnavailableNoticeContext = {
  action: string;
  sessionId: string;
};

export type MainPageController = {
  activeSessionId: string | null;
  confirmationError: string | null;
  detailOverride: DetailOverride;
  eventConnectionStatus: EventConnectionStatus;
  eventError: string | null;
  inputDraft: string;
  inputError: string | null;
  isCreatingSession: boolean;
  isDeletingSession: boolean;
  isInputSubmitting: boolean;
  isPublishingTaskTree: boolean;
  isRenamingSession: boolean;
  isResolvingConfirmation: boolean;
  isSnapshotError: boolean;
  isSnapshotPending: boolean;
  selectedTaskNodeId: TaskNodeId | null;
  snapshotData: MainPageRuntimeSnapshot | undefined;
  snapshotError: unknown;
  stateId: MainPageStateId;
  taskTreeCommandError: string | null;
  uiNotice: string | null;
  actions: {
    changeInputDraft: (draft: string) => void;
    changeState: (nextStateId: MainPageStateId) => void;
    createSession: () => void;
    deleteSession: (session: SessionSummary) => void;
    renameSession: (session: SessionSummary) => void;
    resolveConfirmation: (context: ConfirmationDecisionContext) => void;
    selectSession: (session: SessionSummary, currentSessionId: string) => void;
    selectTask: (nodeId: TaskNodeId) => void;
    showFileChanges: () => void;
    showResult: () => void;
    showUnavailableNotice: (context: UnavailableNoticeContext) => void;
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
  const [detailOverride, setDetailOverride] =
    useState<DetailOverride>("auto");
  const [confirmationError, setConfirmationError] = useState<string | null>(
    null,
  );
  const [inputDraft, setInputDraft] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [taskTreeCommandError, setTaskTreeCommandError] = useState<string | null>(
    null,
  );
  const [uiNotice, setUiNotice] = useState<string | null>(null);
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

  const resolveConfirmationMutation = useMutation({
    mutationFn: async ({
      confirmation,
      decision,
      sessionId,
    }: {
      confirmation: ConfirmationActionView;
      decision: Exclude<ConfirmationDecision, null>;
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
      setConfirmationError("Confirmation command failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Confirmation command was rejected.",
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
      setInputError("Input command failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Input command was rejected.",
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
      setTaskTreeCommandError("Publish command failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Publish command was rejected.",
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

  const createSessionMutation = useMutation({
    mutationFn: async (name: string) =>
      adapter.createSession({
        name,
      }),
    onError: () => {
      setUiNotice("New session command failed. Please retry.");
    },
    onSuccess: (result) => {
      const nextSessionId = result.sessionId ?? result.session?.id ?? null;
      if (nextSessionId === null) {
        setUiNotice("New session command did not return a session id.");
        return;
      }

      setActiveSessionId(nextSessionId);
      setUiNotice(`Created session ${result.session?.name ?? nextSessionId}.`);
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
      setUiNotice("Rename session command failed. Please retry.");
    },
    onSuccess: (result) => {
      setUiNotice(`Renamed session to ${result.session?.name ?? "new name"}.`);
      void refetchSnapshot();
    },
  });

  const deleteSessionMutation = useMutation({
    mutationFn: async (sessionId: string) => adapter.deleteSession(sessionId),
    onError: () => {
      setUiNotice("Delete session command failed. Please retry.");
    },
    onSuccess: (result) => {
      const nextSessionId = result.nextSessionId ?? null;
      setActiveSessionId(nextSessionId);
      setUiNotice("Session deleted.");
    },
  });

  useEffect(() => {
    const currentSnapshot = snapshotDataRef.current;

    if (!currentSnapshot) {
      return;
    }

    setSelectedTaskNodeId(currentSnapshot.metadata.initialSelectedTaskNodeId);
    setDetailOverride("auto");
    setConfirmationError(null);
    setInputDraft("");
    setInputError(null);
    setTaskTreeCommandError(null);
    setUiNotice(null);
    setEventError(null);
  }, [snapshotIdentity]);

  useEffect(() => {
    if (!snapshotData) {
      return undefined;
    }

    mainPageLogger.info("events.subscribe.start", {
      cursor: snapshotData.snapshot.cursor,
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
            eventId: event.eventId,
            eventType: event.eventType,
            sessionId: event.sessionId,
          });

          const nextResyncEventKey = resyncEventKey(event);
          if (
            nextResyncEventKey !== null &&
            nextResyncEventKey === lastResyncEventKeyRef.current
          ) {
            return;
          }
          lastResyncEventKeyRef.current = nextResyncEventKey;

          const action = routeMainPageEvent(event);
          if (action.kind === "ignore") {
            return;
          }

          if (action.errorMessage) {
            setEventError(action.errorMessage);
          }
          setEventConnectionStatus(action.status);
          void refetchSnapshot().finally(() => {
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
    setDetailOverride("auto");
    setConfirmationError(null);
    setInputDraft("");
    setInputError(null);
    setTaskTreeCommandError(null);
    setUiNotice(null);
    setEventError(null);
    resolveConfirmationMutation.reset();
    inputMutation.reset();
    publishTaskTreeMutation.reset();
    createSessionMutation.reset();
    renameSessionMutation.reset();
    deleteSessionMutation.reset();
  }

  function selectTask(nodeId: TaskNodeId) {
    setSelectedTaskNodeId(nodeId);
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

  function showUnavailableNotice({
    action,
    sessionId,
  }: UnavailableNoticeContext) {
    const message = `${action} is not connected in this build yet.`;
    mainPageLogger.warn("ui.action.unavailable", {
      action,
      runtimeKind: adapter.runtimeKind,
      sessionId,
    });
    setUiNotice(message);
  }

  function handleCreateSession() {
    const name = safePrompt("New session name", "New session");
    if (name === null) {
      return;
    }
    const trimmed = name.trim();
    if (!trimmed) {
      setUiNotice("Session name must not be empty.");
      return;
    }

    setUiNotice(null);
    createSessionMutation.mutate(trimmed);
  }

  function handleRenameSession(session: SessionSummary) {
    const nextName = safePrompt("Rename session", session.name);
    if (nextName === null) {
      return;
    }
    const trimmed = nextName.trim();
    if (!trimmed) {
      setUiNotice("Session name must not be empty.");
      return;
    }

    setUiNotice(null);
    renameSessionMutation.mutate({
      name: trimmed,
      sessionId: session.id,
    });
  }

  function handleDeleteSession(session: SessionSummary) {
    const confirmed = safeConfirm(
      `Delete session "${session.name}"? Its files will be archived locally.`,
    );
    if (!confirmed) {
      return;
    }

    setUiNotice(null);
    deleteSessionMutation.mutate(session.id);
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
      setTaskTreeCommandError("No draft TaskTree is available to publish.");
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

  return {
    activeSessionId,
    confirmationError,
    detailOverride,
    eventConnectionStatus,
    eventError,
    inputDraft,
    inputError,
    isCreatingSession: createSessionMutation.isPending,
    isDeletingSession: deleteSessionMutation.isPending,
    isInputSubmitting: inputMutation.isPending,
    isPublishingTaskTree: publishTaskTreeMutation.isPending,
    isRenamingSession: renameSessionMutation.isPending,
    isResolvingConfirmation: resolveConfirmationMutation.isPending,
    isSnapshotError: snapshotQuery.isError,
    isSnapshotPending: snapshotQuery.isPending,
    selectedTaskNodeId,
    snapshotData,
    snapshotError: snapshotQuery.error,
    stateId,
    taskTreeCommandError,
    uiNotice,
    actions: {
      changeInputDraft: setInputDraft,
      changeState: handleStateChange,
      createSession: handleCreateSession,
      deleteSession: handleDeleteSession,
      renameSession: handleRenameSession,
      resolveConfirmation: handleConfirmationDecision,
      selectSession: handleSessionSelect,
      selectTask,
      showFileChanges: () => setDetailOverride("fileChanges"),
      showResult: () => setDetailOverride("result"),
      showUnavailableNotice,
      submitInput: handleInputSubmit,
      publishTaskTree: handlePublishTaskTree,
    },
  };
}

function safePrompt(message: string, defaultValue: string): string | null {
  try {
    const value = globalThis.prompt?.(message, defaultValue);
    return value === undefined ? defaultValue : value;
  } catch {
    return defaultValue;
  }
}

function safeConfirm(message: string): boolean {
  try {
    return globalThis.confirm?.(message) ?? false;
  } catch {
    return false;
  }
}
