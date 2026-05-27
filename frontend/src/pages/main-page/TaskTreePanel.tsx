import { Circle, GitBranch } from "lucide-react";

import type {
  TaskNodeCardView,
  TaskNodeId,
  TaskNodeStatus,
  TaskTreeView,
} from "../../shared/api/types";
import { Badge, Panel, Text } from "../../shared/components";
import type { ConfirmationDecision } from "./mainPageUiTypes";
import { selectTaskNodeStatusPresentation } from "./mainPageSelectors";
import styles from "./MainPage.module.css";

export type TaskTreePanelProps = {
  confirmationDecision: ConfirmationDecision;
  onSelectTask: (nodeId: TaskNodeId) => void;
  selectedTaskNodeId: TaskNodeId | null;
  taskTree: TaskTreeView | null;
};

export function TaskTreePanel({
  confirmationDecision,
  onSelectTask,
  selectedTaskNodeId,
  taskTree,
}: TaskTreePanelProps) {
  return (
    <Panel
      className={styles.workPanel}
      icon={<GitBranch size={18} aria-hidden="true" />}
      title="TaskTree"
      titleId="tasktree-title"
      tone="muted"
    >
      {taskTree ? (
        <div className={styles.taskList}>
          {taskTree.nodes.map((node) => {
            const status = statusForNode(node, confirmationDecision);
            const statusPresentation = selectTaskNodeStatusPresentation(status);

            return (
              <button
                className={
                  node.id === selectedTaskNodeId
                    ? styles.selectedTaskCard
                    : styles.taskCard
                }
                key={node.id}
                onClick={() => onSelectTask(node.id)}
                type="button"
              >
                <Circle size={12} aria-hidden="true" />
                <span className={styles.taskText}>
                  <strong>{node.title}</strong>
                  <small>{node.summary}</small>
                </span>
                <Badge
                  className={styles.taskStatus}
                  tone={statusPresentation.tone}
                >
                  {statusPresentation.label}
                </Badge>
              </button>
            );
          })}
        </div>
      ) : (
        <div className={styles.emptyState}>
          <Text as="h3" variant="subheading">
            No TaskTree yet
          </Text>
          <Text variant="muted">
            Enter a goal. Plato will first understand it, then produce a draft
            TaskTree for review.
          </Text>
        </div>
      )}
    </Panel>
  );
}

function statusForNode(
  node: TaskNodeCardView,
  decision: ConfirmationDecision,
): TaskNodeStatus {
  if (node.id !== "task-visual-direction") {
    return node.status;
  }

  if (decision === "confirmed") {
    return "done";
  }

  if (decision === "revise") {
    return "draft";
  }

  return node.status;
}
