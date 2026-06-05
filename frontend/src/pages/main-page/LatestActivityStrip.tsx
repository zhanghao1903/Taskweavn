import type {
  SessionMessageView,
  TaskNodeCardView,
} from "../../shared/api/types";
import { Badge, Button, Text } from "../../shared/components";
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
      ? `${visibleMessageCount}/${totalMessageCount} shown`
      : `${totalMessageCount} ${totalMessageCount === 1 ? "activity" : "activities"}`;
  const scopeLabel = latestMessage.taskNodeId
    ? selectedTask
      ? "Current task"
      : "Task activity"
    : "Session-wide";

  return (
    <aside className={styles.latestActivityStrip} aria-label="Latest activity">
      <div className={styles.latestActivityLabel}>
        <Text as="span" variant="eyebrow">
          Latest activity
        </Text>
        <Badge size="sm" tone={kindPresentation.tone}>
          {kindPresentation.label}
        </Badge>
      </div>
      <div className={styles.latestActivityContent}>
        <strong title={latestMessage.title}>{latestMessage.title}</strong>
      </div>
      <div className={styles.latestActivityMeta}>
        <Badge size="sm" tone={isMessageScoped ? "blue" : "neutral"}>
          {scopeLabel}
        </Badge>
        <Badge size="sm" tone="neutral">
          {activityCountLabel}
        </Badge>
        {onOpenActivity ? (
          <Button
            aria-label="Open activity overlay"
            onClick={onOpenActivity}
            size="sm"
            variant="ghost"
          >
            View
          </Button>
        ) : null}
      </div>
    </aside>
  );
}
