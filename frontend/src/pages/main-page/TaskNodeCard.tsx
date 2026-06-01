import { Circle, RotateCcw } from "lucide-react";

import type { TaskNodeCardView, TaskNodeId } from "../../shared/api/types";
import { Badge, Button } from "../../shared/components";
import { selectTaskNodeDimensionPresentation } from "./mainPageSelectors";
import styles from "./MainPage.module.css";

export type TaskNodeCardProps = {
  isSelected: boolean;
  node: TaskNodeCardView;
  onRetryTask: (nodeId: TaskNodeId) => void;
  onSelectTask: (nodeId: TaskNodeId) => void;
};

export function TaskNodeCard({
  isSelected,
  node,
  onRetryTask,
  onSelectTask,
}: TaskNodeCardProps) {
  const statusPresentation = selectTaskNodeDimensionPresentation(node);

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
          <strong>{node.title}</strong>
          <small>{node.summary}</small>
        </span>
        <Badge className={styles.taskStatus} tone={statusPresentation.tone}>
          {statusPresentation.label}
        </Badge>
      </button>
      <div className={styles.taskInlineActions}>
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
