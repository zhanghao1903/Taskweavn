import { useMemo, useState } from "react";

import type {
  SessionMessageView,
  TaskNodeCardView,
} from "../../shared/api/types";
import { Badge, Button, Text } from "../../shared/components";
import { selectMessageKindPresentation } from "./mainPageSelectors";
import styles from "./ActivityOverlay.module.css";

type ActivityFilter = "currentTask" | "all" | "results" | "errors";

export type ActivityOverlayProps = {
  allMessages: SessionMessageView[];
  currentMessages: SessionMessageView[];
  onClose: () => void;
  selectedTask: TaskNodeCardView | undefined;
};

const filterLabels: Record<ActivityFilter, string> = {
  all: "All",
  currentTask: "Current task",
  errors: "Errors",
  results: "Results",
};

export function ActivityOverlay({
  allMessages,
  currentMessages,
  onClose,
  selectedTask,
}: ActivityOverlayProps) {
  const [activeFilter, setActiveFilter] = useState<ActivityFilter>(
    selectedTask ? "currentTask" : "all",
  );
  const [readerMessage, setReaderMessage] =
    useState<SessionMessageView | null>(null);
  const messages = useMemo(
    () =>
      selectOverlayMessages({
        activeFilter,
        allMessages,
        currentMessages,
      }),
    [activeFilter, allMessages, currentMessages],
  );

  return (
    <aside
      aria-label="Task updates"
      className={styles.overlay}
      role="dialog"
    >
      <div className={styles.header}>
        <div>
          <Text as="span" variant="eyebrow">
            Activity
          </Text>
          <h2>Task updates</h2>
          <p>
            {selectedTask
              ? `Focused on ${selectedTask.title}.`
              : "Session-wide activity."}
          </p>
        </div>
        <Button onClick={onClose} size="sm" variant="secondary">
          Close
        </Button>
      </div>

      <div aria-label="Activity filters" className={styles.filters}>
        {(["currentTask", "all", "results", "errors"] as const).map(
          (filter) => (
            <button
              aria-pressed={activeFilter === filter}
              className={
                activeFilter === filter ? styles.activeFilter : styles.filter
              }
              disabled={filter === "currentTask" && !selectedTask}
              key={filter}
              onClick={() => setActiveFilter(filter)}
              type="button"
            >
              {filterLabels[filter]}
            </button>
          ),
        )}
      </div>

      {readerMessage ? (
        <ResultReader
          message={readerMessage}
          onBack={() => setReaderMessage(null)}
        />
      ) : messages.length === 0 ? (
        <div className={styles.emptyState}>
          <strong>No matching activity</strong>
          <p>
            {selectedTask
              ? "Try another filter or return to the selected task."
              : "Try another filter or close this view."}
          </p>
        </div>
      ) : (
        <ol className={styles.timeline}>
          {messages.map((message) => (
            <ActivityItem
              key={message.id}
              message={message}
              onOpenReader={() => setReaderMessage(message)}
            />
          ))}
        </ol>
      )}
    </aside>
  );
}

function ActivityItem({
  message,
  onOpenReader,
}: {
  message: SessionMessageView;
  onOpenReader: () => void;
}) {
  const kindPresentation = selectMessageKindPresentation(message.kind);
  const scopeLabel = message.taskNodeId ? "Task" : "Session";
  const isResult = isResultActivity(message);

  return (
    <li className={styles.activityItem}>
      <div className={styles.itemHeader}>
        <Badge size="sm" tone={kindPresentation.tone}>
          {kindPresentation.label}
        </Badge>
        <time dateTime={message.createdAt}>
          {formatActivityTime(message.createdAt)}
        </time>
      </div>
      <strong title={message.title}>{message.title}</strong>
      <p>{message.body}</p>
      <div className={styles.itemMeta}>
        <Badge size="sm" tone={message.taskNodeId ? "blue" : "neutral"}>
          {scopeLabel}
        </Badge>
        {isResult && (
          <Button onClick={onOpenReader} size="sm" variant="ghost">
            View full result
          </Button>
        )}
      </div>
    </li>
  );
}

function ResultReader({
  message,
  onBack,
}: {
  message: SessionMessageView;
  onBack: () => void;
}) {
  return (
    <section aria-label="Full result" className={styles.reader}>
      <div className={styles.readerHeader}>
        <div>
          <Text as="span" variant="eyebrow">
            Full result
          </Text>
          <h3>{message.title}</h3>
        </div>
        <Button onClick={onBack} size="sm" variant="secondary">
          Back to activity
        </Button>
      </div>
      <article className={styles.readerBody}>
        <Badge size="sm" tone="blue">
          Result
        </Badge>
        <p>{message.body}</p>
      </article>
    </section>
  );
}

function selectOverlayMessages({
  activeFilter,
  allMessages,
  currentMessages,
}: {
  activeFilter: ActivityFilter;
  allMessages: SessionMessageView[];
  currentMessages: SessionMessageView[];
}) {
  const source = activeFilter === "currentTask" ? currentMessages : allMessages;
  const filtered =
    activeFilter === "errors"
      ? allMessages.filter((message) => message.kind === "error")
      : activeFilter === "results"
        ? allMessages.filter(isResultActivity)
        : source;

  return filtered
    .slice()
    .sort(
      (left, right) =>
        Date.parse(right.createdAt) - Date.parse(left.createdAt),
    );
}

function isResultActivity(message: SessionMessageView) {
  const searchable = `${message.title} ${message.body}`.toLowerCase();

  return (
    message.kind === "response" ||
    searchable.includes("result") ||
    searchable.includes("summary") ||
    searchable.includes("completed")
  );
}

function formatActivityTime(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en", {
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    day: "2-digit",
  }).format(date);
}
