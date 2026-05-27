import type {
  ConfirmationActionView,
} from "../../shared/api/types";
import { Badge, Button, Panel, Text } from "../../shared/components";
import type { ConfirmationDecision } from "./mainPageUiTypes";
import { confirmationResolutionText } from "./mainPageCopy";
import {
  selectConfirmationOptionVariant,
  selectFileChangeTypePresentation,
} from "./mainPageSelectors";
import type { MainPageDetailView } from "./mainPageViewModel";
import styles from "./MainPage.module.css";

export type MainPageDetailPanelProps = {
  detail: MainPageDetailView;
  onConfirmationDecision: (decision: Exclude<ConfirmationDecision, null>) => void;
  onShowFileChanges: () => void;
  onShowResult: () => void;
};

export function MainPageDetailPanel({
  detail,
  onConfirmationDecision,
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
        onConfirmationDecision={onConfirmationDecision}
        onShowFileChanges={onShowFileChanges}
        onShowResult={onShowResult}
      />
    </Panel>
  );
}

type DetailContentProps = {
  detail: MainPageDetailView;
  onConfirmationDecision: (decision: Exclude<ConfirmationDecision, null>) => void;
  onShowFileChanges: () => void;
  onShowResult: () => void;
};

function DetailContent({
  detail,
  onConfirmationDecision,
  onShowFileChanges,
  onShowResult,
}: DetailContentProps) {
  if (detail.kind === "confirmation") {
    return (
      <Panel className={styles.detailBox} tone="muted">
        <Text as="strong" variant="label">
          {detail.isResolvingConfirmation
            ? "Submitting decision"
            : "Decision needed"}
        </Text>
        <Text variant="muted">
          {detail.confirmation?.body ?? detail.fallbackBody}
        </Text>
        {detail.commandError && (
          <Text variant="muted">{detail.commandError}</Text>
        )}
        <div className={styles.actionRow}>
          {(detail.confirmation?.options ?? fallbackConfirmationOptions).map(
            (option) => (
              <Button
                disabled={detail.isResolvingConfirmation}
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

  if (detail.kind === "confirmationResolved") {
    return (
      <Panel className={styles.detailBox} tone="muted">
        <Text as="strong" variant="label">
          Confirmation resolved
        </Text>
        <Text variant="muted">
          {confirmationResolutionText[detail.decision]}
        </Text>
      </Panel>
    );
  }

  if (detail.kind === "result") {
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

  if (detail.kind === "fileChanges") {
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

  if (detail.kind === "task") {
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
      <Text variant="muted">{detail.body}</Text>
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
