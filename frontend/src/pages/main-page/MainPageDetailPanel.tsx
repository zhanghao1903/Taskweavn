import type {
  ConfirmationActionView,
  FileChangeSummaryView,
  ResultCardView,
  TaskNodeCardView,
} from "../../shared/api/types";
import { Badge, Button, Panel, Text } from "../../shared/components";
import type {
  ConfirmationDecision,
  MainPageDetailHeader,
} from "./mainPageUiTypes";
import { confirmationResolutionText } from "./mainPageCopy";
import {
  selectConfirmationOptionVariant,
  selectFileChangeTypePresentation,
} from "./mainPageSelectors";
import styles from "./MainPage.module.css";

export type MainPageDetailPanelProps = {
  activeConfirmation: ConfirmationActionView | undefined;
  commandError: string | null;
  confirmationDecision: ConfirmationDecision;
  fileChangeSummary: FileChangeSummaryView | null;
  hasConfirmationFocus: boolean;
  hasFileChangeView: boolean;
  hasResultView: boolean;
  header: MainPageDetailHeader;
  isResolvingConfirmation: boolean;
  onConfirmationDecision: (decision: Exclude<ConfirmationDecision, null>) => void;
  onShowFileChanges: () => void;
  onShowResult: () => void;
  result: ResultCardView | null;
  selectedTask: TaskNodeCardView | undefined;
};

export function MainPageDetailPanel({
  activeConfirmation,
  commandError,
  confirmationDecision,
  fileChangeSummary,
  hasConfirmationFocus,
  hasFileChangeView,
  hasResultView,
  header,
  isResolvingConfirmation,
  onConfirmationDecision,
  onShowFileChanges,
  onShowResult,
  result,
  selectedTask,
}: MainPageDetailPanelProps) {
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
        activeConfirmation={activeConfirmation}
        commandError={commandError}
        confirmationDecision={confirmationDecision}
        fallbackBody={header.body}
        fileChangeSummary={fileChangeSummary}
        hasConfirmationFocus={hasConfirmationFocus}
        hasFileChangeView={hasFileChangeView}
        hasResultView={hasResultView}
        isResolvingConfirmation={isResolvingConfirmation}
        onConfirmationDecision={onConfirmationDecision}
        onShowFileChanges={onShowFileChanges}
        onShowResult={onShowResult}
        result={result}
        selectedTask={selectedTask}
      />
    </Panel>
  );
}

type DetailContentProps = {
  activeConfirmation: ConfirmationActionView | undefined;
  commandError: string | null;
  confirmationDecision: ConfirmationDecision;
  fallbackBody: string;
  fileChangeSummary: FileChangeSummaryView | null;
  hasConfirmationFocus: boolean;
  hasFileChangeView: boolean;
  hasResultView: boolean;
  isResolvingConfirmation: boolean;
  onConfirmationDecision: (decision: Exclude<ConfirmationDecision, null>) => void;
  onShowFileChanges: () => void;
  onShowResult: () => void;
  result: ResultCardView | null;
  selectedTask: TaskNodeCardView | undefined;
};

function DetailContent({
  activeConfirmation,
  commandError,
  confirmationDecision,
  fallbackBody,
  fileChangeSummary,
  hasConfirmationFocus,
  hasFileChangeView,
  hasResultView,
  isResolvingConfirmation,
  onConfirmationDecision,
  onShowFileChanges,
  onShowResult,
  result,
  selectedTask,
}: DetailContentProps) {
  if (hasConfirmationFocus) {
    return (
      <Panel className={styles.detailBox} tone="muted">
        <Text as="strong" variant="label">
          {isResolvingConfirmation ? "Submitting decision" : "Decision needed"}
        </Text>
        <Text variant="muted">{activeConfirmation?.body ?? fallbackBody}</Text>
        {commandError && <Text variant="muted">{commandError}</Text>}
        <div className={styles.actionRow}>
          {(activeConfirmation?.options ?? fallbackConfirmationOptions).map(
            (option) => (
              <Button
                disabled={isResolvingConfirmation}
                key={option.value}
                variant={selectConfirmationOptionVariant(option.tone)}
                onClick={() =>
                  onConfirmationDecision(toConfirmationDecision(option.value))
                }
              >
                {option.label}
              </Button>
            ),
          )}
        </div>
      </Panel>
    );
  }

  if (confirmationDecision !== null) {
    return (
      <Panel className={styles.detailBox} tone="muted">
        <Text as="strong" variant="label">
          Confirmation resolved
        </Text>
        <Text variant="muted">
          {confirmationResolutionText[confirmationDecision]}
        </Text>
      </Panel>
    );
  }

  if (hasResultView && result) {
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
        <Text variant="muted">{result.summary}</Text>
        {result.sections && result.sections.length > 0 && (
          <div className={styles.resultSections}>
            {result.sections.map((section) => (
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
        {fileChangeSummary && (
          <div className={styles.actionRow}>
            <Button onClick={onShowFileChanges}>View file changes</Button>
          </div>
        )}
      </Panel>
    );
  }

  if (hasFileChangeView && fileChangeSummary) {
    return (
      <Panel className={styles.detailBox} tone="muted">
        <div className={styles.detailTitleRow}>
          <Text as="strong" variant="label">
            Changed files
          </Text>
          <Badge size="sm" tone={fileChangeSummary.recursive ? "blue" : "neutral"}>
            {fileChangeSummary.recursive
              ? "Recursive subtree summary"
              : "Direct task changes"}
          </Badge>
        </div>
        <Text variant="muted">{fileChangeSummary.summary}</Text>
        <div className={styles.fileChangeList} role="list">
          {fileChangeSummary.changedFiles.map((file) => {
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
        {result && (
          <div className={styles.actionRow}>
            <Button onClick={onShowResult}>View result</Button>
          </div>
        )}
      </Panel>
    );
  }

  if (selectedTask) {
    return (
      <Panel className={styles.detailBox} tone="muted">
        <Text as="strong" variant="label">
          Task interaction
        </Text>
        <Text variant="muted">
          Input now applies to this TaskNode. Completed TaskNodes are read-only;
          running TaskNodes accept appended guidance.
        </Text>
      </Panel>
    );
  }

  return (
    <Panel className={styles.detailBox} tone="muted">
      <Text as="strong" variant="label">
        State note
      </Text>
      <Text variant="muted">{fallbackBody}</Text>
    </Panel>
  );
}

const fallbackConfirmationOptions: NonNullable<
  ConfirmationActionView["options"]
> = [
  { value: "confirmed", label: "Confirm", tone: "primary" },
  { value: "revise", label: "Revise task", tone: "secondary" },
  { value: "skipped", label: "Skip", tone: "danger" },
];

function toConfirmationDecision(value: string): Exclude<ConfirmationDecision, null> {
  if (value === "revise" || value === "skipped") {
    return value;
  }

  return "confirmed";
}
