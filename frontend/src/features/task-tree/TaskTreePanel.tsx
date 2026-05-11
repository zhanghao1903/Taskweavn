import { CheckCircle2, Circle, Clock3, Loader2, PlayCircle, XCircle } from "lucide-react";
import type { CSSProperties } from "react";

import type { TaskId, TaskNodeSummary, TaskStatus, TaskTreeView } from "../../api/contracts";

type Props = {
  trees: TaskTreeView[];
  activeTaskId: TaskId | null;
  isLoading: boolean;
  onSelectTask(taskId: TaskId): void;
};

export function TaskTreePanel({
  activeTaskId,
  isLoading,
  trees,
  onSelectTask,
}: Props) {
  return (
    <aside className="panel task-tree-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Task topology</p>
          <h2>Task Tree List</h2>
        </div>
        <span className="count-pill">{trees.length}</span>
      </div>

      {isLoading ? (
        <div className="empty-state">Loading task tree...</div>
      ) : (
        <div className="task-tree-list">
          {trees.flatMap((tree) =>
            tree.nodes.map((task) => (
              <TaskNodeButton
                active={task.taskId === activeTaskId}
                key={task.taskId}
                task={task}
                onSelectTask={onSelectTask}
              />
            )),
          )}
        </div>
      )}
    </aside>
  );
}

function TaskNodeButton({
  active,
  task,
  onSelectTask,
}: {
  active: boolean;
  task: TaskNodeSummary;
  onSelectTask(taskId: TaskId): void;
}) {
  return (
    <button
      className={`task-node-button ${active ? "active" : ""}`}
      onClick={() => onSelectTask(task.taskId)}
      style={{ "--task-depth": task.depth } as CSSProperties}
      type="button"
    >
      <StatusIcon status={task.status} />
      <span className="task-node-copy">
        <strong>{task.title}</strong>
        <small>{task.intentPreview}</small>
      </span>
      <span className="task-node-meta">
        {task.hasPendingConfirmation ? <span className="dot warning" /> : null}
        {task.fileChangeCount > 0 ? `${task.fileChangeCount} files` : task.status}
      </span>
    </button>
  );
}

function StatusIcon({ status }: { status: TaskStatus }) {
  if (status === "done") return <CheckCircle2 className="status-icon done" size={18} />;
  if (status === "running") return <PlayCircle className="status-icon running" size={18} />;
  if (status === "pending") return <Clock3 className="status-icon pending" size={18} />;
  if (status === "failed") return <XCircle className="status-icon failed" size={18} />;
  if (status === "draft") return <Circle className="status-icon draft" size={18} />;
  return <Loader2 className="status-icon" size={18} />;
}
