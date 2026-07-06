import type {
  SessionMessageView,
  TaskNodeCardView,
} from "../../shared/api/types";
import { Button } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import { selectMessageKindPresentation } from "./mainPageSelectors";
import styles from "./MainPage.module.css";

export type LatestActivityStripProps = {
  isMessageScoped: boolean;
  messages: SessionMessageView[];
  onOpenActivity?: (trigger: HTMLElement) => void;
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
  const uiText = useUiText();
  const latestMessage = messages.at(-1);

  if (!latestMessage) {
    return null;
  }

  const kindPresentation = selectMessageKindPresentation(
    latestMessage.kind,
    uiText.main,
  );
  const activityCountLabel =
    isMessageScoped && visibleMessageCount !== totalMessageCount
      ? `${uiText.main.activity.labels.activity} ${visibleMessageCount}/${totalMessageCount}`
      : uiText.main.activity.labels.activityCount({
          count: totalMessageCount,
        });
  const scopeLabel = latestMessage.taskNodeId
    ? selectedTask
      ? uiText.main.activity.labels.currentTask
      : uiText.main.detail.labels.taskActivity
    : uiText.main.detail.labels.sessionActivity;
  const openActivityLabel = selectedTask
    ? uiText.main.detail.actions.openTaskUpdates
    : uiText.main.detail.actions.openSessionActivity;

  return (
    <aside
      className={styles.latestActivityStrip}
      aria-label={uiText.main.detail.labels.latestActivity}
    >
      <span className={styles.latestActivityDot} aria-hidden="true" />
      <div className={styles.latestActivityContent}>
        <span>{latestActivityLabel(scopeLabel, kindPresentation.label)}</span>
        <strong title={latestMessage.title}>{latestMessage.title}</strong>
      </div>
      <div className={styles.latestActivityMeta}>
        {onOpenActivity ? (
          <Button
            aria-label={`${openActivityLabel} (${activityCountLabel})`}
            className={styles.latestActivityButton}
            onClick={(event) => onOpenActivity(event.currentTarget)}
            size="sm"
            variant="secondary"
          >
            {activityCountLabel}
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
  return `${scopeLabel} · ${kindLabel}`;
}
