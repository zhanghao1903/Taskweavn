import { Circle, GitBranch } from "lucide-react";

import type {
  TaskNodeCardView,
  TaskNodeId,
  TaskNodeStatus,
  TaskTreeView,
} from "../../shared/api/types";
import type { BadgeTone } from "../../shared/components";
import { Badge, Panel, Text } from "../../shared/components";
import type { ConfirmationDecision } from "./mainPageUiTypes";
import styles from "./MainPage.module.css";

const taskStatusTone: Record<TaskNodeStatus, BadgeTone> = {
  cancelled: "danger",
  done: "success",
  draft: "neutral",
  failed: "danger",
  queued: "neutral",
  running: "blue",
  waiting_user: "warning",
};

const taskStatusLabel: Record<TaskNodeStatus, string> = {
  cancelled: "cancelled",
  done: "done",
  draft: "draft",
  failed: "failed",
  queued: "queued",
  running: "running",
  waiting_user: "waiting user",
};

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
                <Badge className={styles.taskStatus} tone={taskStatusTone[status]}>
                  {taskStatusLabel[status]}
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
