import { GitBranch } from "lucide-react";

import type {
  TaskNodeCardView,
  TaskNodeId,
  TaskNodeStatus,
  TaskTreeView,
} from "../../shared/api/types";
import { Panel, Text } from "../../shared/components";
import type { ConfirmationDecision } from "./mainPageUiTypes";
import { TaskNodeCard } from "./TaskNodeCard";
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
          {taskTree.nodes.map((node) => (
            <TaskNodeCard
              isSelected={node.id === selectedTaskNodeId}
              key={node.id}
              node={node}
              onSelectTask={onSelectTask}
              status={statusForNode(node, confirmationDecision)}
            />
          ))}
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
