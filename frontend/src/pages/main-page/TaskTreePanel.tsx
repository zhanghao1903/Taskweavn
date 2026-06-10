import type { ReactNode } from "react";

import type {
  TaskNodeId,
  TaskTreeView,
} from "../../shared/api/types";
import { Badge, Button, Panel, Text } from "../../shared/components";
import { useUiText, type UiTextCatalog } from "../../shared/ui-text";
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
  const uiText = useUiText();

  if (taskTree) {
    const planOverview = planOverviewContent(taskTree, uiText);

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
            <span className={styles.planEyebrow}>
              {uiText.main.plan.overviewLabel}
            </span>
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
              <strong>{uiText.main.repair.authoringStateNeedsRepair}</strong>
              <small>{authoringDiagnostic.message}</small>
            </span>
            <Button
              aria-label={uiText.main.actions.repairAuthoringState}
              disabled={isRepairingAuthoringState || !onRepairAuthoringState}
              onClick={onRepairAuthoringState}
              size="sm"
              variant="secondary"
            >
              {isRepairingAuthoringState
                ? uiText.main.repair.repairing
                : uiText.main.actions.repairAuthoringState}
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
        <TaskPlanGeneratingState uiText={uiText} />
      ) : (
        <div className={styles.emptyState}>
          <Text as="h3" variant="subheading">
            {uiText.main.empty.noPlanTitle}
          </Text>
          <Text variant="muted">
            {uiText.main.empty.noPlanBody}
          </Text>
        </div>
      )}
    </Panel>
  );
}

function TaskPlanGeneratingState({ uiText }: { uiText: UiTextCatalog }) {
  return (
    <div
      aria-label={uiText.main.plan.generatingTitle}
      className={styles.generatingTaskPlan}
      role="status"
    >
      <div className={styles.generatingTaskPlanHeader}>
        <Text as="h3" variant="subheading">
          {uiText.main.plan.generatingTitle}
        </Text>
        <Text variant="muted">
          {uiText.main.plan.generatingBody}
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

function planOverviewText(
  taskTree: TaskTreeView,
  uiText: UiTextCatalog,
): string {
  if (taskTree.nodes.length === 0) {
    return uiText.main.plan.overviewPrepared;
  }

  const visibleTitles = taskTree.nodes.slice(0, 2).map((node) => node.title);
  const remainingCount = taskTree.nodes.length - visibleTitles.length;
  return uiText.main.plan.overviewSummary({
    count: taskTree.nodes.length,
    remainingCount,
    titles: visibleTitles.join(", "),
  });
}

function planOverviewContent(
  taskTree: TaskTreeView,
  uiText: UiTextCatalog,
): {
  detail: string;
  title: string;
} {
  const title = taskTree.title?.trim();
  const summary = taskTree.summary?.trim();
  const taskCountText = uiText.main.plan.taskCount({
    count: taskTree.nodes.length,
  });

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
    title: planOverviewText(taskTree, uiText),
    detail: taskCountText,
  };
}
