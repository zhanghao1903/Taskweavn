import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent,
  type ReactNode,
} from "react";

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
import { ActivityOverlay } from "./ActivityOverlay";
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
import { AuthoringAskWorkArea } from "./interaction/AuthoringAskWorkArea";
import { activityItemsFromMessages } from "./mainPageActivityProjection";
import type {
  MainPageDetailView,
  MainPageViewModel,
} from "./mainPageViewModel";
import { useMainPageFocusScrollRuntime } from "./useMainPageFocusScrollRuntime";
import {
  newestActivityItemId,
  useMainPageOverlayRuntime,
} from "./useMainPageOverlayRuntime";
import type { MainPageController } from "./useMainPageController";
import type {
  ExportDiagnosticBundle,
  LoadSessionActivity,
  LoadTokenUsageSummary,
} from "./runtime/adapter";
import type { MainPageFocusTarget } from "./runtime/mainPageFocusScrollRuntime";
import styles from "./MainPage.module.css";

const DEFAULT_DETAIL_WIDTH = 380;
const MIN_DETAIL_WIDTH = 320;
const MAX_DETAIL_WIDTH = 680;
const DETAIL_RESIZE_STEP = 24;

export type MainPageWorkbenchProps = {
  actions: MainPageController["actions"];
  activeWorkspaceId: MainPageController["activeWorkspaceId"];
  inputDraft: string;
  inputError: string | null;
  inputRecoveryActions: ProductRecoveryAction[];
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
  routeFocusTarget?: MainPageFocusTarget | null;
};

export function MainPageWorkbench({
  actions,
  activeWorkspaceId,
  inputDraft,
  inputError,
  inputRecoveryActions,
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
  const hasPlanLayer =
    viewModel.taskWorkspace.taskTree !== null ||
    viewModel.taskWorkspace.isGeneratingTaskPlan;
  const [isPlanLayerExpanded, setIsPlanLayerExpanded] =
    useState(hasPlanLayer);
  const [detailWidth, setDetailWidth] = useState(DEFAULT_DETAIL_WIDTH);
  const hasActivity =
    viewModel.mainWorkArea.kind !== "authoringAsk" &&
    (viewModel.taskWorkspace.allMessages.length > 0 ||
      runtimeActivityItems.length > 0 ||
      loadSessionActivity !== undefined);
  const fallbackActivityItems = useMemo(
    () => activityItemsFromMessages(viewModel.taskWorkspace.allMessages),
    [viewModel.taskWorkspace.allMessages],
  );
  const archivedPlans = viewModel.taskWorkspace.archivedPlans;
  const archivedPlanIds = useMemo(
    () => archivedPlans.map((plan) => plan.id),
    [archivedPlans],
  );
  const resolvedWorkspaceId =
    viewModel.workspace.workspaceId ??
    viewModel.sidebar.activeSession.workspaceId ??
    activeWorkspaceId ??
    null;
  const overlayRuntime = useMainPageOverlayRuntime({
    archivedPlanIds,
    loadActivityErrorMessage: uiText.main.activity.descriptions.loadError,
    loadSessionActivity,
    resolvedWorkspaceId,
    sessionId: viewModel.sessionId,
  });
  const overlayState = overlayRuntime.state;
  const showsActivityPanel =
    overlayState.activeOverlay === "activity" && hasActivity;
  const selectedArchivedPlan =
    archivedPlans.find((plan) => plan.id === overlayState.selectedArchivedPlanId) ??
    null;
  const archivedPlanDetail =
    selectedArchivedPlan?.taskTreeProjection
      ? archivedPlanDetailView(
          selectedArchivedPlan,
          overlayState.selectedArchivedPlanTaskNodeId,
        )
      : null;
  const showsArchivedPlansPanel =
    overlayState.activeOverlay === "archived_plans" && archivedPlans.length > 0;
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
  const visibleTransientMessages = useMemo(
    () =>
      transientMessages.filter((message) =>
        viewModel.taskWorkspace.selectedTask
          ? message.taskNodeId === viewModel.taskWorkspace.selectedTask.id
          : true,
      ),
    [transientMessages, viewModel.taskWorkspace.selectedTask],
  );
  const hasVisibleActivity =
    viewModel.mainWorkArea.kind !== "authoringAsk" &&
    (viewModel.taskWorkspace.messages.length > 0 ||
      visibleTransientMessages.length > 0);
  const overlayActivityItems =
    loadSessionActivity === undefined
      ? mergeActivityItems(runtimeActivityItems, fallbackActivityItems)
      : mergeActivityItems(runtimeActivityItems, overlayState.activityItems);
  const selectedActivityItemId =
    overlayState.selectedActivityItemId ??
    newestActivityItemId(
      overlayActivityItems,
      viewModel.taskWorkspace.selectedTask?.id ?? null,
    );
  const conversationMessages = useMemo(
    () =>
      mergeMessages(
        viewModel.taskWorkspace.allMessages,
        transientMessages,
      ),
    [transientMessages, viewModel.taskWorkspace.allMessages],
  );
  const focusScrollRuntime = useMainPageFocusScrollRuntime({
    conversationMessageCount: conversationMessages.length,
    inputDisabled: viewModel.input.disabled,
  });
  const handledRouteFocusRequestRef = useRef<string | null>(null);
  const showFileChangesRef = useRef(actions.showFileChanges);
  const previousInputSubmittingRef = useRef(isInputSubmitting);
  const [composerFocusRequestCount, setComposerFocusRequestCount] = useState(0);
  const activeAskFocusIdentity =
    viewModel.mainWorkArea.kind === "authoringAsk"
      ? `authoring:${viewModel.mainWorkArea.authoringAsk.rawTaskId}`
      : viewModel.detail.kind === "executionAsk"
        ? `execution:${viewModel.detail.ask.id}`
        : null;
  const latestActivityMessages = useMemo(
    () =>
      mergeMessages(
        viewModel.taskWorkspace.messages,
        visibleTransientMessages,
      ),
    [viewModel.taskWorkspace.messages, visibleTransientMessages],
  );
  const totalActivityCount = conversationMessages.length;
  const visibleActivityCount = latestActivityMessages.length;
  const collapsedPlanTitle =
    viewModel.taskWorkspace.taskTree?.title ?? viewModel.workspace.title;
  const collapsedPlanMeta =
    viewModel.taskWorkspace.taskTree !== null
      ? `${viewModel.taskWorkspace.taskTree.nodes.length} tasks · ${viewModel.taskWorkspace.taskTree.status}`
      : "Generating plan";
  const activePlan = viewModel.taskWorkspace.activePlan;
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
        {isArchivingPlan ? "Archiving..." : "Archive plan"}
      </Button>
    ) : null;

  useEffect(() => {
    setIsPlanLayerExpanded(hasPlanLayer);
  }, [hasPlanLayer, viewModel.sessionId]);

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
        focusScrollRuntime.focusContextInput("route_restored");
        return;
      }

      if (routeFocusTarget === "ask_card") {
        focusScrollRuntime.scrollTargetIntoView("ask_card", "route_restored");
        focusScrollRuntime.focusTarget("ask_card", "route_restored");
        return;
      }

      if (routeFocusTarget === "conversation") {
        focusScrollRuntime.scrollTargetIntoView(
          "conversation",
          "route_restored",
        );
        focusScrollRuntime.focusTarget("conversation", "route_restored");
        return;
      }

      if (routeFocusTarget === "detail_panel") {
        focusScrollRuntime.scrollTargetIntoView(
          "detail_panel",
          "route_restored",
        );
        focusScrollRuntime.focusTarget("detail_panel", "route_restored");
        return;
      }

      if (routeFocusTarget === "file_changes") {
        focusScrollRuntime.scrollTargetIntoView(
          "file_changes",
          "route_restored",
        );
        focusScrollRuntime.focusTarget("file_changes", "route_restored");
        return;
      }

      if (
        routeFocusTarget === "selected_task" &&
        viewModel.taskWorkspace.selectedTaskNodeId !== null
      ) {
        focusScrollRuntime.scrollTargetIntoView(
          "selected_task",
          "route_restored",
        );
        focusScrollRuntime.focusTarget("selected_task", "route_restored");
      }
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [
    focusScrollRuntime,
    routeFocusTarget,
    viewModel.sessionId,
    viewModel.taskWorkspace.selectedTaskNodeId,
  ]);

  useEffect(() => {
    if (activeAskFocusIdentity === null) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      focusScrollRuntime.scrollTargetIntoView("ask_card", "ask_presented");
      focusScrollRuntime.focusTarget("ask_card", "ask_presented");
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [activeAskFocusIdentity, focusScrollRuntime]);

  useEffect(() => {
    if (composerFocusRequestCount === 0) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      focusScrollRuntime.focusContextInput("input_submitted");
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [composerFocusRequestCount, focusScrollRuntime]);

  useEffect(() => {
    const previousIsInputSubmitting = previousInputSubmittingRef.current;
    previousInputSubmittingRef.current = isInputSubmitting;

    if (!previousIsInputSubmitting && !isInputSubmitting) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      focusScrollRuntime.focusContextInput("input_submitted");
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [focusScrollRuntime, isInputSubmitting]);

  useEffect(() => {
    if (!showsActivityPanel || selectedActivityItemId === null) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      focusScrollRuntime.scrollTargetIntoView(
        "selected_activity",
        "overlay_opened",
      );
      focusScrollRuntime.focusTarget("selected_activity", "overlay_opened");
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [
    focusScrollRuntime,
    selectedActivityItemId,
    showsActivityPanel,
    overlayActivityItems.length,
  ]);

  function openActivityOverlay(
    trigger: HTMLElement | null = null,
    selectedItemId = selectedActivityItemId,
  ) {
    if (trigger) {
      focusScrollRuntime.captureOverlayTriggerElement(trigger);
    } else {
      focusScrollRuntime.captureOverlayTrigger();
    }
    overlayRuntime.actions.openActivity(selectedItemId);
  }

  function closeOverlayAndReturnFocus() {
    overlayRuntime.actions.closeOverlay();
    window.setTimeout(() => {
      focusScrollRuntime.focusTarget("overlay_trigger", "overlay_closed");
    }, 0);
  }

  function closeOverlay() {
    overlayRuntime.actions.closeOverlay();
  }

  function showActivityResult(taskNodeId: string | null) {
    if (taskNodeId !== null) {
      actions.selectTask(taskNodeId);
    }
    actions.showResult();
    closeOverlay();
  }

  function showActivityFiles(taskNodeId: string | null) {
    if (taskNodeId !== null) {
      actions.selectTask(taskNodeId);
    }
    actions.showFileChanges();
    closeOverlay();
  }

  function showActivityAudit(ref: SessionActivityRefView) {
    const href = ref.href ?? viewModel.workspace.auditEntry.href;
    window.location.assign(href);
    closeOverlay();
  }

  async function exportActivityDiagnostic() {
    if (
      exportDiagnosticBundle === undefined ||
      overlayState.isExportingActivityDiagnostic
    ) {
      return;
    }

    overlayRuntime.actions.startDiagnosticExport(
      uiText.settings.actions.exportingDiagnostics,
    );

    try {
      const result = await exportDiagnosticBundle(
        viewModel.sessionId,
        resolvedWorkspaceId,
      );
      overlayRuntime.actions.succeedDiagnosticExport(
        `${uiText.diagnostics.labels.bundleReady}: ${result.bundleId}`,
      );
    } catch {
      overlayRuntime.actions.failDiagnosticExport(
        uiText.settings.messages.diagnosticExportFailed,
      );
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
              hasActivity
                ? (trigger) => openActivityOverlay(trigger)
                : undefined
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
        isTaskPlanSelected={
          overlayState.selectedArchivedPlanTaskNodeId === null
        }
        onRetryTask={() => undefined}
        onSelectTaskPlan={overlayRuntime.actions.selectArchivedPlanOverview}
        onSelectTask={overlayRuntime.actions.selectArchivedPlanTask}
        onStopTask={() => undefined}
        selectedTaskNodeId={overlayState.selectedArchivedPlanTaskNodeId}
        taskTree={selectedArchivedPlan.taskTreeProjection}
      />
    ) : null;
  const collapsePlanAction = (
    <button
      className={styles.planProgressCollapseButton}
      onClick={() => setIsPlanLayerExpanded(false)}
      type="button"
    >
      Collapse
    </button>
  );
  const collapsedPlanTopbarAction =
    hasPlanLayer && !isPlanLayerExpanded ? (
      <button
        aria-label={`Open Plan & Progress: ${collapsedPlanTitle}`}
        className={styles.collapsedPlanTopbarButton}
        onClick={() => setIsPlanLayerExpanded(true)}
        type="button"
      >
        <span className={styles.collapsedPlanTopbarLabel}>Plan</span>
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
      aria-label="Open archived plan from Conversation"
      onClick={(event) => {
        focusScrollRuntime.captureOverlayTriggerElement(event.currentTarget);
        overlayRuntime.actions.openArchivedPlans();
      }}
      size="sm"
      variant="secondary"
    >
      Plan
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

      {viewModel.mainWorkArea.kind !== "authoringAsk" ? (
        <ConversationLayer
          bottomAnchorRef={focusScrollRuntime.conversationBottomAnchorRef}
          className={styles.conversationWorkspace}
          headerActions={conversationHeaderActions}
          messageListRef={focusScrollRuntime.conversationMessageListRef}
          messages={conversationMessages}
          onMessageListScroll={focusScrollRuntime.onConversationScroll}
          onOpenActivity={
            hasActivity
              ? (trigger) => openActivityOverlay(trigger)
              : undefined
          }
          rootRef={focusScrollRuntime.conversationRootRef}
          totalActivityCount={totalActivityCount}
        />
      ) : null}

      {viewModel.mainWorkArea.kind === "authoringAsk" ? (
        <Panel
          as="section"
          className={styles.workspace}
          aria-label={uiText.main.labels.taskWorkspace}
        >
          {renderWorkspaceHeader()}
          <AuthoringAskWorkArea
            focusRef={focusScrollRuntime.askCardRef}
            onSubmit={({ answers, rawTaskId }) =>
              actions.answerAuthoringAskBatch({
                answers,
                rawTaskId,
                sessionId: viewModel.sessionId,
              })
            }
            view={viewModel.mainWorkArea.authoringAsk}
          />
        </Panel>
      ) : isPlanLayerExpanded && planProgressLayer ? (
        <Panel
          as="section"
          className={`${styles.workspace} ${styles.planWorkspace}`}
          aria-label="Plan & Progress workspace"
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
          aria-label="Archived Plan & Progress workspace"
        >
          {renderWorkspaceHeader(
            <button
              className={styles.planProgressCollapseButton}
              onClick={closeOverlayAndReturnFocus}
              type="button"
            >
              Back to conversation
            </button>,
            null,
            "Plan & Progress",
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
          aria-label="Resize details panel"
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
          executionAskFocusRef={focusScrollRuntime.askCardRef}
          fileChangesFocusRef={focusScrollRuntime.fileChangesRef}
          onAnswerAsk={(payload) => {
            if (viewModel.detail.kind !== "executionAsk") {
              return;
            }

            actions.answerAsk({
              askId: viewModel.detail.ask.id,
              selectedOptionIds: payload.selectedOptionIds,
              sessionId: viewModel.sessionId,
              text: payload.text,
            });
          }}
          onCancelAsk={(payload) => {
            if (viewModel.detail.kind !== "executionAsk") {
              return;
            }

            actions.cancelAsk({
              askId: viewModel.detail.ask.id,
              reason: payload.reason,
              sessionId: viewModel.sessionId,
            });
          }}
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
          onDeferAsk={(payload) => {
            if (viewModel.detail.kind !== "executionAsk") {
              return;
            }

            actions.deferAsk({
              askId: viewModel.detail.ask.id,
              reason: payload.reason,
              sessionId: viewModel.sessionId,
            });
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
          onAnswerAsk={() => undefined}
          onCancelAsk={() => undefined}
          onConfirmationDecision={() => undefined}
          onDeferAsk={() => undefined}
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
          errorMessage={overlayState.activityError}
          isLoading={overlayState.isActivityLoading}
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
            closeOverlay();
          }}
          onOpenResult={showActivityResult}
          onOpenTask={(taskNodeId) => {
            actions.selectTask(taskNodeId);
            closeOverlay();
            window.setTimeout(() => {
              focusScrollRuntime.scrollTargetIntoView(
                "selected_task",
                "overlay_closed",
              );
              focusScrollRuntime.focusTarget("selected_task", "overlay_closed");
            }, 0);
          }}
          onRetry={overlayRuntime.actions.retryActivity}
          selectedActivityItemId={selectedActivityItemId}
          selectedActivityItemRef={focusScrollRuntime.selectedActivityItemRef}
          selectedTask={viewModel.taskWorkspace.selectedTask}
          statusMessage={overlayState.activityStatusMessage}
        />
      ) : null}

      {showsArchivedPlansPanel ? (
        <ArchivedPlansPanel
          auditHref={viewModel.workspace.auditEntry.href}
          items={archivedPlans}
          onClose={closeOverlayAndReturnFocus}
          onOpenPlan={overlayRuntime.actions.openArchivedPlan}
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
        inputRef={focusScrollRuntime.contextInputRef}
        isSubmitting={isInputSubmitting}
        recoveryActions={inputRecoveryActions}
        onDraftChange={actions.changeInputDraft}
        onSubmit={() => {
          setComposerFocusRequestCount((count) => count + 1);
          actions.submitInput({
            mode: viewModel.input.mode,
            sessionId: viewModel.sessionId,
            target: viewModel.input.target,
            taskNodeId: viewModel.input.taskNodeId,
          });
        }}
      />
    </main>
  );
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
