import type { Ref } from "react";
import { CircleStop, RotateCcw } from "lucide-react";

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
  selectButtonRef?: Ref<HTMLButtonElement>;
};

export function TaskNodeCard({
  isSelected,
  node,
  onRetryTask,
  onSelectTask,
  onStopTask,
  selectButtonRef,
}: TaskNodeCardProps) {
  const statusPresentation = selectTaskNodeDimensionPresentation(node);
  const isRunning = node.execution === "running" || node.status === "running";
  const displayIndex = node.displayIndex ?? node.orderIndex + 1;
  const isStopping = Boolean(
    node.interruptionRequested && isRunning,
  );
  const showStopAction =
    node.taskRef?.kind === "published" &&
    isRunning &&
    (node.permissions.canCancel || isStopping);

  return (
    <div
      className={isSelected ? styles.selectedTaskCard : styles.taskCard}
    >
      <button
        className={styles.taskSelectButton}
        onClick={() => onSelectTask(node.id)}
        ref={selectButtonRef}
        type="button"
      >
        <span className={styles.taskIndex}>Task {displayIndex}</span>
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
