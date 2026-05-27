import { Circle } from "lucide-react";

import type {
  TaskNodeCardView,
  TaskNodeId,
  TaskNodeStatus,
} from "../../shared/api/types";
import { Badge } from "../../shared/components";
import { selectTaskNodeStatusPresentation } from "./mainPageSelectors";
import styles from "./MainPage.module.css";

export type TaskNodeCardProps = {
  isSelected: boolean;
  node: TaskNodeCardView;
  onSelectTask: (nodeId: TaskNodeId) => void;
  status: TaskNodeStatus;
};

export function TaskNodeCard({
  isSelected,
  node,
  onSelectTask,
  status,
}: TaskNodeCardProps) {
  const statusPresentation = selectTaskNodeStatusPresentation(status);

  return (
    <button
      className={isSelected ? styles.selectedTaskCard : styles.taskCard}
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
  );
}
