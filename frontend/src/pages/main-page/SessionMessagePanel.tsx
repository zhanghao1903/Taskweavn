import { MessagesSquare } from "lucide-react";

import type {
  MessageKind,
  SessionMessageView,
  TaskNodeCardView,
} from "../../shared/api/types";
import type { BadgeTone } from "../../shared/components";
import { Badge, Panel, Text } from "../../shared/components";
import styles from "./MainPage.module.css";

export type SessionMessagePanelProps = {
  isMessageScoped: boolean;
  messages: SessionMessageView[];
  selectedTask: TaskNodeCardView | undefined;
  totalMessageCount: number;
  visibleMessageCount: number;
};

export function SessionMessagePanel({
  isMessageScoped,
  messages,
  selectedTask,
  totalMessageCount,
  visibleMessageCount,
}: SessionMessagePanelProps) {
  return (
    <Panel
      className={styles.workPanel}
      icon={<MessagesSquare size={18} aria-hidden="true" />}
      title="Session messages"
      titleId="message-title"
      tone="muted"
    >
      <div className={styles.messageScope}>
        <Text as="span" variant="eyebrow">
          {selectedTask ? "Task-scoped projection" : "Full session stream"}
        </Text>
        <Badge size="sm" tone={isMessageScoped ? "blue" : "neutral"}>
          {visibleMessageCount}/{totalMessageCount} shown
        </Badge>
      </div>
      {messages.length > 0 ? (
        <div className={styles.messageList}>
          {messages.map((message) => (
            <article className={styles.messageCard} key={message.id}>
              <div className={styles.messageMeta}>
                <Badge size="sm" tone={messageTone(message.kind)}>
                  {message.kind}
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
          ))}
        </div>
      ) : (
        <div className={styles.emptyState}>
          <Text as="h3" variant="subheading">
            No messages yet
          </Text>
          <Text variant="muted">
            {selectedTask
              ? "No messages are attached to this TaskNode yet."
              : "Session messages will appear here as Plato works."}
          </Text>
        </div>
      )}
    </Panel>
  );
}

function messageTone(kind: MessageKind): BadgeTone {
  if (kind === "error") {
    return "danger";
  }

  return kind === "actionable" ? "warning" : "blue";
}
