import type { ReactNode, Ref } from "react";
import { useState } from "react";
import { CircleStop, RotateCcw } from "lucide-react";

import type {
  AnswerAskPayload,
  CancelAskPayload,
  DeferAskPayload,
} from "../../shared/api/platoApi";
import type {
  FileChangeSummaryView,
  SessionId,
  TaskNodeId,
  WorkspaceId,
} from "../../shared/api/types";
import type { TokenUsageSummaryRequest } from "../../shared/api/tokenUsageTypes";
import {
  Badge,
  Button,
  MarkdownContent,
  Panel,
  Text,
} from "../../shared/components";
import { useUiText, type UiTextCatalog } from "../../shared/ui-text";
import { buildWorkspaceInspectionRoute } from "../../app/routes";
import { ConfirmationDetailPanel } from "./interaction/ConfirmationDetailPanel";
import { ExecutionAskDetailPanel } from "./interaction/ExecutionAskDetailPanel";
import { selectFileChangeTypePresentation } from "./mainPageSelectors";
import type { MainPageDetailView } from "./mainPageViewModel";
import { MainPageTokenUsageSummaryCard } from "./MainPageTokenUsageSummaryCard";
import type { LoadTokenUsageSummary } from "./runtime/adapter";
import styles from "./MainPage.module.css";

export type MainPageDetailPanelProps = {
  detail: MainPageDetailView;
  detailFocusRef?: Ref<HTMLElement>;
  executionAskFocusRef?: Ref<HTMLElement>;
  fileChangesFocusRef?: Ref<HTMLElement>;
  onAnswerAsk: (payload: AnswerAskPayload) => void;
  onCancelAsk: (payload: CancelAskPayload) => void;
  onConfirmationDecision: (decision: string) => void;
  onDeferAsk: (payload: DeferAskPayload) => void;
  onRetryTask: (taskNodeId: TaskNodeId) => void;
  onStopTask: (taskNodeId: TaskNodeId) => void;
  onShowFileChanges: () => void;
  onShowResult: () => void;
  loadTokenUsageSummary?: LoadTokenUsageSummary;
  sessionId?: SessionId | null;
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

function localizedDetailHeader(
  detail: MainPageDetailView,
  uiText: UiTextCatalog,
): MainPageDetailView["header"] {
  const shouldLocalizeSystemCopy =
    uiText.main.detail.labels.changedFiles !== "Changed files";

  if (detail.kind === "fileChanges") {
    if (!shouldLocalizeSystemCopy) {
      return detail.header;
    }

    const fileCount = detail.fileChangeSummary.changedFiles.length;
    return {
      body: uiText.main.detail.messages.fileCountChanged({
        count: fileCount,
      }),
      eyebrow: uiText.main.detail.labels.fileChanges,
      title: uiText.main.detail.labels.changedFiles,
    };
  }

  if (detail.kind === "executionAsk") {
    return {
      ...detail.header,
      eyebrow: uiText.main.detail.labels.taskInput,
    };
  }

  if (detail.kind === "task" && detail.header.eyebrow === "Task") {
    return {
      ...detail.header,
      eyebrow: uiText.audit.labels.task,
    };
  }

  if (detail.kind === "plan") {
    return {
      ...detail.header,
      eyebrow:
        detail.header.eyebrow === "Plan" ||
        detail.header.eyebrow === "Draft task plan"
          ? uiText.main.detail.labels.plan
          : detail.header.eyebrow,
    };
  }

  return detail.header;
}

export function MainPageDetailPanel({
  detail,
  detailFocusRef,
  executionAskFocusRef,
  fileChangesFocusRef,
  onAnswerAsk,
  onCancelAsk,
  onConfirmationDecision,
  onDeferAsk,
  onRetryTask,
  onStopTask,
  onShowFileChanges,
  onShowResult,
  loadTokenUsageSummary,
  sessionId,
  workspaceId,
}: MainPageDetailPanelProps) {
  const uiText = useUiText();

  if (detail.kind === "note") {
    return null;
  }

  const header = localizedDetailHeader(detail, uiText);

  return (
    <Panel
      as="aside"
      className={styles.detailPanel}
      aria-label={uiText.main.detail.labels.details}
      ref={detailFocusRef}
      tabIndex={-1}
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
        executionAskFocusRef={executionAskFocusRef}
        fileChangesFocusRef={fileChangesFocusRef}
        onAnswerAsk={onAnswerAsk}
        onCancelAsk={onCancelAsk}
        onConfirmationDecision={onConfirmationDecision}
        onDeferAsk={onDeferAsk}
        onRetryTask={onRetryTask}
        onStopTask={onStopTask}
        onShowFileChanges={onShowFileChanges}
        onShowResult={onShowResult}
        loadTokenUsageSummary={loadTokenUsageSummary}
        sessionId={sessionId}
        workspaceId={workspaceId}
      />
    </Panel>
  );
}

type DetailContentProps = {
  detail: MainPageDetailView;
  executionAskFocusRef?: Ref<HTMLElement>;
  fileChangesFocusRef?: Ref<HTMLElement>;
  onAnswerAsk: (payload: AnswerAskPayload) => void;
  onCancelAsk: (payload: CancelAskPayload) => void;
  onConfirmationDecision: (decision: string) => void;
  onDeferAsk: (payload: DeferAskPayload) => void;
  onRetryTask: (taskNodeId: TaskNodeId) => void;
  onStopTask: (taskNodeId: TaskNodeId) => void;
  onShowFileChanges: () => void;
  onShowResult: () => void;
  loadTokenUsageSummary?: LoadTokenUsageSummary;
  sessionId?: SessionId | null;
  workspaceId?: WorkspaceId | null;
};

function DetailContent({
  detail,
  executionAskFocusRef,
  fileChangesFocusRef,
  onAnswerAsk,
  onCancelAsk,
  onConfirmationDecision,
  onDeferAsk,
  onRetryTask,
  onStopTask,
  onShowFileChanges,
  onShowResult,
  loadTokenUsageSummary,
  sessionId,
  workspaceId,
}: DetailContentProps) {
  switch (detail.kind) {
    case "executionAsk":
      return (
        <ExecutionAskDetailPanel
          detail={detail}
          focusRef={executionAskFocusRef}
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
          fileChangesFocusRef={fileChangesFocusRef}
          onShowFileChanges={onShowFileChanges}
          workspaceId={workspaceId}
        />
      );
    case "fileChanges":
      return (
        <FileChangeSummaryPanel
          detail={detail}
          focusRef={fileChangesFocusRef}
          onShowResult={onShowResult}
          workspaceId={workspaceId}
        />
      );
    case "task":
      return (
        <TaskDetailPanel
          detail={detail}
          loadTokenUsageSummary={loadTokenUsageSummary}
          onRetryTask={onRetryTask}
          onStopTask={onStopTask}
          sessionId={sessionId}
          workspaceId={workspaceId}
        />
      );
    case "plan":
      return (
        <PlanDetailPanel
          detail={detail}
          loadTokenUsageSummary={loadTokenUsageSummary}
          sessionId={sessionId}
          workspaceId={workspaceId}
        />
      );
    case "note":
      return null;
  }
}

function PlanDetailPanel({
  detail,
  loadTokenUsageSummary,
  sessionId,
  workspaceId,
}: {
  detail: PlanDetail;
  loadTokenUsageSummary?: LoadTokenUsageSummary;
  sessionId?: SessionId | null;
  workspaceId?: WorkspaceId | null;
}) {
  const uiText = useUiText();
  const taskCount = detail.taskTree.nodes.length;

  return (
    <>
      {sessionId ? (
        <MainPageTokenUsageSummaryCard
          loadTokenUsageSummary={loadTokenUsageSummary}
          request={{
            dimension: "plan",
            planId: detail.taskTree.id,
            sessionId,
          }}
          workspaceId={workspaceId}
        />
      ) : null}
      <Panel
        aria-label={uiText.main.detail.labels.planInteraction}
        className={styles.detailBox}
        tone="muted"
      >
        <div className={styles.detailTitleRow}>
          <Text as="strong" variant="label">
            {uiText.main.detail.labels.planInteraction}
          </Text>
          <Badge size="sm" tone="blue">
            {uiText.main.detail.messages.taskCount({ count: taskCount })}
          </Badge>
        </div>
        <Text variant="muted">
          {uiText.main.detail.messages.planInteractionBody}
        </Text>
      </Panel>
    </>
  );
}

function ConfirmationResolvedPanel({
  detail,
}: {
  detail: ConfirmationResolvedDetail;
}) {
  const uiText = useUiText();

  return (
    <Panel className={styles.detailBox} tone="muted">
      <Text as="strong" variant="label">
        {uiText.main.activity.kinds.confirmationResolved}
      </Text>
      <Text variant="muted">
        {uiText.main.detail.messages.confirmationResolution[detail.decision]}
      </Text>
    </Panel>
  );
}

type ResultSummaryPanelProps = {
  detail: ResultDetail;
  fileChangesFocusRef?: Ref<HTMLElement>;
  onShowFileChanges: () => void;
  workspaceId?: WorkspaceId | null;
};

function ResultSummaryPanel({
  detail,
  fileChangesFocusRef,
  onShowFileChanges,
  workspaceId,
}: ResultSummaryPanelProps) {
  const uiText = useUiText();
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
        aria-label={uiText.main.detail.labels.fullResult}
      >
        <div className={styles.detailTitleRow}>
          <Text as="strong" variant="label">
            {uiText.main.detail.labels.fullResult}
          </Text>
          <Badge size="sm" tone="blue">
            {sections.length > 0
              ? uiText.main.detail.messages.sectionsAvailable({
                  count: sections.length,
                })
              : uiText.main.detail.labels.summary}
          </Badge>
        </div>
        <MarkdownContent source={detail.result.summary} variant="detail" />
        {sections.length > 0 && (
          <div className={styles.resultSections}>
            {sections.map((section) => (
              <article className={styles.resultSection} key={section.title}>
                <div className={styles.detailTitleRow}>
                  <strong>{section.title}</strong>
                  <Badge size="sm" tone="neutral">
                    {uiText.main.detail.resultSectionKinds[
                      section.kind ?? "text"
                    ]}
                  </Badge>
                </div>
                <MarkdownContent source={section.body} variant="detail" />
              </article>
            ))}
          </div>
        )}
        <div className={styles.actionRow}>
          <Button onClick={() => setIsReaderOpen(false)}>
            {uiText.main.detail.actions.backToSummary}
          </Button>
          {detail.fileChangeSummary && (
            <Button onClick={onShowFileChanges}>
              {uiText.main.detail.actions.viewFileChanges}
            </Button>
          )}
        </div>
      </Panel>
    );
  }

  return (
    <Panel className={styles.detailBox} tone="muted">
      <div className={styles.detailTitleRow}>
        <Text as="strong" variant="label">
          {uiText.main.detail.labels.resultSummary}
        </Text>
        <Badge size="sm" tone="blue">
          {sections.length > 0
            ? uiText.main.detail.labels.detailed
            : uiText.main.detail.labels.summary}
        </Badge>
      </div>
      <MarkdownContent
        className={styles.resultSummaryPreview}
        maxLines={4}
        source={detail.result.summary}
        variant="detail"
      />
      {shouldShowReader && (
        <div className={styles.resultReaderPrompt}>
          <Text variant="muted">
            {sections.length > 0
              ? uiText.main.detail.messages.sectionsAvailable({
                  count: sections.length,
                })
              : uiText.main.detail.messages.fullResultAvailable}
          </Text>
          <Button onClick={() => setIsReaderOpen(true)}>
            {uiText.main.activity.actions.viewFullResult}
          </Button>
        </div>
      )}
      {detail.fileChangeSummary && (
        <WorkspaceChangesPreview
          fileChangeSummary={detail.fileChangeSummary}
          focusRef={fileChangesFocusRef}
          onShowFileChanges={onShowFileChanges}
          workspaceId={resolvedWorkspaceId}
        />
      )}
    </Panel>
  );
}

function WorkspaceChangesPreview({
  fileChangeSummary,
  focusRef,
  onShowFileChanges,
  workspaceId,
}: {
  fileChangeSummary: FileChangeSummaryView;
  focusRef?: Ref<HTMLElement>;
  onShowFileChanges: () => void;
  workspaceId: WorkspaceId;
}) {
  const uiText = useUiText();
  const fileCount = fileChangeSummary.changedFiles.length;

  return (
    <section
      className={styles.resultWorkspaceChanges}
      aria-label={uiText.main.detail.labels.workspaceChanges}
      ref={focusRef}
      tabIndex={-1}
    >
      <div className={styles.detailTitleRow}>
        <Text as="strong" variant="label">
          {uiText.main.detail.labels.workspaceChanges}
        </Text>
        <Badge size="sm" tone={fileCount > 0 ? "blue" : "neutral"}>
          {uiText.main.detail.messages.fileCount({ count: fileCount })}
        </Badge>
      </div>
      <div className={styles.fileChangeList} role="list">
        {fileChangeSummary.changedFiles.map((file) => {
          const changePresentation = selectFileChangeTypePresentation(
            file.changeType,
            uiText.main,
          );
          const taskNodeId =
            file.ownerTaskNodeId ?? fileChangeSummary.taskNodeId ?? undefined;
          const routeContext = {
            path: file.path,
            returnFocus: "file_change" as const,
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
                  {uiText.main.detail.actions.openFile}
                </a>
                <a
                  href={buildWorkspaceInspectionRoute({
                    ...routeContext,
                    view: "diff",
                  })}
                >
                  {uiText.main.detail.actions.viewDiff}
                </a>
              </div>
            </article>
          );
        })}
      </div>
      <div className={styles.actionRow}>
        <Button onClick={onShowFileChanges}>
          {uiText.main.detail.actions.viewFileChanges}
        </Button>
      </div>
    </section>
  );
}

type FileChangeSummaryPanelProps = {
  detail: FileChangesDetail;
  focusRef?: Ref<HTMLElement>;
  onShowResult: () => void;
  workspaceId?: WorkspaceId | null;
};

function FileChangeSummaryPanel({
  detail,
  focusRef,
  onShowResult,
  workspaceId,
}: FileChangeSummaryPanelProps) {
  const uiText = useUiText();
  const fileCount = detail.fileChangeSummary.changedFiles.length;
  const resolvedWorkspaceId = workspaceId ?? "current";

  return (
    <Panel
      className={styles.detailBox}
      ref={focusRef}
      tabIndex={-1}
      tone="muted"
    >
      <div className={styles.detailTitleRow}>
        <Text as="strong" variant="label">
          {uiText.main.detail.labels.changedFiles}
        </Text>
        <div className={styles.badgeGroup}>
          <Badge size="sm" tone={fileCount > 0 ? "blue" : "neutral"}>
            {uiText.main.detail.messages.fileCount({ count: fileCount })}
          </Badge>
          {detail.fileChangeSummary.recursive ? (
            <Badge size="sm" tone="neutral">
              {uiText.main.detail.labels.includesChildTasks}
            </Badge>
          ) : null}
        </div>
      </div>
      <div className={styles.fileChangeList} role="list">
        {detail.fileChangeSummary.changedFiles.map((file) => {
          const changePresentation = selectFileChangeTypePresentation(
            file.changeType,
            uiText.main,
          );
          const taskNodeId =
            file.ownerTaskNodeId ?? detail.fileChangeSummary.taskNodeId ?? undefined;
          const routeContext = {
            path: file.path,
            returnFocus: "file_change" as const,
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
                  {uiText.main.detail.actions.openFile}
                </a>
                <a
                  href={buildWorkspaceInspectionRoute({
                    ...routeContext,
                    view: "diff",
                  })}
                >
                  {uiText.main.detail.actions.viewDiff}
                </a>
              </div>
            </article>
          );
        })}
      </div>
      {detail.result && (
        <div className={styles.actionRow}>
          <Button onClick={onShowResult}>
            {uiText.main.detail.actions.viewResult}
          </Button>
        </div>
      )}
    </Panel>
  );
}

function TaskDetailPanel({
  detail,
  loadTokenUsageSummary,
  onRetryTask,
  onStopTask,
  sessionId,
  workspaceId,
}: {
  detail: TaskDetail;
  loadTokenUsageSummary?: LoadTokenUsageSummary;
  onRetryTask: (taskNodeId: TaskNodeId) => void;
  onStopTask: (taskNodeId: TaskNodeId) => void;
  sessionId?: SessionId | null;
  workspaceId?: WorkspaceId | null;
}) {
  const uiText = useUiText();
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
  const shouldShowUsage = Boolean(loadTokenUsageSummary && sessionId);

  if (
    !shouldShowUsage &&
    !showPublishedStopAction &&
    !showRetryAction &&
    !hasStructuredDetails
  ) {
    return null;
  }

  return (
    <>
      {sessionId ? (
        <MainPageTokenUsageSummaryCard
          loadTokenUsageSummary={loadTokenUsageSummary}
          request={tokenUsageRequestForTaskDetail(detail, sessionId)}
          workspaceId={workspaceId}
        />
      ) : null}
      {hasStructuredDetails && (
        <Panel
          aria-label={uiText.main.detail.labels.taskDetails}
          className={styles.detailBox}
          data-task-node-id={detail.selectedTask.id}
          tone="muted"
        >
          <Text as="strong" variant="label">
            {uiText.main.detail.labels.taskDetails}
          </Text>
          {shouldShowIntent && (
            <TaskDetailSection title={uiText.main.detail.labels.intent}>
              {intent}
            </TaskDetailSection>
          )}
          {instructions && (
            <TaskDetailSection title={uiText.main.detail.labels.instructions}>
              {instructions}
            </TaskDetailSection>
          )}
          {acceptanceCriteria.length > 0 && (
            <div className={styles.taskDetailSection}>
              <Text as="strong" variant="label">
                {uiText.main.detail.labels.acceptanceCriteria}
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
          aria-label={uiText.main.detail.labels.taskActions}
          className={styles.detailBox}
          data-task-node-id={detail.selectedTask.id}
          tone="muted"
        >
          <Text as="strong" variant="label">
            {uiText.main.detail.labels.taskActions}
          </Text>
          {showPublishedStopAction && (
            <div className={styles.actionRow}>
              <Button
                disabled={detail.isStoppingTask || isStopping}
                onClick={() => onStopTask(detail.selectedTask.id)}
                variant="danger"
              >
                <CircleStop size={14} aria-hidden="true" />
                {detail.isStoppingTask || isStopping
                  ? uiText.main.detail.actions.stopping
                  : uiText.main.detail.actions.stop}
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
                {detail.isRetryingTask
                  ? uiText.main.detail.actions.retrying
                  : uiText.main.detail.actions.retry}
              </Button>
            </div>
          )}
        </Panel>
      )}
    </>
  );
}

function tokenUsageRequestForTaskDetail(
  detail: TaskDetail,
  sessionId: SessionId,
): TokenUsageSummaryRequest {
  if (detail.selectedTask.taskRef?.kind === "draft") {
    return {
      dimension: "session",
      sessionId,
    };
  }

  return {
    dimension: "task",
    sessionId,
    taskNodeId: detail.selectedTask.id,
  };
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
