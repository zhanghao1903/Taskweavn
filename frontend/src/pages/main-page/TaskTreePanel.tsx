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
  onStopTask: (nodeId: TaskNodeId) => void;
  selectedTaskNodeId: TaskNodeId | null;
  taskTree: TaskTreeView | null;
};

export function TaskTreePanel({
  onRetryTask,
  onSelectTask,
  onStopTask,
  selectedTaskNodeId,
  taskTree,
}: TaskTreePanelProps) {
  return (
    <Panel
      className={styles.workPanel}
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
              onStopTask={onStopTask}
            />
          ))}
        </div>
      ) : (
        <div className={styles.emptyState}>
          <Text as="h3" variant="subheading">
            No task plan yet
          </Text>
          <Text variant="muted">
            Describe your goal. Plato will turn it into a task structure for
            review before execution.
          </Text>
        </div>
      )}
    </Panel>
  );
}
