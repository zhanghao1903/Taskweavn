import { ShieldAlert } from "lucide-react";

import type { ConfirmationActionView, SessionId, TaskId } from "../../api/contracts";
import { useResolveConfirmation } from "../../api/client";

type Props = {
  confirmations: ConfirmationActionView[];
  sessionId: SessionId;
  taskId: TaskId | null;
};

export function ConfirmationPanel({ confirmations, sessionId, taskId }: Props) {
  const resolveConfirmation = useResolveConfirmation(sessionId, taskId);

  return (
    <section className="panel confirmation-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Action required</p>
          <h2>Confirmations</h2>
        </div>
        <ShieldAlert size={18} />
      </div>

      {confirmations.length ? (
        confirmations.map((confirmation) => (
          <article className="confirmation-card" key={confirmation.confirmationId}>
            <div>
              <span className="risk-label">{confirmation.riskLabel}</span>
              <h3>{confirmation.title}</h3>
              <p>{confirmation.description}</p>
            </div>
            <div className="confirmation-actions">
              {confirmation.options.map((option) => (
                <button
                  className={`action-button ${option.tone ?? "neutral"}`}
                  disabled={resolveConfirmation.isPending}
                  key={option.value}
                  onClick={() =>
                    resolveConfirmation.mutate({
                      sessionId,
                      confirmationId: confirmation.confirmationId,
                      value: option.value,
                    })
                  }
                  type="button"
                >
                  {option.label}
                </button>
              ))}
            </div>
          </article>
        ))
      ) : (
        <div className="empty-state">No pending confirmations for this task.</div>
      )}
    </section>
  );
}
