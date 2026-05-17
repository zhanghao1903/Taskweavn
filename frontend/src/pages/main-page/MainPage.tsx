import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import type {
  ConfirmationActionView,
  MainPageSnapshot,
  MessageKind,
  SessionMessageView,
  TaskNodeCardView,
  TaskNodeId,
  UiEvent,
} from "../../shared/api/types";
import type { BadgeTone } from "../../shared/components";
import { Badge, Button, Panel, Text } from "../../shared/components";
import { ContextInputPanel } from "./ContextInputPanel";
import { MainPageDetailPanel } from "./MainPageDetailPanel";
import { SessionMessagePanel } from "./SessionMessagePanel";
import { TaskTreePanel } from "./TaskTreePanel";
import { confirmationResolutionText } from "./mainPageCopy";
import { buildTaskScopedProjection } from "./mainPageSelectors";
import type {
  ConfirmationDecision,
  DetailOverride,
  EventConnectionStatus,
  InputTarget,
  LocalInputMessage,
} from "./mainPageUiTypes";
import {
  defaultMainPageStateId,
  listMainPageStateOptions,
  mainPageMockAdapter,
} from "./mockPlatoApi";
import type {
  MainPageAdapter,
  MainPageStateId,
  MainPageStateMetadata,
} from "./mockPlatoApi";
import styles from "./MainPage.module.css";

const eventStatusLabel: Record<EventConnectionStatus, string> = {
  connected: "Events live",
  disconnected: "Events offline",
  resyncing: "Resyncing",
};

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
  const [confirmationDecision, setConfirmationDecision] =
    useState<ConfirmationDecision>(null);
  const [confirmationError, setConfirmationError] = useState<string | null>(
    null,
  );
  const [inputDraft, setInputDraft] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [localInputMessage, setLocalInputMessage] =
    useState<LocalInputMessage | null>(null);
  const [localEventMessages, setLocalEventMessages] = useState<
    SessionMessageView[]
  >([]);
  const [eventConnectionStatus, setEventConnectionStatus] =
    useState<EventConnectionStatus>("disconnected");

  const snapshotQuery = useQuery({
    queryKey: ["main-page-snapshot", stateId],
    queryFn: () => adapter.loadSnapshot(stateId),
  });
  const snapshotData = snapshotQuery.data;
  const refetchSnapshot = snapshotQuery.refetch;
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
    onSuccess: (response, variables) => {
      if (!response.ok || response.result?.status !== "accepted") {
        setConfirmationError(
          response.error?.message ?? "Confirmation command was rejected.",
        );
        return;
      }

      setConfirmationError(null);
      setConfirmationDecision(variables.decision);
    },
  });
  const inputMutation = useMutation({
    mutationFn: async ({
      content,
      sessionId,
      target,
      taskNodeId,
    }: {
      content: string;
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
    onSuccess: (response, variables) => {
      if (!response.ok || response.result?.status !== "accepted") {
        setInputError(response.error?.message ?? "Input command was rejected.");
        return;
      }

      setInputError(null);
      setLocalInputMessage({
        content: variables.content,
        createdAt: new Date().toISOString(),
        target: variables.target,
        taskNodeId: variables.taskNodeId,
      });
      setInputDraft("");
    },
  });

  useEffect(() => {
    if (!snapshotData) {
      return;
    }

    setSelectedTaskNodeId(snapshotData.metadata.initialSelectedTaskNodeId);
    setDetailOverride("auto");
    setConfirmationDecision(null);
    setConfirmationError(null);
    setInputDraft("");
    setInputError(null);
    setLocalInputMessage(null);
    setLocalEventMessages([]);
  }, [snapshotData]);

  useEffect(() => {
    if (!snapshotData) {
      return undefined;
    }

    let active = true;
    setEventConnectionStatus("connected");

    const unsubscribe = adapter.subscribeSessionEvents(
      snapshotData.snapshot.session.id,
      snapshotData.snapshot.cursor,
      (event) => {
        if (event.eventType === "message.appended") {
          const message = messageFromEvent(
            event,
            snapshotData.snapshot.session.id,
          );

          if (message) {
            setLocalEventMessages((messages) => [...messages, message]);
          }

          return;
        }

        if (event.eventType === "session.resync_required") {
          setEventConnectionStatus("resyncing");
          void refetchSnapshot().finally(() => {
            if (active) {
              setEventConnectionStatus("connected");
            }
          });
        }
      },
    );

    return () => {
      active = false;
      unsubscribe();
    };
  }, [adapter, refetchSnapshot, snapshotData]);

  if (snapshotQuery.isPending) {
    return (
      <MainPageStatusFrame
        stateId={stateId}
        onStateChange={handleStateChange}
        statusLabel="Loading snapshot"
        statusTone="blue"
        title="Loading session snapshot"
        body="Plato is preparing the current Project, Workflow, Session, TaskTree, and message projection."
      />
    );
  }

  if (snapshotQuery.isError || !snapshotData) {
    return (
      <MainPageStatusFrame
        stateId={stateId}
        onStateChange={handleStateChange}
        statusLabel="Snapshot error"
        statusTone="danger"
        title="Unable to load session snapshot"
        body="The UI could not load the session projection. Keep the local draft state intact and retry the snapshot query."
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
    effectiveSelectedTaskNodeId === metadata.initialSelectedTaskNodeId &&
    confirmationDecision === null;
  const wantsResultView =
    detailOverride === "result" ||
    (detailOverride === "auto" && metadata.detail.mode === "result");
  const wantsFileChangeView =
    detailOverride === "fileChanges" ||
    (detailOverride === "auto" && metadata.detail.mode === "fileChanges");
  const displayTopStatus = topStatusFor(metadata, confirmationDecision);
  const displayMessages = messagesFor(
    snapshot,
    metadata,
    confirmationDecision,
    localInputMessage,
    localEventMessages,
  );
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

  function handleStateChange(nextStateId: MainPageStateId) {
    setStateId(nextStateId);
    setSelectedTaskNodeId(null);
    setDetailOverride("auto");
    setConfirmationDecision(null);
    setConfirmationError(null);
    setInputDraft("");
    setInputError(null);
    setLocalInputMessage(null);
    setLocalEventMessages([]);
    resolveConfirmationMutation.reset();
    inputMutation.reset();
  }

  function selectTask(nodeId: TaskNodeId) {
    setSelectedTaskNodeId(nodeId);
    setDetailOverride("auto");
  }

  function handleInputSubmit() {
    const content = inputDraft.trim();

    if (!content) {
      return;
    }

    setInputError(null);
    inputMutation.mutate({
      content,
      sessionId: snapshot.session.id,
      target: inputTarget,
      taskNodeId: selectedTask?.id ?? null,
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
        <StatePicker stateId={stateId} onStateChange={handleStateChange} />
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
          <Button size="sm">New</Button>
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
            type="button"
          >
            {session.name}
          </button>
        ))}
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
          </div>
          <Button>View audit</Button>
        </div>

        <div className={styles.workGrid}>
          <TaskTreePanel
            confirmationDecision={confirmationDecision}
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
        confirmationDecision={confirmationDecision}
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
  body: string;
  onStateChange: (stateId: MainPageStateId) => void;
  stateId: MainPageStateId;
  statusLabel: string;
  statusTone: BadgeTone;
  title: string;
};

function MainPageStatusFrame({
  body,
  onStateChange,
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
        <StatePicker stateId={stateId} onStateChange={onStateChange} />
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
        </div>
      </Panel>
    </main>
  );
}

function topStatusFor(
  metadata: MainPageStateMetadata,
  decision: ConfirmationDecision,
): { label: string; tone: BadgeTone } {
  if (decision === "confirmed") {
    return { label: "Confirmed", tone: "success" };
  }

  if (decision === "revise") {
    return { label: "Revision requested", tone: "warning" };
  }

  if (decision === "skipped") {
    return { label: "Skipped", tone: "danger" };
  }

  return { label: metadata.topStatus, tone: metadata.topStatusTone };
}

function messagesFor(
  snapshot: MainPageSnapshot,
  metadata: MainPageStateMetadata,
  decision: ConfirmationDecision,
  localInputMessage: LocalInputMessage | null,
  localEventMessages: SessionMessageView[],
): SessionMessageView[] {
  const messages = [...snapshot.messages];

  if (decision !== null) {
    messages.push({
      id: `message-confirmation-${decision}`,
      sessionId: snapshot.session.id,
      taskNodeId: metadata.initialSelectedTaskNodeId,
      kind: "response" as const,
      title: "User decision captured",
      body: confirmationResolutionText[decision],
      createdAt: new Date().toISOString(),
    });
  }

  if (localInputMessage) {
    messages.push({
      id: `message-input-${localInputMessage.createdAt}`,
      sessionId: snapshot.session.id,
      taskNodeId: localInputMessage.taskNodeId,
      kind: "response" as const,
      title:
        localInputMessage.target === "task"
          ? "Task guidance captured"
          : "Session guidance captured",
      body: localInputMessage.content,
      createdAt: localInputMessage.createdAt,
    });
  }

  messages.push(...localEventMessages);

  return messages;
}

function messageFromEvent(
  event: UiEvent,
  fallbackSessionId: string,
): SessionMessageView | null {
  if (event.eventType !== "message.appended") {
    return null;
  }

  return {
    id: event.messageIds[0] ?? event.eventId,
    sessionId: event.sessionId || fallbackSessionId,
    taskNodeId: stringPayload(event.payload.taskNodeId),
    kind: messageKindPayload(event.payload.kind),
    title: stringPayload(event.payload.title) ?? "Session event received",
    body:
      stringPayload(event.payload.body) ??
      "A session message was appended by the event stream.",
    createdAt: event.createdAt,
    relatedCommandId: event.commandId ?? null,
  };
}

function messageKindPayload(value: unknown): MessageKind {
  if (
    value === "informational" ||
    value === "actionable" ||
    value === "response" ||
    value === "error"
  ) {
    return value;
  }

  return "informational";
}

function stringPayload(value: unknown): string | null {
  return typeof value === "string" ? value : null;
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
