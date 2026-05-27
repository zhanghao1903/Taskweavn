import type { SessionMessageView } from "../../shared/api/types";
import { Badge } from "../../shared/components";
import { selectMessageKindPresentation } from "./mainPageSelectors";
import styles from "./MainPage.module.css";

export type SessionMessageCardProps = {
  message: SessionMessageView;
};

export function SessionMessageCard({ message }: SessionMessageCardProps) {
  const kindPresentation = selectMessageKindPresentation(message.kind);

  return (
    <article className={styles.messageCard}>
      <div className={styles.messageMeta}>
        <Badge size="sm" tone={kindPresentation.tone}>
          {kindPresentation.label}
        </Badge>
        <span>
          {message.taskNodeId
            ? `TaskNode: ${message.taskNodeId}`
            : "Session-wide"}
        </span>
      </div>
      <strong>{message.title}</strong>
      <p>{message.body}</p>
    </article>
  );
}
