import type { SessionMessageView } from "../../api/contracts";

type Props = {
  messages: SessionMessageView[];
  compact?: boolean;
  emptyText: string;
};

export function SessionStreamPanel({ compact = false, emptyText, messages }: Props) {
  if (!messages.length) {
    return <div className="empty-state">{emptyText}</div>;
  }

  return (
    <div className={`message-list ${compact ? "compact" : ""}`}>
      {messages.map((message) => (
        <article className={`message-row ${message.author}`} key={message.messageId}>
          <div className="message-meta">
            <span>{message.author}</span>
            {message.taskId ? <span>{message.taskId}</span> : <span>session</span>}
          </div>
          <p>{message.content}</p>
        </article>
      ))}
    </div>
  );
}
