import { Settings as SettingsIcon } from "lucide-react";

import { navigateApp } from "../../app/navigation";
import { productRecoveryActionsFromUnknown } from "../../shared/api/productErrors";
import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type { BadgeTone } from "../../shared/components";
import { Button, Panel, Text } from "../../shared/components";
import { buildSettingsRoute } from "../settings/settingsRouteModel";
import { NO_SESSION_AVAILABLE_MESSAGE } from "./httpMainPageAdapter";
import { MainPageTopBar } from "./MainPageTopBar";
import { MainPageWorkbench } from "./MainPageWorkbench";
import { ProductRecoveryActions } from "./ProductRecoveryActions";
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
    authoringAskRecoveryActions,
    confirmationError,
    confirmationRecoveryActions,
    detailOverride,
    eventConnectionStatus,
    eventError,
    inputDraft,
    inputError,
    inputRecoveryActions,
    isCreatingSession,
    isDeletingSession,
    isAnsweringAuthoringAsk,
    executionAskError,
    executionAskRecoveryActions,
    isAnsweringAsk,
    isCancellingAsk,
    isDeferringAsk,
    isInputSubmitting,
    isPublishingTaskTree,
    isRepairingAuthoringState,
    isRenamingSession,
    isRetryingTask,
    isStoppingTask,
    isResolvingConfirmation,
    selectionTarget,
    sessionDialog,
    isSnapshotError,
    isSnapshotPending,
    selectedTaskNodeId,
    snapshotData,
    snapshotError,
    stateId,
    taskTreeCommandError,
    taskTreeCommandRecoveryActions,
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
        recoveryActions={
          noSessionAvailable
            ? []
            : productRecoveryActionsFromUnknown(snapshotError)
        }
      />
    );
  }

  const { metadata, snapshot } = snapshotData;
  const topBarTrailing = renderTopBarTrailing({
    onStateChange: actions.changeState,
    showStatePicker: adapter.showStatePicker,
    stateId,
  });
  const viewModel = buildMainPageViewModel({
    auditRouteAvailable,
    authoringAskError,
    authoringAskRecoveryActions,
    confirmationError,
    confirmationRecoveryActions,
    detailOverride,
    eventConnectionStatus,
    eventError,
    isAnsweringAuthoringAsk,
    executionAskError,
    executionAskRecoveryActions,
    isAnsweringAsk,
    isCancellingAsk,
    isDeferringAsk,
    inputDisabled: isInputSubmitting,
    isPublishingTaskTree,
    isRetryingTask,
    isStoppingTask,
    isResolvingConfirmation,
    metadata,
    selectionTarget,
    selectedTaskNodeId,
    snapshot,
    taskTreeCommandError,
    taskTreeCommandRecoveryActions,
    uiNotice,
  });

  return (
    <MainPageWorkbench
      actions={actions}
      inputDraft={inputDraft}
      inputError={inputError}
      inputRecoveryActions={inputRecoveryActions}
      isCreatingSession={isCreatingSession}
      isDeletingSession={isDeletingSession}
      isRepairingAuthoringState={isRepairingAuthoringState}
      isRenamingSession={isRenamingSession}
      sessionDialog={sessionDialog}
      topBarTrailing={topBarTrailing}
      viewModel={viewModel}
    />
  );
}

function SettingsTopBarButton() {
  return (
    <Button
      aria-label="Settings"
      onClick={() => navigateApp(buildSettingsRoute())}
      size="icon"
      title="Settings"
      variant="ghost"
    >
      <SettingsIcon aria-hidden="true" size={18} />
    </Button>
  );
}

function renderTopBarTrailing({
  onStateChange,
  showStatePicker,
  stateId,
}: {
  onStateChange: (stateId: MainPageStateId) => void;
  showStatePicker: boolean;
  stateId: MainPageStateId;
}) {
  return showStatePicker ? (
    <StatePicker stateId={stateId} onStateChange={onStateChange} />
  ) : (
    <SettingsTopBarButton />
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
  recoveryActions?: ProductRecoveryAction[];
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
  recoveryActions = [],
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
          renderTopBarTrailing({
            onStateChange,
            showStatePicker,
            stateId,
          })
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
          <ProductRecoveryActions actions={recoveryActions} />
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
