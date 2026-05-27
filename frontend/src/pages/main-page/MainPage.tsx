import type { BadgeTone } from "../../shared/components";
import { Button, Panel, Text } from "../../shared/components";
import { ContextInputPanel } from "./ContextInputPanel";
import { NO_SESSION_AVAILABLE_MESSAGE } from "./httpMainPageAdapter";
import { MainPageDetailPanel } from "./MainPageDetailPanel";
import { MainPageSessionSidebar } from "./MainPageSessionSidebar";
import { MainPageTopBar } from "./MainPageTopBar";
import { MainPageWorkspaceHeader } from "./MainPageWorkspaceHeader";
import { SessionMessagePanel } from "./SessionMessagePanel";
import { TaskTreePanel } from "./TaskTreePanel";
import { buildMainPageViewModel } from "./mainPageViewModel";
import {
  defaultMainPageStateId,
  listMainPageStateOptions,
  mainPageMockAdapter,
} from "./mockPlatoApi";
import type { MainPageStateId } from "./mockPlatoApi";
import type { MainPageAdapter } from "./runtime/adapter";
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
  const viewModel = buildMainPageViewModel({
    confirmationError,
    detailOverride,
    eventConnectionStatus,
    eventError,
    inputDisabled: isInputSubmitting,
    isPublishingTaskTree,
    isResolvingConfirmation,
    metadata,
    selectedTaskNodeId,
    snapshot,
    taskTreeCommandError,
    uiNotice,
  });

  return (
    <main className={styles.page}>
      <MainPageTopBar
        brandLabel={viewModel.topBar.brandLabel}
        contextItems={viewModel.topBar.contextItems}
        statuses={viewModel.topBar.statuses}
        trailing={
          adapter.showStatePicker ? (
            <StatePicker
              stateId={stateId}
              onStateChange={actions.changeState}
            />
          ) : null
        }
      />

      <MainPageSessionSidebar
        activeSession={viewModel.sidebar.activeSession}
        isCreatingSession={isCreatingSession}
        isDeletingSession={isDeletingSession}
        isRenamingSession={isRenamingSession}
        onCreateSession={actions.createSession}
        onDeleteSession={actions.deleteSession}
        onRenameSession={actions.renameSession}
        onSelectSession={actions.selectSession}
        sessions={viewModel.sidebar.sessions}
      />

      <Panel
        as="section"
        className={styles.workspace}
        aria-label="Task workspace"
      >
        <MainPageWorkspaceHeader
          eventError={viewModel.workspace.eventError}
          isPublishingTaskTree={viewModel.workspace.isPublishingTaskTree}
          onPublishTaskTree={() =>
            actions.publishTaskTree({
              sessionId: viewModel.sessionId,
              taskTreeId: viewModel.workspace.taskTreeId,
            })
          }
          onViewAudit={() =>
            actions.showUnavailableNotice({
              action: "Audit view",
              sessionId: viewModel.sessionId,
            })
          }
          showPublishTaskTree={viewModel.workspace.showPublishTaskTree}
          taskTreeCommandError={viewModel.workspace.taskTreeCommandError}
          title={viewModel.workspace.title}
          uiNotice={viewModel.workspace.uiNotice}
        />

        <div className={styles.workGrid}>
          <TaskTreePanel
            confirmationDecision={null}
            onSelectTask={actions.selectTask}
            selectedTaskNodeId={viewModel.taskWorkspace.selectedTaskNodeId}
            taskTree={viewModel.taskWorkspace.taskTree}
          />

          <SessionMessagePanel
            isMessageScoped={viewModel.taskWorkspace.isMessageScoped}
            messages={viewModel.taskWorkspace.messages}
            selectedTask={viewModel.taskWorkspace.selectedTask}
            totalMessageCount={viewModel.taskWorkspace.totalMessageCount}
            visibleMessageCount={viewModel.taskWorkspace.visibleMessageCount}
          />
        </div>
      </Panel>

      <MainPageDetailPanel
        detail={viewModel.detail}
        onConfirmationDecision={(decision) =>
          actions.resolveConfirmation({
            confirmation:
              viewModel.detail.kind === "confirmation"
                ? viewModel.detail.confirmation
                : undefined,
            decision,
            sessionId: viewModel.sessionId,
          })
        }
        onShowFileChanges={actions.showFileChanges}
        onShowResult={actions.showResult}
      />

      <ContextInputPanel
        draft={inputDraft}
        error={inputError}
        input={viewModel.input}
        onDraftChange={actions.changeInputDraft}
        onSubmit={() =>
          actions.submitInput({
            mode: viewModel.input.mode,
            sessionId: viewModel.sessionId,
            target: viewModel.input.target,
            taskNodeId: viewModel.input.taskNodeId,
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
      <MainPageTopBar
        brandLabel="柏拉图 Plato"
        contextItems={[
          "Plato workspace",
          "Snapshot boundary",
          "Session projection",
        ]}
        statuses={[
          {
            label: statusLabel,
            tone: statusTone,
          },
        ]}
        trailing={
          showStatePicker ? (
            <StatePicker stateId={stateId} onStateChange={onStateChange} />
          ) : null
        }
      />

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

function snapshotErrorSummary(error: unknown): string {
  if (error instanceof Error) {
    return `Error: ${error.message}`;
  }

  return "Check the browser console for the captured error payload.";
}
