import { Settings as SettingsIcon } from "lucide-react";

import { navigateApp } from "../../app/navigation";
import { productRecoveryActionsFromUnknown } from "../../shared/api/productErrors";
import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type { BadgeTone } from "../../shared/components";
import { Badge, Button, Panel, Text } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import { buildSettingsRoute } from "../settings/settingsRouteModel";
import { NO_SESSION_AVAILABLE_MESSAGE } from "./httpMainPageAdapter";
import { MainPageSessionSidebar } from "./MainPageSessionSidebar";
import { MainPageWorkbench } from "./MainPageWorkbench";
import type { MainPageWorkspaceRuntime } from "./MainPageWorkspaceSwitcher";
import { PlatoProductMark } from "./PlatoProductMark";
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
  initialTaskNodeId?: string | null;
  workspaceRuntime?: MainPageWorkspaceRuntime | null;
};

export function MainPage({
  adapter = mainPageMockAdapter,
  auditRouteAvailable = true,
  initialStateId = defaultMainPageStateId,
  initialTaskNodeId = null,
  workspaceRuntime = null,
}: MainPageProps = {}) {
  const uiText = useUiText();
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
    isArchivingPlan,
    isPublishingTaskTree,
    isRepairingAuthoringState,
    isRenamingSession,
    isRetryingTask,
    isStoppingTask,
    isResolvingConfirmation,
    activeRuntimeInputMode,
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
    runtimeActivityItems,
    workspaceCatalog,
  } = useMainPageController({
    adapter,
    initialStateId,
    initialTaskNodeId,
  });

  if (isSnapshotPending) {
    return (
      <MainPageStatusFrame
        stateId={stateId}
        onStateChange={actions.changeState}
        showStatePicker={adapter.showStatePicker}
        statusLabel={uiText.common.status.loading}
        statusTone="blue"
        title={uiText.main.states.openingSessionTitle}
        body={uiText.main.states.openingSessionBody}
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
                  ? uiText.main.states.creatingSessionFull
                  : uiText.main.actions.createSession,
                onClick: actions.createSession,
              }
            : undefined
        }
        stateId={stateId}
        onStateChange={actions.changeState}
        showStatePicker={adapter.showStatePicker}
        statusLabel={
          noSessionAvailable
            ? uiText.main.labels.noSessions
            : uiText.main.states.loadError
        }
        statusTone={noSessionAvailable ? "neutral" : "danger"}
        title={
          noSessionAvailable
            ? uiText.main.empty.createFirstSessionTitle
            : uiText.main.states.unableToOpenSessionTitle
        }
        body={
          noSessionAvailable
            ? uiText.main.empty.createFirstSessionBody
            : uiText.main.states.unableToOpenSessionBody
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
  const utilitySlot = renderUtilitySlot({
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
    activeRuntimeInputMode,
    metadata,
    runtimeInputRouterAvailable: adapter.routeRuntimeInput !== undefined,
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
      isInputSubmitting={isInputSubmitting}
      isArchivingPlan={isArchivingPlan}
      isRepairingAuthoringState={isRepairingAuthoringState}
      isRenamingSession={isRenamingSession}
      sessionDialog={sessionDialog}
      utilitySlot={utilitySlot}
      viewModel={viewModel}
      runtimeActivityItems={runtimeActivityItems}
      activeWorkspaceId={activeWorkspaceId}
      workspaceCatalog={workspaceCatalog}
      workspaceRuntime={workspaceRuntime}
      exportDiagnosticBundle={adapter.exportDiagnosticBundle}
      loadSessionActivity={adapter.loadSessionActivity}
      loadTokenUsageSummary={adapter.loadTokenUsageSummary}
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
  const uiText = useUiText();

  return (
    <main className={`${styles.page} ${styles.pageWithoutDetail}`}>
      <MainPageSessionSidebar
        activeSession={null}
        brandLabel="柏拉图 Plato"
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
        utilitySlot={renderUtilitySlot({
          onStateChange,
          showStatePicker,
          stateId,
        })}
        activeWorkspaceId={activeWorkspaceId}
        workspaceCatalog={workspaceCatalog}
        workspaceRuntime={workspaceRuntime}
      />

      <Panel
        as="section"
        className={styles.workspace}
        aria-label={uiText.main.labels.taskWorkspace}
      >
        <div className={styles.emptyState}>
          <Text as="h1" variant="heading">
            {uiText.main.empty.createFirstSessionTitle}
          </Text>
          <Text variant="muted">
            {uiText.main.empty.createFirstSessionBody}
          </Text>
          <Button
            disabled={isCreatingSession}
            onClick={() => onCreateSession(activeWorkspaceId)}
            variant="primary"
          >
            {isCreatingSession
              ? uiText.main.states.creatingSessionFull
              : uiText.main.actions.createSession}
          </Button>
        </div>
      </Panel>
    </main>
  );
}

function SettingsUtilityButton() {
  const uiText = useUiText();

  return (
    <Button
      aria-label={uiText.settings.labels.settings}
      onClick={() => navigateApp(buildSettingsRoute())}
      size="icon"
      title={uiText.settings.labels.settings}
      variant="ghost"
    >
      <SettingsIcon aria-hidden="true" size={18} />
    </Button>
  );
}

function renderUtilitySlot({
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
    <SettingsUtilityButton />
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
  const uiText = useUiText();

  return (
    <main className={`${styles.page} ${styles.statusPage}`}>
      <Panel
        as="section"
        className={styles.workspace}
        aria-label={uiText.main.labels.taskWorkspace}
      >
        <div className={styles.statusFrameToolbar}>
          <div className={styles.statusFrameBrand}>
            <PlatoProductMark className={styles.railBrandMark} />
            <span>Plato</span>
          </div>
          <div className={styles.statusFrameActions}>
            <Badge className={styles.statusFrameBadge} tone={statusTone}>
              {statusLabel}
            </Badge>
            {renderUtilitySlot({
              onStateChange,
              showStatePicker,
              stateId,
            })}
          </div>
        </div>
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
