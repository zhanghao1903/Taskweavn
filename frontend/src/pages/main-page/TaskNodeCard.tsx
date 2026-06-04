import { Circle, CircleStop, RotateCcw } from "lucide-react";

import type { TaskNodeCardView, TaskNodeId } from "../../shared/api/types";
import { Badge, Button } from "../../shared/components";
import { selectTaskNodeDimensionPresentation } from "./mainPageSelectors";
import styles from "./MainPage.module.css";

export type TaskNodeCardProps = {
  isSelected: boolean;
  node: TaskNodeCardView;
  onRetryTask: (nodeId: TaskNodeId) => void;
  onSelectTask: (nodeId: TaskNodeId) => void;
  onStopTask: (nodeId: TaskNodeId) => void;
};

export function TaskNodeCard({
  isSelected,
  node,
  onRetryTask,
  onSelectTask,
  onStopTask,
}: TaskNodeCardProps) {
  const statusPresentation = selectTaskNodeDimensionPresentation(node);
  const isStopping = Boolean(
    node.interruptionRequested &&
      (node.execution === "running" || node.status === "running"),
  );
  const showStopAction =
    node.taskRef?.kind === "published" && (node.permissions.canCancel || isStopping);

  return (
    <div
      className={isSelected ? styles.selectedTaskCard : styles.taskCard}
    >
      <button
        className={styles.taskSelectButton}
        onClick={() => onSelectTask(node.id)}
        type="button"
      >
        <Circle size={12} aria-hidden="true" />
        <span className={styles.taskText}>
          <strong className={styles.listCardTitle} title={node.title}>
            {node.title}
          </strong>
          <small className={styles.listCardBody} title={node.summary}>
            {node.summary}
          </small>
        </span>
        <Badge className={styles.taskStatus} tone={statusPresentation.tone}>
          {statusPresentation.label}
        </Badge>
      </button>
      <div className={styles.taskInlineActions}>
        {showStopAction ? (
          <Button
            className={styles.taskRetryButton}
            disabled={isStopping}
            onClick={() => onStopTask(node.id)}
            size="sm"
            variant="danger"
          >
            <CircleStop size={14} aria-hidden="true" />
            {isStopping ? "Stopping" : "Stop"}
          </Button>
        ) : null}
        {node.permissions.canRetry ? (
          <Button
            className={styles.taskRetryButton}
            onClick={() => onRetryTask(node.id)}
            size="sm"
            variant="primary"
          >
            <RotateCcw size={14} aria-hidden="true" />
            Retry
          </Button>
        ) : null}
      </div>
    </div>
  );
}
