import type { BadgeTone } from "../../shared/components";
import { Button, Panel, Text } from "../../shared/components";
import { NO_SESSION_AVAILABLE_MESSAGE } from "./httpMainPageAdapter";
import { MainPageTopBar } from "./MainPageTopBar";
import { MainPageWorkbench } from "./MainPageWorkbench";
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
  auditRouteAvailable?: boolean;
  initialStateId?: MainPageStateId;
};

export function MainPage({
  adapter = mainPageMockAdapter,
  auditRouteAvailable = true,
  initialStateId = defaultMainPageStateId,
}: MainPageProps = {}) {
  const {
    actions,
    authoringAskError,
    confirmationError,
    detailOverride,
    eventConnectionStatus,
    eventError,
    inputDraft,
    inputError,
    isCreatingSession,
    isDeletingSession,
    isAnsweringAuthoringAsk,
    executionAskError,
    isAnsweringAsk,
    isCancellingAsk,
    isDeferringAsk,
    isInputSubmitting,
    isPublishingTaskTree,
    isRenamingSession,
    isRetryingTask,
    isStoppingTask,
    isResolvingConfirmation,
    sessionDialog,
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
        statusLabel="Loading"
        statusTone="blue"
        title="Opening session"
        body="Plato is preparing this workspace."
      />
    );
  }

  if (isSnapshotError || !snapshotData) {
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
        statusLabel={noSessionAvailable ? "No sessions" : "Load error"}
        statusTone={noSessionAvailable ? "neutral" : "danger"}
        title={
          noSessionAvailable
            ? "Create your first session"
            : "Unable to open session"
        }
        body={
          noSessionAvailable
            ? "This workspace has no sessions yet. Create one when you are ready to start."
            : "Plato could not load this session. Refresh the page or choose another session."
        }
      />
    );
  }

  const { metadata, snapshot } = snapshotData;
  const viewModel = buildMainPageViewModel({
    auditRouteAvailable,
    authoringAskError,
    confirmationError,
    detailOverride,
    eventConnectionStatus,
    eventError,
    isAnsweringAuthoringAsk,
    executionAskError,
    isAnsweringAsk,
    isCancellingAsk,
    isDeferringAsk,
    inputDisabled: isInputSubmitting,
    isPublishingTaskTree,
    isRetryingTask,
    isStoppingTask,
    isResolvingConfirmation,
    metadata,
    selectedTaskNodeId,
    snapshot,
    taskTreeCommandError,
    uiNotice,
  });

  return (
    <MainPageWorkbench
      actions={actions}
      inputDraft={inputDraft}
      inputError={inputError}
      isCreatingSession={isCreatingSession}
      isDeletingSession={isDeletingSession}
      isRenamingSession={isRenamingSession}
      sessionDialog={sessionDialog}
      statePicker={
        adapter.showStatePicker ? (
          <StatePicker stateId={stateId} onStateChange={actions.changeState} />
        ) : null
      }
      viewModel={viewModel}
    />
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
        contextItems={["Local Project", "Task authoring", "Session"]}
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
