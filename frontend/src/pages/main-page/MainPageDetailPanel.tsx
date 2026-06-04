import { CircleStop, RotateCcw } from "lucide-react";

import type {
  AnswerAskPayload,
  CancelAskPayload,
  DeferAskPayload,
} from "../../shared/api/platoApi";
import type { TaskNodeId } from "../../shared/api/types";
import { Badge, Button, Panel, Text } from "../../shared/components";
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
};

type ConfirmationResolvedDetail = Extract<
  MainPageDetailView,
  { kind: "confirmationResolved" }
>;
type ResultDetail = Extract<MainPageDetailView, { kind: "result" }>;
type FileChangesDetail = Extract<MainPageDetailView, { kind: "fileChanges" }>;
type TaskDetail = Extract<MainPageDetailView, { kind: "task" }>;
type StateNoteDetail = Extract<MainPageDetailView, { kind: "note" }>;

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
}: MainPageDetailPanelProps) {
  const { header } = detail;

  return (
    <Panel
      as="aside"
      className={styles.detailPanel}
      aria-label="Context inspector"
    >
      <Text variant="eyebrow">{header.eyebrow}</Text>
      <Text as="h2" variant="heading">
        {header.title}
      </Text>
      <Text variant="muted">{header.body}</Text>
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
        />
      );
    case "fileChanges":
      return (
        <FileChangeSummaryPanel
          detail={detail}
          onShowResult={onShowResult}
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
    case "note":
      return <StateNotePanel detail={detail} />;
  }
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
};

function ResultSummaryPanel({
  detail,
  onShowFileChanges,
}: ResultSummaryPanelProps) {
  return (
    <Panel className={styles.detailBox} tone="muted">
      <div className={styles.detailTitleRow}>
        <Text as="strong" variant="label">
          Result card
        </Text>
        <Badge size="sm" tone="blue">
          structured
        </Badge>
      </div>
      <Text variant="muted">{detail.result.summary}</Text>
      {detail.result.sections && detail.result.sections.length > 0 && (
        <div className={styles.resultSections}>
          {detail.result.sections.map((section) => (
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
      {detail.fileChangeSummary && (
        <div className={styles.actionRow}>
          <Button onClick={onShowFileChanges}>View file changes</Button>
        </div>
      )}
    </Panel>
  );
}

type FileChangeSummaryPanelProps = {
  detail: FileChangesDetail;
  onShowResult: () => void;
};

function FileChangeSummaryPanel({
  detail,
  onShowResult,
}: FileChangeSummaryPanelProps) {
  return (
    <Panel className={styles.detailBox} tone="muted">
      <div className={styles.detailTitleRow}>
        <Text as="strong" variant="label">
          Changed files
        </Text>
        <Badge
          size="sm"
          tone={detail.fileChangeSummary.recursive ? "blue" : "neutral"}
        >
          {detail.fileChangeSummary.recursive
            ? "Recursive subtree summary"
            : "Direct task changes"}
        </Badge>
      </div>
      <Text variant="muted">{detail.fileChangeSummary.summary}</Text>
      <div className={styles.fileChangeList} role="list">
        {detail.fileChangeSummary.changedFiles.map((file) => {
          const changePresentation = selectFileChangeTypePresentation(
            file.changeType,
          );

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
              {file.summary && <p>{file.summary}</p>}
              {file.ownerTaskNodeId && (
                <span className={styles.fileOwner}>
                  Owner TaskNode: {file.ownerTaskNodeId}
                </span>
              )}
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
  const isStopping = Boolean(
    detail.selectedTask.interruptionRequested &&
      (detail.selectedTask.execution === "running" ||
        detail.selectedTask.status === "running"),
  );
  const showStopAction = detail.selectedTask.permissions.canCancel || isStopping;
  const showPublishedStopAction =
    detail.selectedTask.taskRef?.kind === "published" && showStopAction;

  return (
    <Panel
      className={styles.detailBox}
      data-task-node-id={detail.selectedTask.id}
      tone="muted"
    >
      <Text as="strong" variant="label">
        Task interaction
      </Text>
      <Text variant="muted">
        Input now applies to this TaskNode. Completed TaskNodes are read-only;
        running TaskNodes accept appended guidance.
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
      {detail.selectedTask.permissions.canRetry && (
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
  );
}

function StateNotePanel({ detail }: { detail: StateNoteDetail }) {
  return (
    <Panel className={styles.detailBox} tone="muted">
      <Text as="strong" variant="label">
        State note
      </Text>
      <Text variant="muted">{detail.body}</Text>
    </Panel>
  );
}
