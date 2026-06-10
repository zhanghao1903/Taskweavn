import type { ReactNode } from "react";

import type {
  TaskNodeId,
  TaskTreeView,
} from "../../shared/api/types";
import { Badge, Button, Panel, Text } from "../../shared/components";
import { TaskNodeCard } from "./TaskNodeCard";
import type { MainPageAuthoringDiagnosticViewModel } from "./mainPageViewModel";
import styles from "./MainPage.module.css";

export type TaskTreePanelProps = {
  activitySlot?: ReactNode;
  authoringDiagnostic?: MainPageAuthoringDiagnosticViewModel | null;
  isRepairingAuthoringState?: boolean;
  isTaskPlanSelected?: boolean;
  isGeneratingTaskPlan?: boolean;
  onRetryTask: (nodeId: TaskNodeId) => void;
  onRepairAuthoringState?: () => void;
  onSelectTaskPlan: () => void;
  onSelectTask: (nodeId: TaskNodeId) => void;
  onStopTask: (nodeId: TaskNodeId) => void;
  selectedTaskNodeId: TaskNodeId | null;
  taskTree: TaskTreeView | null;
};

export function TaskTreePanel({
  activitySlot = null,
  authoringDiagnostic = null,
  isRepairingAuthoringState = false,
  isTaskPlanSelected = false,
  isGeneratingTaskPlan = false,
  onRetryTask,
  onRepairAuthoringState,
  onSelectTaskPlan,
  onSelectTask,
  onStopTask,
  selectedTaskNodeId,
  taskTree,
}: TaskTreePanelProps) {
  if (taskTree) {
    const planOverview = planOverviewContent(taskTree);

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
            <strong className={styles.listCardTitle} title={planOverview.title}>
              {planOverview.title}
            </strong>
            <small className={styles.listCardBody}>
              {planOverview.detail}
            </small>
          </span>
          <Badge tone="blue">{taskTree.status}</Badge>
        </button>
        {authoringDiagnostic ? (
          <div className={styles.authoringDiagnosticBanner} role="status">
            <span className={styles.authoringDiagnosticText}>
              <strong>Authoring state needs repair</strong>
              <small>{authoringDiagnostic.message}</small>
            </span>
            <Button
              aria-label="Repair authoring state"
              disabled={isRepairingAuthoringState || !onRepairAuthoringState}
              onClick={onRepairAuthoringState}
              size="sm"
              variant="secondary"
            >
              {isRepairingAuthoringState ? "Repairing" : "Repair"}
            </Button>
          </div>
        ) : null}
        {activitySlot}
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
const DEFAULT_TASK_TREE_TITLE = "Task Tree";

function planOverviewText(taskTree: TaskTreeView): string {
  if (taskTree.nodes.length === 0) {
    return "Plan overview is being prepared.";
  }

  const visibleTitles = taskTree.nodes.slice(0, 2).map((node) => node.title);
  const remainingCount = taskTree.nodes.length - visibleTitles.length;
  const suffix = remainingCount > 0 ? `, and ${remainingCount} more` : "";
  return `${taskTree.nodes.length}-task plan covering ${visibleTitles.join(", ")}${suffix}.`;
}

function planOverviewContent(taskTree: TaskTreeView): {
  detail: string;
  title: string;
} {
  const title = taskTree.title?.trim();
  const summary = taskTree.summary?.trim();
  const taskCountText =
    taskTree.nodes.length === 1
      ? "1 task in this plan"
      : `${taskTree.nodes.length} tasks in this plan`;

  if (title && title !== DEFAULT_TASK_TREE_TITLE) {
    return {
      title,
      detail: summary && summary !== title ? summary : taskCountText,
    };
  }

  if (summary) {
    return {
      title: summary,
      detail: taskCountText,
    };
  }

  return {
    title: planOverviewText(taskTree),
    detail: taskCountText,
  };
}
