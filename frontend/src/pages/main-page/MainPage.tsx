import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import type {
  ConfirmationActionView,
  MainPageSnapshot,
  SessionMessageView,
  TaskNodeCardView,
  TaskNodeId,
} from "../../shared/api/types";
import type { BadgeTone } from "../../shared/components";
import { Badge, Button, Panel, Text } from "../../shared/components";
import {
  createFrontendLogger,
  summarizeLoggableError,
  toLoggableError,
} from "../../shared/logging/frontendLogger";
import { ContextInputPanel } from "./ContextInputPanel";
import { NO_SESSION_AVAILABLE_MESSAGE } from "./httpMainPageAdapter";
import { MainPageDetailPanel } from "./MainPageDetailPanel";
import { SessionMessagePanel } from "./SessionMessagePanel";
import { TaskTreePanel } from "./TaskTreePanel";
import { buildTaskScopedProjection } from "./mainPageSelectors";
import type {
  ConfirmationDecision,
  DetailOverride,
  EventConnectionStatus,
  InputTarget,
} from "./mainPageUiTypes";
import {
  defaultMainPageStateId,
  listMainPageStateOptions,
  mainPageMockAdapter,
} from "./mockPlatoApi";
import type { MainPageStateId } from "./mockPlatoApi";
import type {
  MainPageAdapter,
  MainPageStateMetadata,
} from "./runtime/adapter";
import {
  mainPageSnapshotIdentity,
  mainPageSnapshotQueryKey,
} from "./runtime/adapter";
import { handleCommandResponse } from "./runtime/commandRefresh";
import { resyncEventKey, routeMainPageEvent } from "./runtime/eventRouter";
import styles from "./MainPage.module.css";

const eventStatusLabel: Record<EventConnectionStatus, string> = {
  connected: "Events live",
  disconnected: "Events offline",
  resyncing: "Resyncing",
};

const mainPageLogger = createFrontendLogger("main-page");

function eventStatusTone(status: EventConnectionStatus): BadgeTone {
  if (status === "resyncing") {
    return "warning";
  }

  if (status === "connected") {
    return "success";
  }

  return "neutral";
}

const stateOptions = listMainPageStateOptions();

export type MainPageProps = {
  adapter?: MainPageAdapter;
  initialStateId?: MainPageStateId;
};

export function MainPage({
  adapter = mainPageMockAdapter,
  initialStateId = defaultMainPageStateId,
}: MainPageProps = {}) {
  const [stateId, setStateId] = useState<MainPageStateId>(
    initialStateId,
  );
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
      hasTaskTree,
      sessionId,
      target,
      taskNodeId,
    }: {
      content: string;
      hasTaskTree: boolean;
      sessionId: string;
      target: InputTarget;
      taskNodeId: TaskNodeId | null;
    }) => {
      const commandId = `append-${target}-${Date.now()}`;

      if (target === "task" && taskNodeId) {
        return adapter.appendTaskInput(sessionId, taskNodeId, {
          commandId,
          sessionId,
          payload: {
            content,
            mode: "guidance",
          },
        });
      }

      if (!hasTaskTree) {
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

  if (snapshotQuery.isPending) {
    return (
      <MainPageStatusFrame
        stateId={stateId}
        onStateChange={handleStateChange}
        showStatePicker={adapter.showStatePicker}
        statusLabel="Loading snapshot"
        statusTone="blue"
        title="Loading session snapshot"
        body="Plato is preparing the current Project, Workflow, Session, TaskTree, and message projection."
      />
    );
  }

  if (snapshotQuery.isError || !snapshotData) {
    const errorSummary = snapshotQuery.isError
      ? snapshotErrorSummary(snapshotQuery.error)
      : "Snapshot data is empty.";
    const noSessionAvailable =
      snapshotQuery.error instanceof Error &&
      snapshotQuery.error.message === NO_SESSION_AVAILABLE_MESSAGE;

    return (
      <MainPageStatusFrame
        action={
          noSessionAvailable
            ? {
                disabled: createSessionMutation.isPending,
                label: createSessionMutation.isPending
                  ? "Creating session"
                  : "New session",
                onClick: handleCreateSession,
              }
            : undefined
        }
        stateId={stateId}
        onStateChange={handleStateChange}
        showStatePicker={adapter.showStatePicker}
        statusLabel={noSessionAvailable ? "No sessions" : "Snapshot error"}
        statusTone={noSessionAvailable ? "neutral" : "danger"}
        title={
          noSessionAvailable
            ? "Create your first session"
            : "Unable to load session snapshot"
        }
        body={
          noSessionAvailable
            ? "This workspace has no sessions yet. Create one when you are ready to start."
            : `The UI could not load the session projection. ${errorSummary}`
        }
      />
    );
  }

  const { metadata, snapshot } = snapshotData;
  const taskNodes = snapshot.taskTree?.nodes ?? [];
  const effectiveSelectedTaskNodeId =
    selectedTaskNodeId ?? metadata.initialSelectedTaskNodeId;
  const activeConfirmation =
    snapshot.pendingConfirmations.find(
      (confirmation) => confirmation.taskNodeId === effectiveSelectedTaskNodeId,
    ) ?? snapshot.pendingConfirmations[0];
  const hasConfirmationFocus =
    metadata.detail.mode === "confirmation" &&
    effectiveSelectedTaskNodeId === metadata.initialSelectedTaskNodeId;
  const wantsResultView =
    detailOverride === "result" ||
    (detailOverride === "auto" && metadata.detail.mode === "result");
  const wantsFileChangeView =
    detailOverride === "fileChanges" ||
    (detailOverride === "auto" && metadata.detail.mode === "fileChanges");
  const displayTopStatus = topStatusFor(metadata);
  const displayMessages = messagesFor(snapshot);
  const scopedProjection = buildTaskScopedProjection({
    fileChangeSummary: snapshot.fileChangeSummary,
    messages: displayMessages,
    nodes: taskNodes,
    result: snapshot.result,
    selectedTaskNodeId: effectiveSelectedTaskNodeId,
  });
  const {
    fileChangeSummary: visibleFileChangeSummary,
    messages: scopedMessages,
    result: visibleResult,
    selectedTask,
  } = scopedProjection;
  const hasResultView = wantsResultView && visibleResult !== null;
  const hasFileChangeView =
    wantsFileChangeView && visibleFileChangeSummary !== null;
  const inputScope = inputScopeFor(
    metadata,
    selectedTask,
    hasConfirmationFocus,
    detailOverride,
  );
  const inputTarget: InputTarget = selectedTask ? "task" : "session";
  const canPublishTaskTree = snapshot.taskTree?.status === "draft";

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

  function showUnavailableNotice(action: string) {
    const message = `${action} is not connected in this build yet.`;
    mainPageLogger.warn("ui.action.unavailable", {
      action,
      runtimeKind: adapter.runtimeKind,
      sessionId: snapshot.session.id,
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

  function handleRenameSession() {
    const nextName = safePrompt("Rename session", snapshot.session.name);
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
      sessionId: snapshot.session.id,
    });
  }

  function handleDeleteSession() {
    const confirmed = safeConfirm(
      `Delete session "${snapshot.session.name}"? Its files will be archived locally.`,
    );
    if (!confirmed) {
      return;
    }

    setUiNotice(null);
    deleteSessionMutation.mutate(snapshot.session.id);
  }

  function handleInputSubmit() {
    const content = inputDraft.trim();

    if (!content) {
      return;
    }

    setInputError(null);
    setUiNotice(null);
    inputMutation.mutate({
      content,
      hasTaskTree: snapshot.taskTree !== null,
      sessionId: snapshot.session.id,
      target: inputTarget,
      taskNodeId: selectedTask?.id ?? null,
    });
  }

  function handlePublishTaskTree() {
    if (!snapshot.taskTree) {
      setTaskTreeCommandError("No draft TaskTree is available to publish.");
      return;
    }

    setTaskTreeCommandError(null);
    setUiNotice(null);
    publishTaskTreeMutation.mutate({
      sessionId: snapshot.session.id,
      taskTreeId: snapshot.taskTree.id,
    });
  }

  function handleConfirmationDecision(
    decision: Exclude<ConfirmationDecision, null>,
  ) {
    if (!activeConfirmation) {
      setConfirmationError("No pending confirmation is available.");
      return;
    }

    setConfirmationError(null);
    setUiNotice(null);
    resolveConfirmationMutation.mutate({
      confirmation: activeConfirmation,
      decision,
      sessionId: snapshot.session.id,
    });
  }

  return (
    <main className={styles.page}>
      <header className={styles.topBar}>
        <div className={styles.brand}>柏拉图 Plato</div>
        <div className={styles.contextStack}>
          <span>{snapshot.project.name}</span>
          <span>{snapshot.workflow.name}</span>
          <span>{snapshot.session.name}</span>
        </div>
        <Badge tone={displayTopStatus.tone}>{displayTopStatus.label}</Badge>
        <Badge tone={eventStatusTone(eventConnectionStatus)}>
          {eventStatusLabel[eventConnectionStatus]}
        </Badge>
        {adapter.showStatePicker ? (
          <StatePicker stateId={stateId} onStateChange={handleStateChange} />
        ) : null}
      </header>

      <Panel
        as="aside"
        className={styles.sidebar}
        aria-label="Workflow sessions"
      >
        <div className={styles.sidebarHeader}>
          <Text as="span" variant="label">
            Workflow
          </Text>
          <Button
            disabled={createSessionMutation.isPending}
            onClick={handleCreateSession}
            size="sm"
          >
            {createSessionMutation.isPending ? "Creating" : "New"}
          </Button>
        </div>
        <Text as="div" variant="eyebrow">
          Sessions
        </Text>
        {snapshot.sessions.map((session) => (
          <button
            className={
              session.id === snapshot.session.id
                ? styles.activeNavItem
                : styles.navItem
            }
            key={session.id}
            onClick={() =>
              session.id === snapshot.session.id
                ? setUiNotice("This session is already open.")
                : setActiveSessionId(session.id)
            }
            type="button"
          >
            {session.name}
          </button>
        ))}
        <div className={styles.sidebarActions}>
          <Button
            disabled={renameSessionMutation.isPending}
            onClick={handleRenameSession}
            size="sm"
            variant="ghost"
          >
            Rename
          </Button>
          <Button
            disabled={deleteSessionMutation.isPending}
            onClick={handleDeleteSession}
            size="sm"
            variant="danger"
          >
            Delete
          </Button>
        </div>
      </Panel>

      <Panel
        as="section"
        className={styles.workspace}
        aria-label="Task workspace"
      >
        <div className={styles.sectionHeader}>
          <div>
            <Text variant="eyebrow">Session workspace</Text>
            <Text as="h1" variant="heading">
              {snapshot.taskTree?.title ?? "Start a new session"}
            </Text>
            {taskTreeCommandError ? (
              <Text variant="muted">{taskTreeCommandError}</Text>
            ) : null}
            {eventError ? <Text variant="muted">{eventError}</Text> : null}
            {uiNotice ? <Text variant="muted">{uiNotice}</Text> : null}
          </div>
          <div className={styles.actionRow}>
            {canPublishTaskTree ? (
              <Button
                disabled={publishTaskTreeMutation.isPending}
                onClick={handlePublishTaskTree}
              >
                {publishTaskTreeMutation.isPending
                  ? "Publishing"
                  : "Publish TaskTree"}
              </Button>
            ) : null}
            <Button onClick={() => showUnavailableNotice("Audit view")}>
              View audit
            </Button>
          </div>
        </div>

        <div className={styles.workGrid}>
          <TaskTreePanel
            confirmationDecision={null}
            onSelectTask={selectTask}
            selectedTaskNodeId={effectiveSelectedTaskNodeId}
            taskTree={snapshot.taskTree}
          />

          <SessionMessagePanel
            isMessageScoped={scopedProjection.isMessageScoped}
            messages={scopedMessages}
            selectedTask={selectedTask}
            totalMessageCount={scopedProjection.totalMessageCount}
            visibleMessageCount={scopedProjection.visibleMessageCount}
          />
        </div>
      </Panel>

      <MainPageDetailPanel
        activeConfirmation={activeConfirmation}
        commandError={confirmationError}
        confirmationDecision={null}
        fileChangeSummary={visibleFileChangeSummary}
        hasConfirmationFocus={hasConfirmationFocus}
        hasFileChangeView={hasFileChangeView}
        hasResultView={hasResultView}
        header={detailHeaderFor(
          metadata,
          selectedTask,
          hasConfirmationFocus,
          hasResultView,
          hasFileChangeView,
        )}
        isResolvingConfirmation={resolveConfirmationMutation.isPending}
        onConfirmationDecision={handleConfirmationDecision}
        onShowFileChanges={() => setDetailOverride("fileChanges")}
        onShowResult={() => setDetailOverride("result")}
        result={visibleResult}
        selectedTask={selectedTask}
      />

      <ContextInputPanel
        disabled={inputMutation.isPending}
        draft={inputDraft}
        error={inputError}
        inputScope={inputScope}
        onDraftChange={setInputDraft}
        onSubmit={handleInputSubmit}
      />
    </main>
  );
}

type StatePickerProps = {
  onStateChange: (stateId: MainPageStateId) => void;
  stateId: MainPageStateId;
};

function StatePicker({ onStateChange, stateId }: StatePickerProps) {
  return (
    <label className={styles.statePicker}>
      <span>State</span>
      <select
        value={stateId}
        onChange={(event) =>
          onStateChange(event.currentTarget.value as MainPageStateId)
        }
      >
        {stateOptions.map((state) => (
          <option key={state.id} value={state.id}>
            {state.label}
          </option>
        ))}
      </select>
    </label>
  );
}

type MainPageStatusFrameProps = {
  action?: {
    disabled?: boolean;
    label: string;
    onClick: () => void;
  };
  body: string;
  onStateChange: (stateId: MainPageStateId) => void;
  showStatePicker: boolean;
  stateId: MainPageStateId;
  statusLabel: string;
  statusTone: BadgeTone;
  title: string;
};

function MainPageStatusFrame({
  action,
  body,
  onStateChange,
  showStatePicker,
  stateId,
  statusLabel,
  statusTone,
  title,
}: MainPageStatusFrameProps) {
  return (
    <main className={styles.page}>
      <header className={styles.topBar}>
        <div className={styles.brand}>柏拉图 Plato</div>
        <div className={styles.contextStack}>
          <span>Plato workspace</span>
          <span>Snapshot boundary</span>
          <span>Session projection</span>
        </div>
        <Badge tone={statusTone}>{statusLabel}</Badge>
        {showStatePicker ? (
          <StatePicker stateId={stateId} onStateChange={onStateChange} />
        ) : null}
      </header>

      <Panel
        as="section"
        className={styles.workspace}
        aria-label="Task workspace"
      >
        <div className={styles.emptyState}>
          <Text as="h1" variant="heading">
            {title}
          </Text>
          <Text variant="muted">{body}</Text>
          {action ? (
            <Button
              disabled={action.disabled}
              onClick={action.onClick}
              variant="primary"
            >
              {action.label}
            </Button>
          ) : null}
        </div>
      </Panel>
    </main>
  );
}

function topStatusFor(
  metadata: MainPageStateMetadata,
): { label: string; tone: BadgeTone } {
  return { label: metadata.topStatus, tone: metadata.topStatusTone };
}

function messagesFor(snapshot: MainPageSnapshot): SessionMessageView[] {
  return snapshot.messages;
}

function snapshotErrorSummary(error: unknown): string {
  if (error instanceof Error) {
    return `Error: ${error.message}`;
  }

  return "Check the browser console for the captured error payload.";
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

function detailHeaderFor(
  metadata: MainPageStateMetadata,
  selectedTask: TaskNodeCardView | undefined,
  hasConfirmationFocus: boolean,
  hasResultView: boolean,
  hasFileChangeView: boolean,
) {
  if (hasConfirmationFocus || hasResultView || hasFileChangeView) {
    return metadata.detail;
  }

  if (selectedTask) {
    return {
      eyebrow: "TaskNode",
      title: selectedTask.title,
      body: selectedTask.summary,
    };
  }

  return metadata.detail;
}

function inputScopeFor(
  metadata: MainPageStateMetadata,
  selectedTask: TaskNodeCardView | undefined,
  hasConfirmationFocus: boolean,
  detailOverride: DetailOverride,
) {
  if (hasConfirmationFocus || detailOverride !== "auto") {
    return metadata.inputScope;
  }

  if (selectedTask) {
    return {
      label: `Scope: selected task / ${selectedTask.title}`,
      placeholder: "Add guidance that only applies to this TaskNode.",
    };
  }

  return metadata.inputScope;
}
