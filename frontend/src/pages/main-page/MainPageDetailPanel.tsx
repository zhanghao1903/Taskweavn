import type { ReactNode } from "react";
import { useState } from "react";
import { CircleStop, RotateCcw } from "lucide-react";

import type {
  AnswerAskPayload,
  CancelAskPayload,
  DeferAskPayload,
} from "../../shared/api/platoApi";
import type {
  FileChangeSummaryView,
  TaskNodeId,
  WorkspaceId,
} from "../../shared/api/types";
import { Badge, Button, Panel, Text } from "../../shared/components";
import { buildWorkspaceInspectionRoute } from "../../app/routes";
import { ConfirmationDetailPanel } from "./interaction/ConfirmationDetailPanel";
import { ExecutionAskDetailPanel } from "./interaction/ExecutionAskDetailPanel";
import { confirmationResolutionText } from "./mainPageCopy";
import { selectFileChangeTypePresentation } from "./mainPageSelectors";
import type { MainPageDetailView } from "./mainPageViewModel";
import styles from "./MainPage.module.css";

export type MainPageDetailPanelProps = {
  detail: MainPageDetailView;
  onAnswerAsk: (payload: AnswerAskPayload) => void;
  onCancelAsk: (payload: CancelAskPayload) => void;
  onConfirmationDecision: (decision: string) => void;
  onDeferAsk: (payload: DeferAskPayload) => void;
  onRetryTask: (taskNodeId: TaskNodeId) => void;
  onStopTask: (taskNodeId: TaskNodeId) => void;
  onShowFileChanges: () => void;
  onShowResult: () => void;
  workspaceId?: WorkspaceId | null;
};

type ConfirmationResolvedDetail = Extract<
  MainPageDetailView,
  { kind: "confirmationResolved" }
>;
type ResultDetail = Extract<MainPageDetailView, { kind: "result" }>;
type FileChangesDetail = Extract<MainPageDetailView, { kind: "fileChanges" }>;
type PlanDetail = Extract<MainPageDetailView, { kind: "plan" }>;
type TaskDetail = Extract<MainPageDetailView, { kind: "task" }>;

export function MainPageDetailPanel({
  detail,
  onAnswerAsk,
  onCancelAsk,
  onConfirmationDecision,
  onDeferAsk,
  onRetryTask,
  onStopTask,
  onShowFileChanges,
  onShowResult,
  workspaceId,
}: MainPageDetailPanelProps) {
  if (detail.kind === "note") {
    return null;
  }

  const { header } = detail;

  return (
    <Panel
      as="aside"
      className={styles.detailPanel}
      aria-label="Details"
    >
      <Text variant="eyebrow">{header.eyebrow}</Text>
      <Text as="h2" className={styles.detailHeaderTitle} variant="heading">
        {header.title}
      </Text>
      <Text className={styles.detailHeaderBody} variant="muted">
        {header.body}
      </Text>
      <DetailContent
        detail={detail}
        onAnswerAsk={onAnswerAsk}
        onCancelAsk={onCancelAsk}
        onConfirmationDecision={onConfirmationDecision}
        onDeferAsk={onDeferAsk}
        onRetryTask={onRetryTask}
        onStopTask={onStopTask}
        onShowFileChanges={onShowFileChanges}
        onShowResult={onShowResult}
        workspaceId={workspaceId}
      />
    </Panel>
  );
}

type DetailContentProps = {
  detail: MainPageDetailView;
  onAnswerAsk: (payload: AnswerAskPayload) => void;
  onCancelAsk: (payload: CancelAskPayload) => void;
  onConfirmationDecision: (decision: string) => void;
  onDeferAsk: (payload: DeferAskPayload) => void;
  onRetryTask: (taskNodeId: TaskNodeId) => void;
  onStopTask: (taskNodeId: TaskNodeId) => void;
  onShowFileChanges: () => void;
  onShowResult: () => void;
  workspaceId?: WorkspaceId | null;
};

function DetailContent({
  detail,
  onAnswerAsk,
  onCancelAsk,
  onConfirmationDecision,
  onDeferAsk,
  onRetryTask,
  onStopTask,
  onShowFileChanges,
  onShowResult,
  workspaceId,
}: DetailContentProps) {
  switch (detail.kind) {
    case "executionAsk":
      return (
        <ExecutionAskDetailPanel
          detail={detail}
          onAnswer={onAnswerAsk}
          onCancel={onCancelAsk}
          onDefer={onDeferAsk}
        />
      );
    case "confirmation":
      return (
        <ConfirmationDetailPanel
          detail={detail}
          onResolve={onConfirmationDecision}
        />
      );
    case "confirmationResolved":
      return <ConfirmationResolvedPanel detail={detail} />;
    case "result":
      return (
        <ResultSummaryPanel
          detail={detail}
          onShowFileChanges={onShowFileChanges}
          workspaceId={workspaceId}
        />
      );
    case "fileChanges":
      return (
        <FileChangeSummaryPanel
          detail={detail}
          onShowResult={onShowResult}
          workspaceId={workspaceId}
        />
      );
    case "task":
      return (
        <TaskDetailPanel
          detail={detail}
          onRetryTask={onRetryTask}
          onStopTask={onStopTask}
        />
      );
    case "plan":
      return <PlanDetailPanel detail={detail} />;
    case "note":
      return null;
  }
}

function PlanDetailPanel({ detail }: { detail: PlanDetail }) {
  const taskCount = detail.taskTree.nodes.length;

  return (
    <Panel
      aria-label="Plan interaction"
      className={styles.detailBox}
      tone="muted"
    >
      <div className={styles.detailTitleRow}>
        <Text as="strong" variant="label">
          Plan interaction
        </Text>
        <Badge size="sm" tone="blue">
          {taskCount === 1 ? "1 task" : `${taskCount} tasks`}
        </Badge>
      </div>
      <Text variant="muted">
        Input now refines the whole plan. Select a task to inspect or guide one
        Task.
      </Text>
    </Panel>
  );
}

function ConfirmationResolvedPanel({
  detail,
}: {
  detail: ConfirmationResolvedDetail;
}) {
  return (
    <Panel className={styles.detailBox} tone="muted">
      <Text as="strong" variant="label">
        Confirmation resolved
      </Text>
      <Text variant="muted">{confirmationResolutionText[detail.decision]}</Text>
    </Panel>
  );
}

type ResultSummaryPanelProps = {
  detail: ResultDetail;
  onShowFileChanges: () => void;
  workspaceId?: WorkspaceId | null;
};

function ResultSummaryPanel({
  detail,
  onShowFileChanges,
  workspaceId,
}: ResultSummaryPanelProps) {
  const [isReaderOpen, setIsReaderOpen] = useState(false);
  const sections = detail.result.sections ?? [];
  const shouldShowReader =
    detail.result.summary.length > 220 || sections.length > 0;
  const resolvedWorkspaceId = workspaceId ?? "current";

  if (isReaderOpen) {
    return (
      <Panel
        className={styles.detailBox}
        tone="muted"
        aria-label="Full result"
      >
        <div className={styles.detailTitleRow}>
          <Text as="strong" variant="label">
            Full result
          </Text>
          <Badge size="sm" tone="blue">
            {sections.length > 0 ? `${sections.length} sections` : "Summary"}
          </Badge>
        </div>
        <Text variant="muted">{detail.result.summary}</Text>
        {sections.length > 0 && (
          <div className={styles.resultSections}>
            {sections.map((section) => (
              <article className={styles.resultSection} key={section.title}>
                <div className={styles.detailTitleRow}>
                  <strong>{section.title}</strong>
                  <Badge size="sm" tone="neutral">
                    {section.kind ?? "text"}
                  </Badge>
                </div>
                <p>{section.body}</p>
              </article>
            ))}
          </div>
        )}
        <div className={styles.actionRow}>
          <Button onClick={() => setIsReaderOpen(false)}>
            Back to summary
          </Button>
          {detail.fileChangeSummary && (
            <Button onClick={onShowFileChanges}>View file changes</Button>
          )}
        </div>
      </Panel>
    );
  }

  return (
    <Panel className={styles.detailBox} tone="muted">
      <div className={styles.detailTitleRow}>
        <Text as="strong" variant="label">
          Result summary
        </Text>
        <Badge size="sm" tone="blue">
          {sections.length > 0 ? "Detailed" : "Summary"}
        </Badge>
      </div>
      <Text className={styles.resultSummaryPreview} variant="muted">
        {detail.result.summary}
      </Text>
      {shouldShowReader && (
        <div className={styles.resultReaderPrompt}>
          <Text variant="muted">
            {sections.length > 0
              ? `${sections.length} sections available.`
              : "Full result available."}
          </Text>
          <Button onClick={() => setIsReaderOpen(true)}>
            View full result
          </Button>
        </div>
      )}
      {detail.fileChangeSummary && (
        <WorkspaceChangesPreview
          fileChangeSummary={detail.fileChangeSummary}
          onShowFileChanges={onShowFileChanges}
          workspaceId={resolvedWorkspaceId}
        />
      )}
    </Panel>
  );
}

function WorkspaceChangesPreview({
  fileChangeSummary,
  onShowFileChanges,
  workspaceId,
}: {
  fileChangeSummary: FileChangeSummaryView;
  onShowFileChanges: () => void;
  workspaceId: WorkspaceId;
}) {
  const fileCount = fileChangeSummary.changedFiles.length;

  return (
    <section className={styles.resultWorkspaceChanges} aria-label="Workspace changes">
      <div className={styles.detailTitleRow}>
        <Text as="strong" variant="label">
          Workspace changes
        </Text>
        <Badge size="sm" tone={fileCount > 0 ? "blue" : "neutral"}>
          {fileCount === 1 ? "1 file" : `${fileCount} files`}
        </Badge>
      </div>
      <div className={styles.fileChangeList} role="list">
        {fileChangeSummary.changedFiles.map((file) => {
          const changePresentation = selectFileChangeTypePresentation(
            file.changeType,
          );
          const taskNodeId =
            file.ownerTaskNodeId ?? fileChangeSummary.taskNodeId ?? undefined;
          const routeContext = {
            path: file.path,
            returnSessionId: fileChangeSummary.sessionId,
            returnTaskNodeId: taskNodeId ?? undefined,
            sessionId: fileChangeSummary.sessionId,
            taskNodeId: taskNodeId ?? undefined,
            workspaceId,
          };

          return (
            <article
              className={styles.fileChangeItem}
              key={file.path}
              role="listitem"
            >
              <div className={styles.detailTitleRow}>
                <strong className={styles.filePath}>{file.path}</strong>
                <Badge size="sm" tone={changePresentation.tone}>
                  {changePresentation.label}
                </Badge>
              </div>
              <div className={styles.fileActionRow}>
                <a
                  href={buildWorkspaceInspectionRoute({
                    ...routeContext,
                    view: "file",
                  })}
                >
                  Open file
                </a>
                <a
                  href={buildWorkspaceInspectionRoute({
                    ...routeContext,
                    view: "diff",
                  })}
                >
                  View diff
                </a>
              </div>
            </article>
          );
        })}
      </div>
      <div className={styles.actionRow}>
        <Button onClick={onShowFileChanges}>View file changes</Button>
      </div>
    </section>
  );
}

type FileChangeSummaryPanelProps = {
  detail: FileChangesDetail;
  onShowResult: () => void;
  workspaceId?: WorkspaceId | null;
};

function FileChangeSummaryPanel({
  detail,
  onShowResult,
  workspaceId,
}: FileChangeSummaryPanelProps) {
  const fileCount = detail.fileChangeSummary.changedFiles.length;
  const resolvedWorkspaceId = workspaceId ?? "current";

  return (
    <Panel className={styles.detailBox} tone="muted">
      <div className={styles.detailTitleRow}>
        <Text as="strong" variant="label">
          Changed files
        </Text>
        <div className={styles.badgeGroup}>
          <Badge size="sm" tone={fileCount > 0 ? "blue" : "neutral"}>
            {fileCount === 1 ? "1 file" : `${fileCount} files`}
          </Badge>
          {detail.fileChangeSummary.recursive ? (
            <Badge size="sm" tone="neutral">
              Includes child tasks
            </Badge>
          ) : null}
        </div>
      </div>
      <div className={styles.fileChangeList} role="list">
        {detail.fileChangeSummary.changedFiles.map((file) => {
          const changePresentation = selectFileChangeTypePresentation(
            file.changeType,
          );
          const taskNodeId =
            file.ownerTaskNodeId ?? detail.fileChangeSummary.taskNodeId ?? undefined;
          const routeContext = {
            path: file.path,
            returnSessionId: detail.fileChangeSummary.sessionId,
            returnTaskNodeId: taskNodeId ?? undefined,
            sessionId: detail.fileChangeSummary.sessionId,
            taskNodeId: taskNodeId ?? undefined,
            workspaceId: resolvedWorkspaceId,
          };

          return (
            <article
              className={styles.fileChangeItem}
              key={file.path}
              role="listitem"
            >
              <div className={styles.detailTitleRow}>
                <strong className={styles.filePath}>{file.path}</strong>
                <Badge size="sm" tone={changePresentation.tone}>
                  {changePresentation.label}
                </Badge>
              </div>
              <div className={styles.fileActionRow}>
                <a
                  href={buildWorkspaceInspectionRoute({
                    ...routeContext,
                    view: "file",
                  })}
                >
                  Open file
                </a>
                <a
                  href={buildWorkspaceInspectionRoute({
                    ...routeContext,
                    view: "diff",
                  })}
                >
                  View diff
                </a>
              </div>
            </article>
          );
        })}
      </div>
      {detail.result && (
        <div className={styles.actionRow}>
          <Button onClick={onShowResult}>View result</Button>
        </div>
      )}
    </Panel>
  );
}

function TaskDetailPanel({
  detail,
  onRetryTask,
  onStopTask,
}: {
  detail: TaskDetail;
  onRetryTask: (taskNodeId: TaskNodeId) => void;
  onStopTask: (taskNodeId: TaskNodeId) => void;
}) {
  const isRunning =
    detail.selectedTask.execution === "running" ||
    detail.selectedTask.status === "running";
  const isStopping = Boolean(
    detail.selectedTask.interruptionRequested && isRunning,
  );
  const showPublishedStopAction =
    detail.selectedTask.taskRef?.kind === "published" &&
    isRunning &&
    (detail.selectedTask.permissions.canCancel || isStopping);
  const showRetryAction = detail.selectedTask.permissions.canRetry;
  const intent = detail.selectedTask.intent?.trim();
  const instructions = detail.selectedTask.instructions?.trim();
  const acceptanceCriteria = detail.selectedTask.acceptanceCriteria ?? [];
  const shouldShowIntent =
    Boolean(intent) &&
    intent !== detail.selectedTask.summary &&
    intent !== detail.selectedTask.title;
  const hasStructuredDetails =
    shouldShowIntent || Boolean(instructions) || acceptanceCriteria.length > 0;

  if (!showPublishedStopAction && !showRetryAction && !hasStructuredDetails) {
    return null;
  }

  return (
    <>
      {hasStructuredDetails && (
        <Panel
          aria-label="Task details"
          className={styles.detailBox}
          data-task-node-id={detail.selectedTask.id}
          tone="muted"
        >
          <Text as="strong" variant="label">
            Task details
          </Text>
          {shouldShowIntent && (
            <TaskDetailSection title="Intent">{intent}</TaskDetailSection>
          )}
          {instructions && (
            <TaskDetailSection title="Instructions">
              {instructions}
            </TaskDetailSection>
          )}
          {acceptanceCriteria.length > 0 && (
            <div className={styles.taskDetailSection}>
              <Text as="strong" variant="label">
                Acceptance criteria
              </Text>
              <ul className={styles.taskDetailList}>
                {acceptanceCriteria.map((criterion) => (
                  <li key={criterion}>{criterion}</li>
                ))}
              </ul>
            </div>
          )}
        </Panel>
      )}
      {(showPublishedStopAction || showRetryAction) && (
        <Panel
          aria-label="Task actions"
          className={styles.detailBox}
          data-task-node-id={detail.selectedTask.id}
          tone="muted"
        >
          <Text as="strong" variant="label">
            Task actions
          </Text>
          {showPublishedStopAction && (
            <div className={styles.actionRow}>
              <Button
                disabled={detail.isStoppingTask || isStopping}
                onClick={() => onStopTask(detail.selectedTask.id)}
                variant="danger"
              >
                <CircleStop size={14} aria-hidden="true" />
                {detail.isStoppingTask || isStopping ? "Stopping" : "Stop"}
              </Button>
            </div>
          )}
          {showRetryAction && (
            <div className={styles.actionRow}>
              <Button
                disabled={detail.isRetryingTask}
                onClick={() => onRetryTask(detail.selectedTask.id)}
                variant="primary"
              >
                <RotateCcw size={14} aria-hidden="true" />
                {detail.isRetryingTask ? "Retrying" : "Retry"}
              </Button>
            </div>
          )}
        </Panel>
      )}
    </>
  );
}

function TaskDetailSection({
  children,
  title,
}: {
  children: ReactNode;
  title: string;
}) {
  return (
    <div className={styles.taskDetailSection}>
      <Text as="strong" variant="label">
        {title}
      </Text>
      <Text variant="muted">{children}</Text>
    </div>
  );
}
