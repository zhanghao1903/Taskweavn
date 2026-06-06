import type {
  TaskNodeId,
  TaskTreeView,
} from "../../shared/api/types";
import { Badge, Panel, Text } from "../../shared/components";
import { TaskNodeCard } from "./TaskNodeCard";
import styles from "./MainPage.module.css";

export type TaskTreePanelProps = {
  isTaskPlanSelected?: boolean;
  isGeneratingTaskPlan?: boolean;
  onRetryTask: (nodeId: TaskNodeId) => void;
  onSelectTaskPlan: () => void;
  onSelectTask: (nodeId: TaskNodeId) => void;
  onStopTask: (nodeId: TaskNodeId) => void;
  selectedTaskNodeId: TaskNodeId | null;
  taskTree: TaskTreeView | null;
};

export function TaskTreePanel({
  isTaskPlanSelected = false,
  isGeneratingTaskPlan = false,
  onRetryTask,
  onSelectTaskPlan,
  onSelectTask,
  onStopTask,
  selectedTaskNodeId,
  taskTree,
}: TaskTreePanelProps) {
  if (taskTree) {
    return (
      <div className={styles.taskListPanel}>
        <button
          aria-pressed={isTaskPlanSelected}
          className={
            isTaskPlanSelected ? styles.selectedPlanCard : styles.planCard
          }
          onClick={onSelectTaskPlan}
          type="button"
        >
          <span className={styles.planText}>
            <span className={styles.planEyebrow}>Plan overview</span>
            <strong className={styles.listCardTitle} title={taskTree.title}>
              {taskTree.title}
            </strong>
            <small className={styles.listCardBody}>
              {taskTree.nodes.length === 1
                ? "1 task in this plan"
                : `${taskTree.nodes.length} tasks in this plan`}
            </small>
          </span>
          <Badge tone="blue">{taskTree.status}</Badge>
        </button>
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
      </div>
    );
  }

  return (
    <Panel
      className={styles.workPanel}
      tone="surface"
    >
      {isGeneratingTaskPlan ? (
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
