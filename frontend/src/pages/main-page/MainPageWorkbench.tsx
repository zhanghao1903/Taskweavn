import type { ReactNode } from "react";

import { Panel } from "../../shared/components";
import { ContextInputPanel } from "./ContextInputPanel";
import { MainPageDetailPanel } from "./MainPageDetailPanel";
import { MainPageSessionSidebar } from "./MainPageSessionSidebar";
import { MainPageTopBar } from "./MainPageTopBar";
import { MainPageWorkspaceHeader } from "./MainPageWorkspaceHeader";
import { SessionMessagePanel } from "./SessionMessagePanel";
import { TaskTreePanel } from "./TaskTreePanel";
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
  statePicker?: ReactNode;
  viewModel: MainPageViewModel;
};

export function MainPageWorkbench({
  actions,
  inputDraft,
  inputError,
  isCreatingSession,
  isDeletingSession,
  isRenamingSession,
  statePicker = null,
  viewModel,
}: MainPageWorkbenchProps) {
  return (
    <main className={styles.page}>
      <MainPageTopBar
        brandLabel={viewModel.topBar.brandLabel}
        contextItems={viewModel.topBar.contextItems}
        statuses={viewModel.topBar.statuses}
        trailing={statePicker}
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
