import type {
  SessionMessageView,
  TaskNodeCardView,
} from "../../shared/api/types";
import { Button } from "../../shared/components";
import { selectMessageKindPresentation } from "./mainPageSelectors";
import styles from "./MainPage.module.css";

export type LatestActivityStripProps = {
  isMessageScoped: boolean;
  messages: SessionMessageView[];
  onOpenActivity?: () => void;
  selectedTask: TaskNodeCardView | undefined;
  totalMessageCount: number;
  visibleMessageCount: number;
};

export function LatestActivityStrip({
  isMessageScoped,
  messages,
  onOpenActivity,
  selectedTask,
  totalMessageCount,
  visibleMessageCount,
}: LatestActivityStripProps) {
  const latestMessage = messages.at(-1);

  if (!latestMessage) {
    return null;
  }

  const kindPresentation = selectMessageKindPresentation(latestMessage.kind);
  const activityCountLabel =
    isMessageScoped && visibleMessageCount !== totalMessageCount
      ? `Activity ${visibleMessageCount}/${totalMessageCount}`
      : `Activity ${totalMessageCount}`;
  const scopeLabel = latestMessage.taskNodeId
    ? selectedTask
      ? "Current task"
      : "Task activity"
    : "Session-wide";

  return (
    <aside className={styles.latestActivityStrip} aria-label="Latest activity">
      <span className={styles.latestActivityDot} aria-hidden="true" />
      <div className={styles.latestActivityContent}>
        <span>{latestActivityLabel(scopeLabel, kindPresentation.label)}</span>
        <strong title={latestMessage.title}>{latestMessage.title}</strong>
      </div>
      <div className={styles.latestActivityMeta}>
        {onOpenActivity ? (
          <Button
            aria-label={`Open activity overlay (${activityCountLabel})`}
            onClick={onOpenActivity}
            size="sm"
            variant="ghost"
          >
            View {activityCountLabel}
          </Button>
        ) : (
          <span className={styles.latestActivityCount}>
            {activityCountLabel}
          </span>
        )}
      </div>
    </aside>
  );
}

function latestActivityLabel(scopeLabel: string, kindLabel: string) {
  return `Latest update · ${scopeLabel} · ${kindLabel}`;
}
