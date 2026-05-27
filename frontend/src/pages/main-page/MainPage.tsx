import type {
  MainPageSnapshot,
  SessionMessageView,
  TaskNodeCardView,
} from "../../shared/api/types";
import type { BadgeTone } from "../../shared/components";
import { Badge, Button, Panel, Text } from "../../shared/components";
import { ContextInputPanel } from "./ContextInputPanel";
import { NO_SESSION_AVAILABLE_MESSAGE } from "./httpMainPageAdapter";
import { MainPageDetailPanel } from "./MainPageDetailPanel";
import { MainPageSessionSidebar } from "./MainPageSessionSidebar";
import { SessionMessagePanel } from "./SessionMessagePanel";
import { TaskTreePanel } from "./TaskTreePanel";
import {
  buildTaskScopedProjection,
  selectEventConnectionStatusPresentation,
  selectTopStatusPresentation,
} from "./mainPageSelectors";
import type { DetailOverride } from "./mainPageUiTypes";
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
import { useMainPageController } from "./useMainPageController";
import styles from "./MainPage.module.css";

const stateOptions = listMainPageStateOptions();

export type MainPageProps = {
  adapter?: MainPageAdapter;
  initialStateId?: MainPageStateId;
};

export function MainPage({
  adapter = mainPageMockAdapter,
  initialStateId = defaultMainPageStateId,
}: MainPageProps = {}) {
  const {
    actions,
    confirmationError,
    detailOverride,
    eventConnectionStatus,
    eventError,
    inputDraft,
    inputError,
    isCreatingSession,
    isDeletingSession,
    isInputSubmitting,
    isPublishingTaskTree,
    isRenamingSession,
    isResolvingConfirmation,
    isSnapshotError,
    isSnapshotPending,
    selectedTaskNodeId,
    snapshotData,
    snapshotError,
    stateId,
    taskTreeCommandError,
    uiNotice,
  } = useMainPageController({
    adapter,
    initialStateId,
  });

  if (isSnapshotPending) {
    return (
      <MainPageStatusFrame
        stateId={stateId}
        onStateChange={actions.changeState}
        showStatePicker={adapter.showStatePicker}
        statusLabel="Loading snapshot"
        statusTone="blue"
        title="Loading session snapshot"
        body="Plato is preparing the current Project, Workflow, Session, TaskTree, and message projection."
      />
    );
  }

  if (isSnapshotError || !snapshotData) {
    const errorSummary = isSnapshotError
      ? snapshotErrorSummary(snapshotError)
      : "Snapshot data is empty.";
    const noSessionAvailable =
      snapshotError instanceof Error &&
      snapshotError.message === NO_SESSION_AVAILABLE_MESSAGE;

    return (
      <MainPageStatusFrame
        action={
          noSessionAvailable
            ? {
                disabled: isCreatingSession,
                label: isCreatingSession
                  ? "Creating session"
                  : "New session",
                onClick: actions.createSession,
              }
            : undefined
        }
        stateId={stateId}
        onStateChange={actions.changeState}
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
  const displayTopStatus = selectTopStatusPresentation(metadata);
  const eventStatus = selectEventConnectionStatusPresentation(
    eventConnectionStatus,
  );
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
  const inputTarget = selectedTask ? "task" : "session";
  const canPublishTaskTree = snapshot.taskTree?.status === "draft";

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
        <Badge tone={eventStatus.tone}>{eventStatus.label}</Badge>
        {adapter.showStatePicker ? (
          <StatePicker stateId={stateId} onStateChange={actions.changeState} />
        ) : null}
      </header>

      <MainPageSessionSidebar
        activeSession={snapshot.session}
        isCreatingSession={isCreatingSession}
        isDeletingSession={isDeletingSession}
        isRenamingSession={isRenamingSession}
        onCreateSession={actions.createSession}
        onDeleteSession={actions.deleteSession}
        onRenameSession={actions.renameSession}
        onSelectSession={actions.selectSession}
        sessions={snapshot.sessions}
      />

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
                disabled={isPublishingTaskTree}
                onClick={() =>
                  actions.publishTaskTree({
                    sessionId: snapshot.session.id,
                    taskTreeId: snapshot.taskTree?.id ?? null,
                  })
                }
              >
                {isPublishingTaskTree
                  ? "Publishing"
                  : "Publish TaskTree"}
              </Button>
            ) : null}
            <Button
              onClick={() =>
                actions.showUnavailableNotice({
                  action: "Audit view",
                  sessionId: snapshot.session.id,
                })
              }
            >
              View audit
            </Button>
          </div>
        </div>

        <div className={styles.workGrid}>
          <TaskTreePanel
            confirmationDecision={null}
            onSelectTask={actions.selectTask}
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
        isResolvingConfirmation={isResolvingConfirmation}
        onConfirmationDecision={(decision) =>
          actions.resolveConfirmation({
            confirmation: activeConfirmation,
            decision,
            sessionId: snapshot.session.id,
          })
        }
        onShowFileChanges={actions.showFileChanges}
        onShowResult={actions.showResult}
        result={visibleResult}
        selectedTask={selectedTask}
      />

      <ContextInputPanel
        disabled={isInputSubmitting}
        draft={inputDraft}
        error={inputError}
        inputScope={inputScope}
        onDraftChange={actions.changeInputDraft}
        onSubmit={() =>
          actions.submitInput({
            hasTaskTree: snapshot.taskTree !== null,
            sessionId: snapshot.session.id,
            target: inputTarget,
            taskNodeId: selectedTask?.id ?? null,
          })
        }
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

function messagesFor(snapshot: MainPageSnapshot): SessionMessageView[] {
  return snapshot.messages;
}

function snapshotErrorSummary(error: unknown): string {
  if (error instanceof Error) {
    return `Error: ${error.message}`;
  }

  return "Check the browser console for the captured error payload.";
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
