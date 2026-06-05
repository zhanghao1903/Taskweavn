import { useState } from "react";
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
      return null;
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
  const [isReaderOpen, setIsReaderOpen] = useState(false);
  const sections = detail.result.sections ?? [];
  const shouldShowReader =
    detail.result.summary.length > 220 || sections.length > 0;

  if (isReaderOpen) {
    return (
      <Panel
        className={styles.detailBox}
        tone="muted"
        aria-label="Result reader"
      >
        <div className={styles.detailTitleRow}>
          <Text as="strong" variant="label">
            Result reader
          </Text>
          <Badge size="sm" tone="blue">
            {sections.length} sections
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
            Back to result card
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
          Result card
        </Text>
        <Badge size="sm" tone="blue">
          structured
        </Badge>
      </div>
      <Text className={styles.resultSummaryPreview} variant="muted">
        {detail.result.summary}
      </Text>
      {shouldShowReader && (
        <div className={styles.resultReaderPrompt}>
          <Text variant="muted">
            {sections.length > 0
              ? `${sections.length} structured sections available.`
              : "Full result available in reader."}
          </Text>
          <Button onClick={() => setIsReaderOpen(true)}>Open reader</Button>
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
  const fileCount = detail.fileChangeSummary.changedFiles.length;

  return (
    <Panel className={styles.detailBox} tone="muted">
      <div className={styles.detailTitleRow}>
        <Text as="strong" variant="label">
          Changed files
        </Text>
        <Badge size="sm" tone={fileCount > 0 ? "blue" : "neutral"}>
          {fileCount === 1 ? "1 file" : `${fileCount} files`}
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
              {file.summary && (
                <p className={styles.fileChangeSummaryPreview}>{file.summary}</p>
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

  return (
    <Panel
      aria-label="Selected task details"
      className={styles.detailBox}
      data-task-node-id={detail.selectedTask.id}
      tone="muted"
    >
      <Text as="strong" variant="label">
        Task details
      </Text>
      <div className={styles.taskDetailContent}>
        <strong>{detail.selectedTask.title}</strong>
        <p>{detail.selectedTask.summary}</p>
      </div>
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
