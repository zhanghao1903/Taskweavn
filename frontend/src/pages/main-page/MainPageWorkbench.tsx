import {
  useEffect,
  useMemo,
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
import { AuthoringAskWorkArea } from "./interaction/AuthoringAskWorkArea";
import { activityItemsFromMessages } from "./mainPageActivityProjection";
import type { MainPageViewModel } from "./mainPageViewModel";
import type { MainPageController } from "./useMainPageController";
import type {
  ExportDiagnosticBundle,
  LoadSessionActivity,
  LoadTokenUsageSummary,
} from "./runtime/adapter";
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
}: MainPageWorkbenchProps) {
  const uiText = useUiText();
  const [isActivityOverlayOpen, setIsActivityOverlayOpen] = useState(false);
  const [isArchivedPlansPanelOpen, setIsArchivedPlansPanelOpen] =
    useState(false);
  const [activityItems, setActivityItems] = useState<
    SessionActivityItemView[]
  >([]);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [activityLoadKey, setActivityLoadKey] = useState(0);
  const [isActivityLoading, setIsActivityLoading] = useState(false);
  const hasPlanLayer =
    viewModel.taskWorkspace.taskTree !== null ||
    viewModel.taskWorkspace.isGeneratingTaskPlan;
  const [isPlanLayerExpanded, setIsPlanLayerExpanded] =
    useState(hasPlanLayer);
  const [activityStatusMessage, setActivityStatusMessage] =
    useState<ActivityOverlayStatusMessage | null>(null);
  const [isExportingActivityDiagnostic, setIsExportingActivityDiagnostic] =
    useState(false);
  const [detailWidth, setDetailWidth] = useState(DEFAULT_DETAIL_WIDTH);
  const hasActivity =
    viewModel.mainWorkArea.kind !== "authoringAsk" &&
    (viewModel.taskWorkspace.allMessages.length > 0 ||
      runtimeActivityItems.length > 0 ||
      loadSessionActivity !== undefined);
  const showsActivityPanel = isActivityOverlayOpen && hasActivity;
  const fallbackActivityItems = useMemo(
    () => activityItemsFromMessages(viewModel.taskWorkspace.allMessages),
    [viewModel.taskWorkspace.allMessages],
  );
  const archivedPlanItems = useMemo(
    () =>
      selectArchivedPlanItems(
        mergeActivityItems(
          runtimeActivityItems,
          mergeActivityItems(activityItems, fallbackActivityItems),
        ),
      ),
    [activityItems, fallbackActivityItems, runtimeActivityItems],
  );
  const showsArchivedPlansPanel =
    isArchivedPlansPanelOpen && archivedPlanItems.length > 0;
  const hasDetailColumn =
    viewModel.detail.kind !== "note" ||
    showsActivityPanel ||
    showsArchivedPlansPanel;
  const showsDetailPanel =
    viewModel.detail.kind !== "note" &&
    !showsActivityPanel &&
    !showsArchivedPlansPanel;
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
  const resolvedWorkspaceId =
    viewModel.workspace.workspaceId ??
    viewModel.sidebar.activeSession.workspaceId ??
    activeWorkspaceId ??
    null;
  const overlayActivityItems =
    loadSessionActivity === undefined
      ? mergeActivityItems(runtimeActivityItems, fallbackActivityItems)
      : mergeActivityItems(runtimeActivityItems, activityItems);
  const conversationMessages = useMemo(
    () =>
      mergeMessages(
        viewModel.taskWorkspace.allMessages,
        transientMessages,
      ),
    [transientMessages, viewModel.taskWorkspace.allMessages],
  );
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
    setIsActivityOverlayOpen(false);
    setIsArchivedPlansPanelOpen(false);
  }, [hasPlanLayer, viewModel.sessionId]);

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

  function showActivityResult(taskNodeId: string | null) {
    if (taskNodeId !== null) {
      actions.selectTask(taskNodeId);
    }
    actions.showResult();
    setIsActivityOverlayOpen(false);
    setIsArchivedPlansPanelOpen(false);
  }

  function showActivityFiles(taskNodeId: string | null) {
    if (taskNodeId !== null) {
      actions.selectTask(taskNodeId);
    }
    actions.showFileChanges();
    setIsActivityOverlayOpen(false);
    setIsArchivedPlansPanelOpen(false);
  }

  function showActivityAudit(ref: SessionActivityRefView) {
    const href = ref.href ?? viewModel.workspace.auditEntry.href;
    window.location.assign(href);
    setIsActivityOverlayOpen(false);
    setIsArchivedPlansPanelOpen(false);
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
              hasActivity
                ? () => {
                    setIsArchivedPlansPanelOpen(false);
                    setIsActivityOverlayOpen(true);
                  }
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
      selectedTaskNodeId={viewModel.taskWorkspace.selectedTaskNodeId}
      isGeneratingTaskPlan={viewModel.taskWorkspace.isGeneratingTaskPlan}
      taskTree={viewModel.taskWorkspace.taskTree}
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
    archivedPlanItems.length > 0;
  const conversationPlanAction = showConversationPlanEntry ? (
    <Button
      aria-label="Open archived plan from Conversation"
      onClick={() => {
        setIsActivityOverlayOpen(false);
        setIsArchivedPlansPanelOpen(true);
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
        title={viewModel.workspace.title}
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
          className={styles.conversationWorkspace}
          headerActions={conversationHeaderActions}
          messages={conversationMessages}
          onOpenActivity={
            hasActivity
              ? () => {
                  setIsArchivedPlansPanelOpen(false);
                  setIsActivityOverlayOpen(true);
                }
              : undefined
          }
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

      {showsActivityPanel ? (
        <ActivityOverlay
          errorMessage={activityError}
          isLoading={isActivityLoading}
          items={overlayActivityItems}
          onClose={() => {
            setIsActivityOverlayOpen(false);
          }}
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
          }}
          onOpenResult={showActivityResult}
          onOpenTask={(taskNodeId) => {
            actions.selectTask(taskNodeId);
            setIsActivityOverlayOpen(false);
            setIsArchivedPlansPanelOpen(false);
          }}
          onRetry={() => setActivityLoadKey((key) => key + 1)}
          selectedTask={viewModel.taskWorkspace.selectedTask}
          statusMessage={activityStatusMessage}
        />
      ) : null}

      {showsArchivedPlansPanel ? (
        <ArchivedPlansPanel
          auditHref={viewModel.workspace.auditEntry.href}
          items={archivedPlanItems}
          onClose={() => setIsArchivedPlansPanelOpen(false)}
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
        isSubmitting={isInputSubmitting}
        recoveryActions={inputRecoveryActions}
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

function selectArchivedPlanItems(
  items: readonly SessionActivityItemView[],
): SessionActivityItemView[] {
  return items.filter(
    (item) =>
      item.kind === "plan_updated" &&
      item.title.trim().toLocaleLowerCase() === "plan archived",
  );
}
