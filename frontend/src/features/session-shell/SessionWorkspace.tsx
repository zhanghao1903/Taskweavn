import {
  Activity,
  GitBranch,
  MessageSquare,
  PanelRightOpen,
  ShieldAlert,
} from "lucide-react";
import type { ReactNode } from "react";

import type { SessionId, TaskId } from "../../api/contracts";
import {
  usePendingConfirmations,
  useSessionMessages,
  useSessionOverview,
  useTaskFileChanges,
  useTaskMessages,
  useTaskNode,
  useTaskTrees,
} from "../../api/client";
import { ComposerBar } from "../composer/ComposerBar";
import { ConfirmationPanel } from "../confirmations/ConfirmationPanel";
import { SessionStreamPanel } from "../session-stream/SessionStreamPanel";
import { TaskDetailPanel } from "../task-detail/TaskDetailPanel";
import { TaskTreePanel } from "../task-tree/TaskTreePanel";

type Props = {
  sessionId: SessionId;
  selectedTaskId: TaskId | null;
  onSelectTask(taskId: TaskId): void;
};

export function SessionWorkspace({
  sessionId,
  selectedTaskId,
  onSelectTask,
}: Props) {
  const overview = useSessionOverview(sessionId);
  const taskTrees = useTaskTrees(sessionId);
  const effectiveTaskId =
    selectedTaskId ?? overview.data?.activeTaskId ?? taskTrees.data?.[0]?.rootTaskId ?? null;
  const taskDetail = useTaskNode(sessionId, effectiveTaskId);
  const taskMessages = useTaskMessages(sessionId, effectiveTaskId, "direct");
  const sessionMessages = useSessionMessages(sessionId);
  const confirmations = usePendingConfirmations(sessionId, effectiveTaskId ?? undefined);
  const fileChanges = useTaskFileChanges(sessionId, effectiveTaskId, true);

  return (
    <main className="workspace">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">TaskWeavn UI Prototype</p>
          <h1>{overview.data?.name ?? "Loading session"}</h1>
        </div>
        <div className="header-metrics" aria-label="Session status">
          <Metric
            icon={<Activity size={16} />}
            label="Session"
            value={overview.data?.status ?? "loading"}
          />
          <Metric icon={<GitBranch size={16} />} label="Topology" value="Tree List" />
          <Metric
            icon={<ShieldAlert size={16} />}
            label="Confirmations"
            value={String(overview.data?.pendingConfirmationCount ?? 0)}
          />
        </div>
      </header>

      <section className="workspace-grid" aria-label="TaskWeavn workspace">
        <TaskTreePanel
          activeTaskId={effectiveTaskId}
          isLoading={taskTrees.isLoading}
          trees={taskTrees.data ?? []}
          onSelectTask={onSelectTask}
        />

        <section className="center-column">
          <TaskDetailPanel
            detail={taskDetail.data}
            fileChanges={fileChanges.data ?? []}
            isLoading={taskDetail.isLoading}
          />
          <div className="panel task-message-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Task messages</p>
                <h2>Selected task stream</h2>
              </div>
              <MessageSquare size={18} />
            </div>
            <SessionStreamPanel
              compact
              emptyText="No task-scoped messages yet."
              messages={taskMessages.data?.items ?? []}
            />
          </div>
        </section>

        <aside className="right-column">
          <ConfirmationPanel
            confirmations={confirmations.data ?? []}
            sessionId={sessionId}
            taskId={effectiveTaskId}
          />
          <div className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Session stream</p>
                <h2>Global timeline</h2>
              </div>
              <PanelRightOpen size={18} />
            </div>
            <SessionStreamPanel
              emptyText="No session messages yet."
              messages={sessionMessages.data?.items ?? []}
            />
          </div>
        </aside>
      </section>

      <ComposerBar sessionId={sessionId} selectedTaskId={effectiveTaskId} />
    </main>
  );
}

function Metric({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="metric">
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
