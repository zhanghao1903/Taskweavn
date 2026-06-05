import type {
  TaskNodeId,
  TaskTreeView,
} from "../../shared/api/types";
import { Panel, Text } from "../../shared/components";
import { TaskNodeCard } from "./TaskNodeCard";
import styles from "./MainPage.module.css";

export type TaskTreePanelProps = {
  isGeneratingTaskPlan?: boolean;
  onRetryTask: (nodeId: TaskNodeId) => void;
  onSelectTask: (nodeId: TaskNodeId) => void;
  onStopTask: (nodeId: TaskNodeId) => void;
  selectedTaskNodeId: TaskNodeId | null;
  taskTree: TaskTreeView | null;
};

export function TaskTreePanel({
  isGeneratingTaskPlan = false,
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
      ) : isGeneratingTaskPlan ? (
        <TaskPlanGeneratingState />
      ) : (
        <div className={styles.emptyState}>
          <Text as="h3" variant="subheading">
            No task plan yet
          </Text>
          <Text variant="muted">
            Describe a goal. Plato will draft a task plan for review.
          </Text>
        </div>
      )}
    </Panel>
  );
}

function TaskPlanGeneratingState() {
  return (
    <div
      aria-label="Generating task plan"
      className={styles.generatingTaskPlan}
      role="status"
    >
      <div className={styles.generatingTaskPlanHeader}>
        <Text as="h3" variant="subheading">
          Generating task plan
        </Text>
        <Text variant="muted">
          Plato is understanding your goal and shaping the first task plan.
        </Text>
      </div>
      <div aria-hidden="true" className={styles.generatingSkeleton}>
        {Array.from({ length: SKELETON_GROUP_COUNT }, (_, index) => (
          <div className={styles.generatingSkeletonGroup} key={`group-${index}`}>
            <span />
            <span />
          </div>
        ))}
      </div>
    </div>
  );
}

const SKELETON_GROUP_COUNT = 5;
