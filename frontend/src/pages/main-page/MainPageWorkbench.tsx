import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent,
  type ReactNode,
} from "react";

import { navigateApp } from "../../app/navigation";
import { buildSettingsRoute } from "../settings/settingsRouteModel";
import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type {
  PlanView,
  SessionActivityItemView,
  SessionActivityRefView,
  SessionMessageView,
  TaskNodeId,
} from "../../shared/api/types";
import { Button, Panel } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import {
  ActivityOverlay,
  type ActivityOverlayStatusMessage,
} from "./ActivityOverlay";
import { ArchivedPlansPanel } from "./ArchivedPlansPanel";
import { ConfirmationDock } from "./ConfirmationDock";
import { ConversationLayer } from "./ConversationLayer";
import { ContextInputPanel } from "./ContextInputPanel";
import { LatestActivityStrip } from "./LatestActivityStrip";
import { MainPageDetailPanel } from "./MainPageDetailPanel";
import { MainPageSessionSidebar } from "./MainPageSessionSidebar";
import type { MainPageWorkspaceRuntime } from "./MainPageWorkspaceSwitcher";
import { MainPageWorkspaceHeader } from "./MainPageWorkspaceHeader";
import { TaskTreePanel } from "./TaskTreePanel";
import { buildConversationAskInteraction } from "./conversation-ask/buildConversationAskInteraction";
import type { ExecutionAskConversationCommandState } from "./conversation-ask/conversationAskInteraction";
import { useConversationAskDraftStore } from "./conversation-ask/useConversationAskDraftStore";
import {
  isActivitySourceMessage,
  isConversationVisible,
} from "./conversationMessageVisibility";
import { activityItemsFromMessages } from "./mainPageActivityProjection";
import { newestActivityItemId } from "./useMainPageOverlayRuntime";
import type {
  MainPageDetailView,
  MainPageViewModel,
} from "./mainPageViewModel";
import type { MainPageController } from "./useMainPageController";
import { useMainPageFocusScrollRuntime } from "./useMainPageFocusScrollRuntime";
import type {
  ExportDiagnosticBundle,
  LoadSessionActivity,
  LoadTokenUsageSummary,
} from "./runtime/adapter";
import type { MainPageRouteFocusTarget } from "./runtime/mainPageFocusScrollRuntime";
import styles from "./MainPage.module.css";

const DEFAULT_DETAIL_WIDTH = 380;
const MIN_DETAIL_WIDTH = 320;
const MAX_DETAIL_WIDTH = 680;
const DETAIL_RESIZE_STEP = 24;
const SETTINGS_RECOVERY_ACTIONS = new Set<ProductRecoveryAction>([
  "open_settings",
  "open_macos_privacy_accessibility",
  "open_macos_privacy_automation",
  "restart_helper",
  "rerun_readiness_check",
]);

export type MainPageWorkbenchProps = {
  actions: MainPageController["actions"];
  activeWorkspaceId: MainPageController["activeWorkspaceId"];
  inputDraft: string;
  inputError: string | null;
  inputRecoveryActions: ProductRecoveryAction[];
  executionAskCommandStates?: Readonly<
    Record<string, ExecutionAskConversationCommandState>
  >;
  isArchivingPlan: boolean;
  isCreatingSession: boolean;
  isDeletingSession: boolean;
  isInputSubmitting: boolean;
  isRepairingAuthoringState: boolean;
  isRenamingSession: boolean;
  sessionDialog: MainPageController["sessionDialog"];
  utilitySlot?: ReactNode;
  viewModel: MainPageViewModel;
  runtimeActivityItems?: readonly SessionActivityItemView[];
  workspaceCatalog: MainPageController["workspaceCatalog"];
  workspaceRuntime?: MainPageWorkspaceRuntime | null;
  exportDiagnosticBundle?: ExportDiagnosticBundle;
  loadSessionActivity?: LoadSessionActivity;
  loadTokenUsageSummary?: LoadTokenUsageSummary;
  routeFocusTarget?: MainPageRouteFocusTarget | null;
};

export function MainPageWorkbench({
  actions,
  activeWorkspaceId,
  inputDraft,
  inputError,
  inputRecoveryActions,
  executionAskCommandStates = {},
  isArchivingPlan,
  isCreatingSession,
  isDeletingSession,
  isInputSubmitting,
  isRepairingAuthoringState,
  isRenamingSession,
  sessionDialog,
  utilitySlot = null,
  viewModel,
  runtimeActivityItems = [],
  workspaceCatalog,
  workspaceRuntime = null,
  exportDiagnosticBundle,
  loadSessionActivity,
  loadTokenUsageSummary,
  routeFocusTarget = null,
}: MainPageWorkbenchProps) {
  const uiText = useUiText();
  const askDraftStore = useConversationAskDraftStore(viewModel.sessionId);
  const [isActivityOverlayOpen, setIsActivityOverlayOpen] = useState(false);
  const [isArchivedPlansPanelOpen, setIsArchivedPlansPanelOpen] =
    useState(false);
  const [selectedArchivedPlanId, setSelectedArchivedPlanId] =
    useState<string | null>(null);
  const [selectedArchivedPlanTaskNodeId, setSelectedArchivedPlanTaskNodeId] =
    useState<TaskNodeId | null>(null);
  const [activityItems, setActivityItems] = useState<
    SessionActivityItemView[]
  >([]);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [activityLoadKey, setActivityLoadKey] = useState(0);
  const [isActivityLoading, setIsActivityLoading] = useState(false);
  const hasPlanLayer =
    viewModel.taskWorkspace.taskTree !== null ||
    viewModel.taskWorkspace.isGeneratingTaskPlan;
  const activeAskFocusIdentity =
    viewModel.mainWorkArea.kind === "authoringAsk"
      ? `authoring:${viewModel.mainWorkArea.authoringAsk.rawTaskId}`
      : viewModel.detail.kind === "executionAsk"
        ? `execution:${viewModel.detail.ask.id}`
        : null;
  const [isPlanLayerExpanded, setIsPlanLayerExpanded] =
    useState(hasPlanLayer && activeAskFocusIdentity === null);
  const [activityStatusMessage, setActivityStatusMessage] =
    useState<ActivityOverlayStatusMessage | null>(null);
  const [isExportingActivityDiagnostic, setIsExportingActivityDiagnostic] =
    useState(false);
  const [detailWidth, setDetailWidth] = useState(DEFAULT_DETAIL_WIDTH);
  const contextInputRef = useRef<HTMLInputElement>(null);
  const hasActivity =
    viewModel.taskWorkspace.allMessages.length > 0 ||
    runtimeActivityItems.length > 0 ||
    loadSessionActivity !== undefined;
  const showsActivityPanel = isActivityOverlayOpen && hasActivity;
  const fallbackActivityItems = useMemo(
    () =>
      activityItemsFromMessages(
        viewModel.taskWorkspace.allMessages.filter(isActivitySourceMessage),
      ),
    [viewModel.taskWorkspace.allMessages],
  );
  const archivedPlans = viewModel.taskWorkspace.archivedPlans;
  const selectedArchivedPlan =
    archivedPlans.find((plan) => plan.id === selectedArchivedPlanId) ?? null;
  const archivedPlanDetail =
    selectedArchivedPlan?.taskTreeProjection
      ? archivedPlanDetailView(
          selectedArchivedPlan,
          selectedArchivedPlanTaskNodeId,
        )
      : null;
  const showsArchivedPlansPanel =
    isArchivedPlansPanelOpen && archivedPlans.length > 0;
  const showsArchivedPlanDetailPanel =
    archivedPlanDetail !== null &&
    !showsActivityPanel &&
    !showsArchivedPlansPanel;
  const hasDetailColumn =
    viewModel.detail.kind !== "note" ||
    showsActivityPanel ||
    showsArchivedPlansPanel ||
    showsArchivedPlanDetailPanel;
  const showsDetailPanel =
    viewModel.detail.kind !== "note" &&
    !showsActivityPanel &&
    !showsArchivedPlansPanel &&
    !showsArchivedPlanDetailPanel;
  const pageClassName = !hasDetailColumn
    ? `${styles.page} ${styles.pageWithoutDetail}`
    : styles.page;
  const pageStyle = {
    "--plato-detail-width": `${detailWidth}px`,
  } as CSSProperties;
  const transientMessages = useMemo(
    () => runtimeActivityItems.map(messageFromActivityItem),
    [runtimeActivityItems],
  );
  const scopedTransientMessages = useMemo(
    () =>
      transientMessages.filter((message) =>
        (viewModel.taskWorkspace.selectedTask
          ? message.taskNodeId === viewModel.taskWorkspace.selectedTask.id
          : true),
      ),
    [transientMessages, viewModel.taskWorkspace.selectedTask],
  );
  const hasVisibleActivity =
    viewModel.taskWorkspace.messages.some(isActivitySourceMessage) ||
    scopedTransientMessages.length > 0;
  const resolvedWorkspaceId =
    viewModel.workspace.workspaceId ??
    viewModel.sidebar.activeSession.workspaceId ??
    activeWorkspaceId ??
    null;
  const overlayActivityItems =
    loadSessionActivity === undefined
      ? mergeActivityItems(runtimeActivityItems, fallbackActivityItems)
      : mergeActivityItems(runtimeActivityItems, activityItems);
  const selectedActivityItemId = newestActivityItemId(
    overlayActivityItems,
    viewModel.taskWorkspace.selectedTask?.id ?? null,
  );
  const allConversationMessages = useMemo(
    () =>
      mergeMessages(
        viewModel.taskWorkspace.allMessages,
        transientMessages,
      ),
    [transientMessages, viewModel.taskWorkspace.allMessages],
  );
  const conversationMessages = useMemo(
    () => allConversationMessages.filter(isConversationVisible),
    [allConversationMessages],
  );
  const focusScrollRuntime = useMainPageFocusScrollRuntime({
    inputDisabled: viewModel.input.disabled,
    inputError,
    inputRef: contextInputRef,
    isInputSubmitting,
    messages: conversationMessages,
    sessionId: viewModel.sessionId,
    workspaceId: resolvedWorkspaceId,
  });
  const {
    focusContextInput,
    focusTarget,
    scrollTargetIntoView,
  } = focusScrollRuntime;
  const handledRouteFocusRequestRef = useRef<string | null>(null);
  const showFileChangesRef = useRef(actions.showFileChanges);
  const latestActivityMessages = useMemo(
    () =>
      mergeMessages(
        viewModel.taskWorkspace.messages.filter(
          isActivitySourceMessage,
        ),
        scopedTransientMessages,
      ),
    [viewModel.taskWorkspace.messages, scopedTransientMessages],
  );
  const totalActivityCount = allConversationMessages.filter(
    isActivitySourceMessage,
  ).length;
  const visibleActivityCount = latestActivityMessages.length;
  const collapsedPlanTitle =
    viewModel.taskWorkspace.taskTree?.title ?? viewModel.workspace.title;
  const collapsedPlanMeta =
    viewModel.taskWorkspace.taskTree !== null
      ? `${uiText.main.detail.messages.taskCount({
          count: viewModel.taskWorkspace.taskTree.nodes.length,
        })} · ${
          uiText.main.detail.status.taskTree[
            viewModel.taskWorkspace.taskTree.status
          ]
        }`
      : uiText.main.plan.generatingTitle;
  const activePlan = viewModel.taskWorkspace.activePlan;
  const askInteraction = buildConversationAskInteraction(actions, viewModel, {
    draftStore: askDraftStore,
    executionByAskId: executionAskCommandStates,
  });
  const showArchivePlan = activePlan != null && canArchivePlan(activePlan);
  const archivePlanAction =
    showArchivePlan && activePlan != null ? (
      <Button
        disabled={isArchivingPlan}
        onClick={() =>
          actions.archivePlan({
            expectedVersion: activePlan.version,
            planId: activePlan.id,
            sessionId: viewModel.sessionId,
          })
        }
        size="sm"
        variant="secondary"
      >
        {isArchivingPlan
          ? uiText.main.detail.actions.archivingPlan
          : uiText.main.detail.actions.archivePlan}
      </Button>
    ) : null;

  useEffect(() => {
    setIsPlanLayerExpanded(
      hasPlanLayer && activeAskFocusIdentity === null,
    );
    setIsActivityOverlayOpen(false);
    setIsArchivedPlansPanelOpen(false);
    setSelectedArchivedPlanId(null);
    setSelectedArchivedPlanTaskNodeId(null);
  }, [activeAskFocusIdentity, hasPlanLayer, viewModel.sessionId]);

  useEffect(() => {
    if (
      selectedArchivedPlanId !== null &&
      !archivedPlans.some((plan) => plan.id === selectedArchivedPlanId)
    ) {
      setSelectedArchivedPlanId(null);
      setSelectedArchivedPlanTaskNodeId(null);
    }
  }, [archivedPlans, selectedArchivedPlanId]);

  useEffect(() => {
    showFileChangesRef.current = actions.showFileChanges;
  }, [actions.showFileChanges]);

  useEffect(() => {
    if (routeFocusTarget === null) {
      handledRouteFocusRequestRef.current = null;
      return;
    }

    const routeFocusRequestKey = [
      viewModel.sessionId,
      routeFocusTarget,
      viewModel.taskWorkspace.selectedTaskNodeId ?? "none",
    ].join(":");
    if (handledRouteFocusRequestRef.current === routeFocusRequestKey) {
      return;
    }
    handledRouteFocusRequestRef.current = routeFocusRequestKey;

    if (
      routeFocusTarget === "selected_task" &&
      viewModel.taskWorkspace.selectedTaskNodeId !== null
    ) {
      setIsPlanLayerExpanded(true);
    }

    if (routeFocusTarget === "file_changes") {
      showFileChangesRef.current();
    }

    const timeoutId = window.setTimeout(() => {
      if (routeFocusTarget === "input_composer") {
        focusContextInput("route_restored");
        return;
      }

      if (routeFocusTarget === "overlay_trigger") {
        focusTarget("overlay_trigger", "route_restored");
        return;
      }

      if (routeFocusTarget === "ask_card") {
        scrollTargetIntoView("ask_card", "route_restored");
        focusTarget("ask_card", "route_restored");
        return;
      }

      if (routeFocusTarget === "selected_task") {
        if (viewModel.taskWorkspace.selectedTaskNodeId !== null) {
          scrollTargetIntoView("selected_task", "route_restored");
          focusTarget("selected_task", "route_restored");
        }
        return;
      }

      scrollTargetIntoView(routeFocusTarget, "route_restored");
      focusTarget(routeFocusTarget, "route_restored");
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [
    focusContextInput,
    focusTarget,
    routeFocusTarget,
    scrollTargetIntoView,
    viewModel.sessionId,
    viewModel.taskWorkspace.selectedTaskNodeId,
  ]);

  useEffect(() => {
    if (activeAskFocusIdentity === null) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      scrollTargetIntoView("ask_card", "ask_presented");
      focusTarget("ask_card", "ask_presented");
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [
    activeAskFocusIdentity,
    focusTarget,
    scrollTargetIntoView,
  ]);

  useEffect(() => {
    if (!showsActivityPanel || selectedActivityItemId === null) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      scrollTargetIntoView("selected_activity", "overlay_opened");
      focusTarget("selected_activity", "overlay_opened");
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [
    focusTarget,
    overlayActivityItems.length,
    scrollTargetIntoView,
    selectedActivityItemId,
    showsActivityPanel,
  ]);

  useEffect(() => {
    if (!isActivityOverlayOpen || loadSessionActivity === undefined) {
      return;
    }

    let isCancelled = false;
    setIsActivityLoading(true);
    setActivityError(null);

    void loadSessionActivity(
      {
        limit: 100,
        sessionId: viewModel.sessionId,
      },
      resolvedWorkspaceId,
    )
      .then((timeline) => {
        if (isCancelled) {
          return;
        }
        setActivityItems(timeline.items);
      })
      .catch((error: unknown) => {
        if (isCancelled) {
          return;
        }
        setActivityError(
          error instanceof Error
            ? error.message
            : uiText.main.activity.descriptions.loadError,
        );
      })
      .finally(() => {
        if (!isCancelled) {
          setIsActivityLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [
    activityLoadKey,
    isActivityOverlayOpen,
    loadSessionActivity,
    resolvedWorkspaceId,
    uiText.main.activity.descriptions.loadError,
    viewModel.sessionId,
  ]);

  function openActivityOverlay(trigger: HTMLElement | null = null) {
    if (trigger !== null) {
      focusScrollRuntime.captureOverlayTriggerElement(trigger);
    } else {
      focusScrollRuntime.captureOverlayTrigger();
    }
    setIsArchivedPlansPanelOpen(false);
    setSelectedArchivedPlanId(null);
    setSelectedArchivedPlanTaskNodeId(null);
    setIsActivityOverlayOpen(true);
  }

  function openArchivedPlans(trigger: HTMLElement | null = null) {
    if (trigger !== null) {
      focusScrollRuntime.captureOverlayTriggerElement(trigger);
    } else {
      focusScrollRuntime.captureOverlayTrigger();
    }
    setIsActivityOverlayOpen(false);
    setIsArchivedPlansPanelOpen(true);
    setSelectedArchivedPlanId(null);
    setSelectedArchivedPlanTaskNodeId(null);
  }

  function closeOverlayAndReturnFocus() {
    setIsActivityOverlayOpen(false);
    setIsArchivedPlansPanelOpen(false);
    window.setTimeout(() => {
      focusScrollRuntime.focusTarget("overlay_trigger", "overlay_closed");
    }, 0);
  }

  function closeArchivedPlanAndReturnFocus() {
    setSelectedArchivedPlanId(null);
    setSelectedArchivedPlanTaskNodeId(null);
    window.setTimeout(() => {
      focusScrollRuntime.focusTarget("overlay_trigger", "overlay_closed");
    }, 0);
  }

  function showActivityResult(taskNodeId: string | null) {
    if (taskNodeId !== null) {
      actions.selectTask(taskNodeId);
    }
    actions.showResult();
    setIsActivityOverlayOpen(false);
    setIsArchivedPlansPanelOpen(false);
    setSelectedArchivedPlanId(null);
    setSelectedArchivedPlanTaskNodeId(null);
  }

  function showActivityFiles(taskNodeId: string | null) {
    if (taskNodeId !== null) {
      actions.selectTask(taskNodeId);
    }
    actions.showFileChanges();
    setIsActivityOverlayOpen(false);
    setIsArchivedPlansPanelOpen(false);
    setSelectedArchivedPlanId(null);
    setSelectedArchivedPlanTaskNodeId(null);
  }

  function showActivityAudit(ref: SessionActivityRefView) {
    const href = ref.href ?? viewModel.workspace.auditEntry.href;
    window.location.assign(href);
    setIsActivityOverlayOpen(false);
    setIsArchivedPlansPanelOpen(false);
    setSelectedArchivedPlanId(null);
    setSelectedArchivedPlanTaskNodeId(null);
  }

  async function exportActivityDiagnostic() {
    if (exportDiagnosticBundle === undefined || isExportingActivityDiagnostic) {
      return;
    }

    setActivityStatusMessage({
      body: uiText.settings.actions.exportingDiagnostics,
      tone: "info",
    });
    setIsExportingActivityDiagnostic(true);

    try {
      const result = await exportDiagnosticBundle(
        viewModel.sessionId,
        resolvedWorkspaceId,
      );
      setActivityStatusMessage({
        body: `${uiText.diagnostics.labels.bundleReady}: ${result.bundleId}`,
        tone: "info",
      });
    } catch {
      setActivityStatusMessage({
        body: uiText.settings.messages.diagnosticExportFailed,
        tone: "danger",
      });
    } finally {
      setIsExportingActivityDiagnostic(false);
    }
  }

  function resizeDetailPanel(nextWidth: number) {
    setDetailWidth(clampDetailWidth(nextWidth));
  }

  function startDetailResize(event: PointerEvent<HTMLButtonElement>) {
    if (!hasDetailColumn) {
      return;
    }

    event.preventDefault();
    const startX = event.clientX;
    const startWidth = detailWidth;

    function handlePointerMove(moveEvent: globalThis.PointerEvent) {
      resizeDetailPanel(startWidth - (moveEvent.clientX - startX));
    }

    function handlePointerUp() {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    }

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp, { once: true });
  }

  const planProgressLayer = hasPlanLayer ? (
    <TaskTreePanel
      activitySlot={
        hasVisibleActivity ? (
          <LatestActivityStrip
            isMessageScoped={viewModel.taskWorkspace.isMessageScoped}
            messages={latestActivityMessages}
            onOpenActivity={
              hasActivity ? openActivityOverlay : undefined
            }
            selectedTask={viewModel.taskWorkspace.selectedTask}
            totalMessageCount={totalActivityCount}
            visibleMessageCount={visibleActivityCount}
          />
        ) : null
      }
      authoringDiagnostic={viewModel.taskWorkspace.authoringDiagnostic}
      isRepairingAuthoringState={isRepairingAuthoringState}
      isTaskPlanSelected={viewModel.taskWorkspace.isTaskPlanSelected}
      onRetryTask={(taskNodeId) =>
        actions.retryTask({
          sessionId: viewModel.sessionId,
          taskNodeId,
        })
      }
      onRepairAuthoringState={() =>
        actions.repairAuthoringState({
          sessionId: viewModel.sessionId,
        })
      }
      onSelectTaskPlan={actions.selectTaskPlan}
      onSelectTask={actions.selectTask}
      onStopTask={(taskNodeId) =>
        actions.stopTask({
          sessionId: viewModel.sessionId,
          taskNodeId,
        })
      }
      selectedTaskRef={focusScrollRuntime.selectedTaskCardRef}
      selectedTaskNodeId={viewModel.taskWorkspace.selectedTaskNodeId}
      isGeneratingTaskPlan={viewModel.taskWorkspace.isGeneratingTaskPlan}
      taskTree={viewModel.taskWorkspace.taskTree}
    />
  ) : null;
  const archivedPlanProgressLayer =
    selectedArchivedPlan?.taskTreeProjection ? (
      <TaskTreePanel
        isTaskPlanSelected={selectedArchivedPlanTaskNodeId === null}
        onRetryTask={() => undefined}
        onSelectTaskPlan={() => setSelectedArchivedPlanTaskNodeId(null)}
        onSelectTask={setSelectedArchivedPlanTaskNodeId}
        onStopTask={() => undefined}
        selectedTaskNodeId={selectedArchivedPlanTaskNodeId}
        taskTree={selectedArchivedPlan.taskTreeProjection}
      />
    ) : null;
  const collapsePlanAction = (
    <button
      className={styles.planProgressCollapseButton}
      onClick={() => setIsPlanLayerExpanded(false)}
      type="button"
    >
      {uiText.main.detail.actions.collapse}
    </button>
  );
  const collapsedPlanTopbarAction =
    hasPlanLayer && !isPlanLayerExpanded ? (
      <button
        aria-label={uiText.main.detail.actions.openPlanProgress({
          title: collapsedPlanTitle,
        })}
        className={styles.collapsedPlanTopbarButton}
        onClick={() => setIsPlanLayerExpanded(true)}
        type="button"
      >
        <span className={styles.collapsedPlanTopbarLabel}>
          {uiText.main.detail.labels.plan}
        </span>
        <span className={styles.collapsedPlanTopbarTitle}>
          {collapsedPlanTitle}
        </span>
        <span className={styles.collapsedPlanTopbarMeta}>
          {collapsedPlanMeta}
        </span>
      </button>
    ) : null;
  const showConversationPlanEntry =
    !hasPlanLayer &&
    archivedPlans.length > 0;
  const conversationPlanAction = showConversationPlanEntry ? (
    <Button
      aria-label={uiText.main.detail.actions.openArchivedPlan}
      onClick={(event) => openArchivedPlans(event.currentTarget)}
      size="sm"
      variant="secondary"
    >
      {uiText.main.detail.labels.plan}
    </Button>
  ) : null;
  const conversationAuditAction =
    !hasPlanLayer || !isPlanLayerExpanded ? (
      viewModel.workspace.auditEntry.isEnabled ? (
        <Button asChild size="sm" variant="secondary">
          <a href={viewModel.workspace.auditEntry.href}>
            {viewModel.workspace.auditEntry.label}
          </a>
        </Button>
      ) : (
        <Button
          disabled
          size="sm"
          title={viewModel.workspace.auditEntry.disabledReason ?? undefined}
          variant="secondary"
        >
          {viewModel.workspace.auditEntry.label}
        </Button>
      )
    ) : null;
  const conversationHeaderActions = (
    <>
      {collapsedPlanTopbarAction}
      {conversationPlanAction}
      {conversationAuditAction}
    </>
  );

  function renderWorkspaceHeader(
    statusActions: ReactNode = null,
    actionSlot: ReactNode = null,
    title = viewModel.workspace.title,
  ) {
    return (
      <MainPageWorkspaceHeader
        actionSlot={actionSlot}
        auditEntry={viewModel.workspace.auditEntry}
        eventError={viewModel.workspace.eventError}
        isPublishingTaskTree={viewModel.workspace.isPublishingTaskTree}
        onPublishTaskTree={() =>
          actions.publishTaskTree({
            sessionId: viewModel.sessionId,
            taskTreeId: viewModel.workspace.taskTreeId,
          })
        }
        projectName={viewModel.topBar.contextItems[0] ?? ""}
        showPublishTaskTree={viewModel.workspace.showPublishTaskTree}
        taskTreeCommandError={viewModel.workspace.taskTreeCommandError}
        taskTreeCommandRecoveryActions={
          viewModel.workspace.taskTreeCommandRecoveryActions
        }
        sessionName={viewModel.sidebar.activeSession.name}
        statuses={viewModel.topBar.statuses}
        title={title}
        statusActions={statusActions}
        uiNotice={viewModel.workspace.uiNotice}
      />
    );
  }

  return (
    <main className={pageClassName} style={pageStyle}>
      <MainPageSessionSidebar
        activeSession={viewModel.sidebar.activeSession}
        brandLabel={viewModel.topBar.brandLabel}
        isCreatingSession={isCreatingSession}
        isDeletingSession={isDeletingSession}
        isRenamingSession={isRenamingSession}
        onCancelSessionDialog={actions.cancelSessionDialog}
        onChangeSessionDialogDraft={actions.changeSessionDialogDraft}
        onCreateSession={actions.createSession}
        onDeleteSession={actions.deleteSession}
        onRenameSession={actions.renameSession}
        onSelectSession={actions.selectSession}
        onSubmitSessionDialog={actions.submitSessionDialog}
        sessionDialog={sessionDialog}
        sessions={viewModel.sidebar.sessions}
        utilitySlot={utilitySlot}
        activeWorkspaceId={activeWorkspaceId}
        workspaceCatalog={workspaceCatalog}
        workspaceRuntime={workspaceRuntime}
      />

      <ConversationLayer
        activeAskIdentity={activeAskFocusIdentity}
        askCardRef={focusScrollRuntime.askCardRef}
        askInteraction={askInteraction}
        bottomSentinelRef={focusScrollRuntime.bottomSentinelRef}
        className={styles.conversationWorkspace}
        headerActions={conversationHeaderActions}
        messageListRef={focusScrollRuntime.messageListRef}
        messages={conversationMessages}
        onMessageListScroll={focusScrollRuntime.onMessageListScroll}
        onOpenActivity={hasActivity ? openActivityOverlay : undefined}
        rootRef={focusScrollRuntime.conversationRootRef}
        totalActivityCount={totalActivityCount}
      />

      {isPlanLayerExpanded && planProgressLayer ? (
        <Panel
          as="section"
          className={`${styles.workspace} ${styles.planWorkspace}`}
          aria-label={uiText.main.detail.labels.planProgressWorkspace}
        >
          {renderWorkspaceHeader(collapsePlanAction, archivePlanAction)}
          <div className={styles.planProgressWorkspaceBody}>
            {planProgressLayer}
          </div>
        </Panel>
      ) : null}

      {!hasPlanLayer && selectedArchivedPlan !== null ? (
        <Panel
          as="section"
          className={`${styles.workspace} ${styles.planWorkspace}`}
          aria-label={uiText.main.detail.labels.archivedPlanProgressWorkspace}
        >
          {renderWorkspaceHeader(
            <button
              className={styles.planProgressCollapseButton}
              onClick={closeArchivedPlanAndReturnFocus}
              type="button"
            >
              {uiText.main.detail.actions.backToConversation}
            </button>,
            null,
            uiText.main.detail.labels.planProgress,
          )}
          <div className={styles.planProgressWorkspaceBody}>
            {archivedPlanProgressLayer ?? (
              <TaskTreePanel
                isTaskPlanSelected
                onRetryTask={() => undefined}
                onSelectTaskPlan={() => undefined}
                onSelectTask={() => undefined}
                onStopTask={() => undefined}
                selectedTaskNodeId={null}
                taskTree={null}
              />
            )}
          </div>
        </Panel>
      ) : null}

      {hasDetailColumn ? (
        <button
          aria-label={uiText.main.detail.labels.resizeDetailsPanel}
          aria-orientation="vertical"
          aria-valuemax={MAX_DETAIL_WIDTH}
          aria-valuemin={MIN_DETAIL_WIDTH}
          aria-valuenow={detailWidth}
          className={styles.detailSplitter}
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft") {
              event.preventDefault();
              resizeDetailPanel(detailWidth + DETAIL_RESIZE_STEP);
            }
            if (event.key === "ArrowRight") {
              event.preventDefault();
              resizeDetailPanel(detailWidth - DETAIL_RESIZE_STEP);
            }
            if (event.key === "Home") {
              event.preventDefault();
              resizeDetailPanel(MIN_DETAIL_WIDTH);
            }
            if (event.key === "End") {
              event.preventDefault();
              resizeDetailPanel(MAX_DETAIL_WIDTH);
            }
          }}
          onPointerDown={startDetailResize}
          role="separator"
          type="button"
        />
      ) : null}

      {showsDetailPanel ? (
        <MainPageDetailPanel
          detail={viewModel.detail}
          detailFocusRef={focusScrollRuntime.detailPanelRef}
          fileChangesFocusRef={focusScrollRuntime.fileChangesRef}
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
          onFocusExecutionAsk={() => {
            setIsPlanLayerExpanded(false);
            window.setTimeout(() => {
              scrollTargetIntoView("ask_card", "route_restored");
              focusTarget("ask_card", "route_restored");
            }, 0);
          }}
          onRetryTask={(taskNodeId) =>
            actions.retryTask({
              sessionId: viewModel.sessionId,
              taskNodeId,
            })
          }
          onStopTask={(taskNodeId) =>
            actions.stopTask({
              sessionId: viewModel.sessionId,
              taskNodeId,
            })
          }
          onShowFileChanges={actions.showFileChanges}
          onShowResult={actions.showResult}
          loadTokenUsageSummary={loadTokenUsageSummary}
          sessionId={viewModel.sessionId}
          workspaceId={resolvedWorkspaceId}
        />
      ) : null}

      {showsArchivedPlanDetailPanel ? (
        <MainPageDetailPanel
          detail={archivedPlanDetail}
          detailFocusRef={focusScrollRuntime.detailPanelRef}
          fileChangesFocusRef={focusScrollRuntime.fileChangesRef}
          onConfirmationDecision={() => undefined}
          onFocusExecutionAsk={() => undefined}
          onRetryTask={() => undefined}
          onStopTask={() => undefined}
          onShowFileChanges={actions.showFileChanges}
          onShowResult={actions.showResult}
          loadTokenUsageSummary={loadTokenUsageSummary}
          sessionId={viewModel.sessionId}
          workspaceId={resolvedWorkspaceId}
        />
      ) : null}

      {showsActivityPanel ? (
        <ActivityOverlay
          errorMessage={activityError}
          isLoading={isActivityLoading}
          items={overlayActivityItems}
          onClose={closeOverlayAndReturnFocus}
          onOpenAudit={
            viewModel.workspace.auditEntry.isEnabled
              ? showActivityAudit
              : undefined
          }
          onOpenDiagnostic={
            exportDiagnosticBundle === undefined
              ? undefined
              : () => {
                  void exportActivityDiagnostic();
                }
          }
          onOpenFiles={showActivityFiles}
          onOpenPlan={() => {
            actions.selectTaskPlan();
            setIsActivityOverlayOpen(false);
            setIsArchivedPlansPanelOpen(false);
            setSelectedArchivedPlanId(null);
            setSelectedArchivedPlanTaskNodeId(null);
          }}
          onOpenResult={showActivityResult}
          onOpenTask={(taskNodeId) => {
            actions.selectTask(taskNodeId);
            setIsActivityOverlayOpen(false);
            setIsArchivedPlansPanelOpen(false);
            setSelectedArchivedPlanId(null);
            setSelectedArchivedPlanTaskNodeId(null);
            window.setTimeout(() => {
              focusScrollRuntime.scrollTargetIntoView(
                "selected_task",
                "overlay_closed",
              );
              focusScrollRuntime.focusTarget("selected_task", "overlay_closed");
            }, 0);
          }}
          onRetry={() => setActivityLoadKey((key) => key + 1)}
          selectedActivityItemId={selectedActivityItemId}
          selectedActivityItemRef={focusScrollRuntime.selectedActivityItemRef}
          selectedTask={viewModel.taskWorkspace.selectedTask}
          statusMessage={activityStatusMessage}
        />
      ) : null}

      {showsArchivedPlansPanel ? (
        <ArchivedPlansPanel
          auditHref={viewModel.workspace.auditEntry.href}
          items={archivedPlans}
          onClose={closeOverlayAndReturnFocus}
          onOpenPlan={(planId) => {
            setSelectedArchivedPlanId(planId);
            setSelectedArchivedPlanTaskNodeId(null);
            setIsArchivedPlansPanelOpen(false);
          }}
        />
      ) : null}

      <ConfirmationDock
        confirmations={viewModel.pendingConfirmations}
        error={viewModel.confirmationError}
        isResolving={viewModel.isResolvingConfirmation}
        onResolve={(confirmation, decision) =>
          actions.resolveConfirmation({
            confirmation,
            decision,
            sessionId: viewModel.sessionId,
          })
        }
      />

      <ContextInputPanel
        draft={inputDraft}
        error={inputError}
        input={viewModel.input}
        inputRef={contextInputRef}
        isSubmitting={isInputSubmitting}
        isRecoveryActionEnabled={isSettingsRecoveryAction}
        recoveryActions={inputRecoveryActions}
        onDraftChange={actions.changeInputDraft}
        onRecoveryAction={handleInputRecoveryAction}
        onSubmit={() => {
          const commandId = actions.submitInput({
            mode: viewModel.input.mode,
            sessionId: viewModel.sessionId,
            target: viewModel.input.target,
            taskNodeId: viewModel.input.taskNodeId,
          });
          if (commandId !== null) {
            focusScrollRuntime.notifyRuntimeInputSubmitStarted(commandId);
          }
        }}
      />
    </main>
  );
}

function handleInputRecoveryAction(action: ProductRecoveryAction) {
  if (!isSettingsRecoveryAction(action)) {
    return;
  }
  navigateApp(buildSettingsRoute());
}

function isSettingsRecoveryAction(action: ProductRecoveryAction): boolean {
  return SETTINGS_RECOVERY_ACTIONS.has(action);
}

function mergeActivityItems(
  transientItems: readonly SessionActivityItemView[],
  sourceItems: readonly SessionActivityItemView[],
): SessionActivityItemView[] {
  const byId = new Set<string>();
  const sourceDedupKeys = new Set(
    sourceItems
      .map(activityDedupKey)
      .filter((key): key is string => key !== null),
  );
  const merged: SessionActivityItemView[] = [];

  for (const item of transientItems) {
    const dedupKey = activityDedupKey(item);
    if (dedupKey !== null && sourceDedupKeys.has(dedupKey)) {
      continue;
    }
    if (byId.has(item.id)) {
      continue;
    }
    byId.add(item.id);
    merged.push(item);
  }

  for (const item of sourceItems) {
    if (byId.has(item.id)) {
      continue;
    }
    byId.add(item.id);
    merged.push(item);
  }

  return merged;
}

function mergeMessages(
  sourceMessages: readonly SessionMessageView[],
  transientMessages: readonly SessionMessageView[],
): SessionMessageView[] {
  const byId = new Set<string>();
  const sourceDedupKeys = new Set(
    sourceMessages
      .map(messageDedupKey)
      .filter((key): key is string => key !== null),
  );
  const merged: SessionMessageView[] = [];

  for (const message of sourceMessages) {
    if (byId.has(message.id)) {
      continue;
    }
    byId.add(message.id);
    merged.push(message);
  }

  for (const message of transientMessages) {
    const dedupKey = messageDedupKey(message);
    if (dedupKey !== null && sourceDedupKeys.has(dedupKey)) {
      continue;
    }
    if (byId.has(message.id)) {
      continue;
    }
    byId.add(message.id);
    merged.push(message);
  }

  return merged;
}

function messageFromActivityItem(
  item: SessionActivityItemView,
): SessionMessageView {
  return {
    id: `activity-message:${item.id}`,
    sessionId: item.sessionId,
    taskNodeId: item.taskNodeId ?? null,
    kind: messageKindFromActivity(item),
    title: item.title,
    body: item.body,
    createdAt: item.occurredAt,
    relatedCommandId:
      item.sourceKind === "router" && item.sourceId ? item.sourceId : null,
    activityRelatedRefs: item.relatedRefs,
  };
}

function activityDedupKey(item: SessionActivityItemView): string | null {
  if (item.sourceKind !== "router" || !item.sourceId) {
    return null;
  }

  return routeScopedDedupKey(
    item.sourceId,
    item.kind,
    item.scopeKind,
    item.planId ?? null,
    item.taskNodeId ?? null,
  );
}

function messageDedupKey(message: SessionMessageView): string | null {
  if (!message.relatedCommandId) {
    return null;
  }

  return routeScopedDedupKey(
    message.relatedCommandId,
    messageRouteKind(message),
    message.taskNodeId === null ? "session" : "task",
    null,
    message.taskNodeId,
  );
}

function routeScopedDedupKey(
  commandId: string,
  kind: string,
  scopeKind: string,
  planId: string | null,
  taskNodeId: string | null,
): string {
  return [
    "router",
    commandId,
    kind,
    scopeKind,
    planId ?? "",
    taskNodeId ?? "",
  ].join(":");
}

function messageRouteKind(message: SessionMessageView): string {
  const title = message.title.trim().toLocaleLowerCase();

  if (title === "read-only question answered" || title === "read-only answer") {
    return "answer";
  }
  if (title === "user input") {
    return "user_input";
  }
  if (title === "router interpretation") {
    return "router_interpretation";
  }

  return `${message.kind}:${title}`;
}

function messageKindFromActivity(
  item: SessionActivityItemView,
): SessionMessageView["kind"] {
  if (item.kind === "answer" || item.kind === "result_ready") {
    return "response";
  }
  if (item.kind === "recovery_note") {
    return "error";
  }
  if (
    item.kind === "ask_asked" ||
    item.kind === "confirmation_requested" ||
    item.sideEffect !== "no_effect"
  ) {
    return "actionable";
  }
  return "informational";
}

function clampDetailWidth(width: number): number {
  return Math.min(MAX_DETAIL_WIDTH, Math.max(MIN_DETAIL_WIDTH, width));
}

function isArchiveablePlanStatus(status: string): boolean {
  return (
    status === "ready_for_review" ||
    status === "accepted" ||
    status === "follow_up_needed" ||
    status === "failed" ||
    status === "cancelled"
  );
}

function canArchivePlan(plan: PlanView): boolean {
  if (!isArchiveablePlanStatus(plan.status)) {
    return false;
  }
  return (
    plan.sourceKind === "plan_store" ||
    plan.sourceKind === "legacy_published_task_tree"
  );
}

function archivedPlanDetailView(
  plan: PlanView,
  selectedTaskNodeId: TaskNodeId | null,
): MainPageDetailView {
  const taskTree = plan.taskTreeProjection;
  if (taskTree === null || taskTree === undefined) {
    return {
      body: "Archived plan details are unavailable.",
      header: {
        body: plan.summary,
        eyebrow: "PLAN",
        title: plan.title,
      },
      kind: "note",
    };
  }

  const selectedTask =
    selectedTaskNodeId === null
      ? undefined
      : taskTree.nodes.find((node) => node.id === selectedTaskNodeId);

  if (selectedTask !== undefined) {
    return {
      header: {
        body: selectedTask.summary,
        eyebrow: "TASK",
        title: selectedTask.title,
      },
      isRetryingTask: false,
      isStoppingTask: false,
      kind: "task",
      selectedTask,
    };
  }

  return {
    header: {
      body: plan.summary,
      eyebrow: "PLAN",
      title: plan.title,
    },
    kind: "plan",
    taskTree,
  };
}
