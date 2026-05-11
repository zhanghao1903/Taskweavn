import { FileText, Lock, MessageCircle, PencilLine } from "lucide-react";

import type { TaskFileChangeSummary, TaskNodeDetail } from "../../api/contracts";

type Props = {
  detail: TaskNodeDetail | undefined;
  fileChanges: TaskFileChangeSummary[];
  isLoading: boolean;
};

export function TaskDetailPanel({ detail, fileChanges, isLoading }: Props) {
  if (isLoading || !detail) {
    return (
      <section className="panel task-detail-panel">
        <div className="empty-state">Select a task to inspect its details.</div>
      </section>
    );
  }

  const editable = detail.permissions.canEdit;

  return (
    <section className="panel task-detail-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Selected task</p>
          <h2>{detail.summary.title}</h2>
        </div>
        <span className={`status-chip ${detail.summary.status}`}>
          {detail.summary.status}
        </span>
      </div>

      <p className="task-intent">{detail.intent}</p>

      <div className="detail-grid">
        <div className="detail-box">
          <div className="detail-box-title">
            <PencilLine size={16} />
            Constraints
          </div>
          <ul>
            {detail.constraints.map((constraint) => (
              <li key={constraint}>{constraint}</li>
            ))}
          </ul>
        </div>

        <div className="detail-box">
          <div className="detail-box-title">
            {editable ? <MessageCircle size={16} /> : <Lock size={16} />}
            Permissions
          </div>
          <p>
            {editable
              ? "This task can still be edited before execution."
              : "This task is read-only; add follow-up work through a new task."}
          </p>
        </div>
      </div>

      <div className="detail-box file-box">
        <div className="detail-box-title">
          <FileText size={16} />
          File change summary
        </div>
        {fileChanges.length ? (
          <ul className="file-list">
            {fileChanges.map((change) => (
              <li key={change.fileChangeId}>
                <span className="file-change-type">{change.changeType}</span>
                <span>
                  <strong>{change.path}</strong>
                  <small>
                    {change.summary}
                    {change.fromDescendant ? " · from child task" : ""}
                  </small>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p>No file changes recorded yet.</p>
        )}
      </div>
    </section>
  );
}
