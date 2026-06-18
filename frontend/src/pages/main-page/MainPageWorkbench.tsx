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
  SessionActivityItemView,
  SessionActivityRefView,
  SessionMessageView,
} from "../../shared/api/types";
import { Panel } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import {
  ActivityOverlay,
  type ActivityOverlayStatusMessage,
} from "./ActivityOverlay";
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
  const hidesDetailPanel = viewModel.detail.kind === "note";
  const pageClassName = hidesDetailPanel
    ? `${styles.page} ${styles.pageWithoutDetail}`
    : styles.page;
  const pageStyle = {
    "--plato-detail-width": `${detailWidth}px`,
  } as CSSProperties;
  const hasActivity =
    viewModel.mainWorkArea.kind !== "authoringAsk" &&
    (viewModel.taskWorkspace.allMessages.length > 0 ||
      runtimeActivityItems.length > 0 ||
      loadSessionActivity !== undefined);
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
  const fallbackActivityItems = useMemo(
    () => activityItemsFromMessages(viewModel.taskWorkspace.allMessages),
    [viewModel.taskWorkspace.allMessages],
  );
  const overlayActivityItems =
    loadSessionActivity === undefined
      ? mergeActivityItems(runtimeActivityItems, fallbackActivityItems)
      : mergeActivityItems(runtimeActivityItems, activityItems);
  const latestActivityMessages = [
    ...viewModel.taskWorkspace.messages,
    ...visibleTransientMessages,
  ];
  const conversationMessages = useMemo(
    () =>
      mergeMessages(
        viewModel.taskWorkspace.allMessages,
        transientMessages,
      ),
    [transientMessages, viewModel.taskWorkspace.allMessages],
  );
  const totalActivityCount =
    viewModel.taskWorkspace.totalMessageCount + transientMessages.length;
  const visibleActivityCount =
    viewModel.taskWorkspace.visibleMessageCount + visibleTransientMessages.length;
  const collapsedPlanTitle =
    viewModel.taskWorkspace.taskTree?.title ?? viewModel.workspace.title;
  const collapsedPlanMeta =
    viewModel.taskWorkspace.taskTree !== null
      ? `${viewModel.taskWorkspace.taskTree.nodes.length} tasks · ${viewModel.taskWorkspace.taskTree.status}`
      : "Generating plan";

  useEffect(() => {
    setIsPlanLayerExpanded(hasPlanLayer);
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
  }

  function showActivityFiles(taskNodeId: string | null) {
    if (taskNodeId !== null) {
      actions.selectTask(taskNodeId);
    }
    actions.showFileChanges();
    setIsActivityOverlayOpen(false);
  }

  function showActivityAudit(ref: SessionActivityRefView) {
    const href = ref.href ?? viewModel.workspace.auditEntry.href;
    window.location.assign(href);
    setIsActivityOverlayOpen(false);
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
    if (hidesDetailPanel) {
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
                ? () => setIsActivityOverlayOpen(true)
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

  function renderWorkspaceHeader(statusActions: ReactNode = null) {
    return (
      <MainPageWorkspaceHeader
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
          headerActions={collapsedPlanTopbarAction}
          messages={conversationMessages}
          onOpenActivity={
            hasActivity ? () => setIsActivityOverlayOpen(true) : undefined
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
          {renderWorkspaceHeader(collapsePlanAction)}
          <div className={styles.planProgressWorkspaceBody}>
            {planProgressLayer}
          </div>
        </Panel>
      ) : null}

      {!hidesDetailPanel ? (
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

      {isActivityOverlayOpen && hasActivity ? (
        <ActivityOverlay
          errorMessage={activityError}
          isLoading={isActivityLoading}
          items={overlayActivityItems}
          onClose={() => setIsActivityOverlayOpen(false)}
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
          }}
          onOpenResult={showActivityResult}
          onOpenTask={(taskNodeId) => {
            actions.selectTask(taskNodeId);
            setIsActivityOverlayOpen(false);
          }}
          onRetry={() => setActivityLoadKey((key) => key + 1)}
          selectedTask={viewModel.taskWorkspace.selectedTask}
          statusMessage={activityStatusMessage}
        />
      ) : null}

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
  const merged: SessionActivityItemView[] = [];

  for (const item of [...transientItems, ...sourceItems]) {
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
  const merged: SessionMessageView[] = [];

  for (const message of [...sourceMessages, ...transientMessages]) {
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
  };
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
