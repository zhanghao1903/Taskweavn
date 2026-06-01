import { GitBranch } from "lucide-react";

import type {
  TaskNodeId,
  TaskTreeView,
} from "../../shared/api/types";
import { Panel, Text } from "../../shared/components";
import { TaskNodeCard } from "./TaskNodeCard";
import styles from "./MainPage.module.css";

export type TaskTreePanelProps = {
  onRetryTask: (nodeId: TaskNodeId) => void;
  onSelectTask: (nodeId: TaskNodeId) => void;
  selectedTaskNodeId: TaskNodeId | null;
  taskTree: TaskTreeView | null;
};

export function TaskTreePanel({
  onRetryTask,
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
      tone="surface"
    >
      {taskTree ? (
        <div className={styles.taskList}>
          {taskTree.nodes.map((node) => (
            <TaskNodeCard
              isSelected={node.id === selectedTaskNodeId}
              key={node.id}
              node={node}
              onRetryTask={onRetryTask}
              onSelectTask={onSelectTask}
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
