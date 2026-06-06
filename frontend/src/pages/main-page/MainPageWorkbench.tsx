import { useState, type ReactNode } from "react";

import { Panel } from "../../shared/components";
import { ActivityOverlay } from "./ActivityOverlay";
import { ContextInputPanel } from "./ContextInputPanel";
import { LatestActivityStrip } from "./LatestActivityStrip";
import { MainPageDetailPanel } from "./MainPageDetailPanel";
import { MainPageSessionSidebar } from "./MainPageSessionSidebar";
import { MainPageTopBar } from "./MainPageTopBar";
import { MainPageWorkspaceHeader } from "./MainPageWorkspaceHeader";
import { TaskTreePanel } from "./TaskTreePanel";
import { AuthoringAskWorkArea } from "./interaction/AuthoringAskWorkArea";
import type { MainPageViewModel } from "./mainPageViewModel";
import type { MainPageController } from "./useMainPageController";
import styles from "./MainPage.module.css";

export type MainPageWorkbenchProps = {
  actions: MainPageController["actions"];
  inputDraft: string;
  inputError: string | null;
  isCreatingSession: boolean;
  isDeletingSession: boolean;
  isRenamingSession: boolean;
  sessionDialog: MainPageController["sessionDialog"];
  topBarTrailing?: ReactNode;
  viewModel: MainPageViewModel;
};

export function MainPageWorkbench({
  actions,
  inputDraft,
  inputError,
  isCreatingSession,
  isDeletingSession,
  isRenamingSession,
  sessionDialog,
  topBarTrailing = null,
  viewModel,
}: MainPageWorkbenchProps) {
  const [isActivityOverlayOpen, setIsActivityOverlayOpen] = useState(false);
  const hidesDetailPanel = viewModel.detail.kind === "note";
  const pageClassName = hidesDetailPanel
    ? `${styles.page} ${styles.pageWithoutDetail}`
    : styles.page;
  const hasActivity =
    viewModel.mainWorkArea.kind !== "authoringAsk" &&
    viewModel.taskWorkspace.allMessages.length > 0;
  const hasVisibleActivity =
    viewModel.mainWorkArea.kind !== "authoringAsk" &&
    viewModel.taskWorkspace.messages.length > 0;

  return (
    <main className={pageClassName}>
      <MainPageTopBar
        brandLabel={viewModel.topBar.brandLabel}
        contextItems={viewModel.topBar.contextItems}
        statuses={viewModel.topBar.statuses}
        trailing={topBarTrailing}
      />

      <MainPageSessionSidebar
        activeSession={viewModel.sidebar.activeSession}
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
      />

      <Panel
        as="section"
        className={styles.workspace}
        aria-label="Task workspace"
      >
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
          showPublishTaskTree={viewModel.workspace.showPublishTaskTree}
          taskTreeCommandError={viewModel.workspace.taskTreeCommandError}
          title={viewModel.workspace.title}
          uiNotice={viewModel.workspace.uiNotice}
        />

        {viewModel.mainWorkArea.kind === "authoringAsk" ? (
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
        ) : (
          <div
            className={
              hasVisibleActivity
                ? styles.workGrid
                : `${styles.workGrid} ${styles.workGridWithoutActivity}`
            }
          >
            <LatestActivityStrip
              isMessageScoped={viewModel.taskWorkspace.isMessageScoped}
              messages={viewModel.taskWorkspace.messages}
              onOpenActivity={
                hasActivity ? () => setIsActivityOverlayOpen(true) : undefined
              }
              selectedTask={viewModel.taskWorkspace.selectedTask}
              totalMessageCount={viewModel.taskWorkspace.totalMessageCount}
              visibleMessageCount={viewModel.taskWorkspace.visibleMessageCount}
            />
            <TaskTreePanel
              isTaskPlanSelected={
                viewModel.taskWorkspace.isTaskPlanSelected
              }
              onRetryTask={(taskNodeId) =>
                actions.retryTask({
                  sessionId: viewModel.sessionId,
                  taskNodeId,
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
              isGeneratingTaskPlan={
                viewModel.taskWorkspace.isGeneratingTaskPlan
              }
              taskTree={viewModel.taskWorkspace.taskTree}
            />
          </div>
        )}
      </Panel>

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
      />

      {isActivityOverlayOpen && hasActivity ? (
        <ActivityOverlay
          allMessages={viewModel.taskWorkspace.allMessages}
          currentMessages={viewModel.taskWorkspace.messages}
          onClose={() => setIsActivityOverlayOpen(false)}
          selectedTask={viewModel.taskWorkspace.selectedTask}
        />
      ) : null}

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
