import { Settings as SettingsIcon } from "lucide-react";

import { navigateApp } from "../../app/navigation";
import { productRecoveryActionsFromUnknown } from "../../shared/api/productErrors";
import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type { BadgeTone } from "../../shared/components";
import { Button, Panel, Text } from "../../shared/components";
import { buildSettingsRoute } from "../settings/settingsRouteModel";
import { NO_SESSION_AVAILABLE_MESSAGE } from "./httpMainPageAdapter";
import { MainPageSessionSidebar } from "./MainPageSessionSidebar";
import { MainPageTopBar } from "./MainPageTopBar";
import { MainPageWorkbench } from "./MainPageWorkbench";
import type { MainPageWorkspaceRuntime } from "./MainPageWorkspaceSwitcher";
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
  workspaceRuntime?: MainPageWorkspaceRuntime | null;
};

export function MainPage({
  adapter = mainPageMockAdapter,
  auditRouteAvailable = true,
  initialStateId = defaultMainPageStateId,
  workspaceRuntime = null,
}: MainPageProps = {}) {
  const {
    actions,
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
    workspaceCatalog,
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

    if (noSessionAvailable) {
      return (
        <MainPageNoSessionFrame
          isCreatingSession={isCreatingSession}
          isDeletingSession={isDeletingSession}
          isRenamingSession={isRenamingSession}
          onCancelSessionDialog={actions.cancelSessionDialog}
          onChangeSessionDialogDraft={actions.changeSessionDialogDraft}
          onCreateSession={actions.createSession}
          onDeleteSession={actions.deleteSession}
          onRenameSession={actions.renameSession}
          onSelectSession={actions.selectSession}
          onStateChange={actions.changeState}
          onSubmitSessionDialog={actions.submitSessionDialog}
          sessionDialog={sessionDialog}
          showStatePicker={adapter.showStatePicker}
          stateId={stateId}
          activeWorkspaceId={activeWorkspaceId}
          workspaceCatalog={workspaceCatalog}
          workspaceRuntime={workspaceRuntime}
        />
      );
    }

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
    workspaceId: activeWorkspaceId,
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
      activeWorkspaceId={activeWorkspaceId}
      workspaceCatalog={workspaceCatalog}
      workspaceRuntime={workspaceRuntime}
    />
  );
}

type MainPageNoSessionFrameProps = {
  activeWorkspaceId: string | null;
  isCreatingSession: boolean;
  isDeletingSession: boolean;
  isRenamingSession: boolean;
  onCancelSessionDialog: () => void;
  onChangeSessionDialogDraft: (draftName: string) => void;
  onCreateSession: MainPageControllerAction<"createSession">;
  onDeleteSession: MainPageControllerAction<"deleteSession">;
  onRenameSession: MainPageControllerAction<"renameSession">;
  onSelectSession: MainPageControllerAction<"selectSession">;
  onStateChange: (stateId: MainPageStateId) => void;
  onSubmitSessionDialog: () => void;
  sessionDialog: ReturnType<typeof useMainPageController>["sessionDialog"];
  showStatePicker: boolean;
  stateId: MainPageStateId;
  workspaceCatalog: ReturnType<typeof useMainPageController>["workspaceCatalog"];
  workspaceRuntime?: MainPageWorkspaceRuntime | null;
};

type MainPageControllerAction<
  TAction extends keyof ReturnType<typeof useMainPageController>["actions"],
> = ReturnType<typeof useMainPageController>["actions"][TAction];

function MainPageNoSessionFrame({
  activeWorkspaceId,
  isCreatingSession,
  isDeletingSession,
  isRenamingSession,
  onCancelSessionDialog,
  onChangeSessionDialogDraft,
  onCreateSession,
  onDeleteSession,
  onRenameSession,
  onSelectSession,
  onStateChange,
  onSubmitSessionDialog,
  sessionDialog,
  showStatePicker,
  stateId,
  workspaceCatalog,
  workspaceRuntime = null,
}: MainPageNoSessionFrameProps) {
  return (
    <main className={`${styles.page} ${styles.pageWithoutDetail}`}>
      <MainPageTopBar
        brandLabel="柏拉图 Plato"
        contextItems={["Local Project", "Session"]}
        statuses={[
          {
            label: "No sessions",
            tone: "neutral",
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

      <MainPageSessionSidebar
        activeSession={null}
        isCreatingSession={isCreatingSession}
        isDeletingSession={isDeletingSession}
        isRenamingSession={isRenamingSession}
        onCancelSessionDialog={onCancelSessionDialog}
        onChangeSessionDialogDraft={onChangeSessionDialogDraft}
        onCreateSession={onCreateSession}
        onDeleteSession={onDeleteSession}
        onRenameSession={onRenameSession}
        onSelectSession={onSelectSession}
        onSubmitSessionDialog={onSubmitSessionDialog}
        sessionDialog={sessionDialog}
        sessions={[]}
        activeWorkspaceId={activeWorkspaceId}
        workspaceCatalog={workspaceCatalog}
        workspaceRuntime={workspaceRuntime}
      />

      <Panel
        as="section"
        className={styles.workspace}
        aria-label="Task workspace"
      >
        <div className={styles.emptyState}>
          <Text as="h1" variant="heading">
            Create your first session
          </Text>
          <Text variant="muted">
            This workspace has no sessions yet. Create one when you are ready to
            start.
          </Text>
          <Button
            disabled={isCreatingSession}
            onClick={() => onCreateSession(activeWorkspaceId)}
            variant="primary"
          >
            {isCreatingSession ? "Creating session" : "New session"}
          </Button>
        </div>
      </Panel>
    </main>
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
