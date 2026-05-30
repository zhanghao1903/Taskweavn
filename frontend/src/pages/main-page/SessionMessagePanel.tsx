import { MessagesSquare } from "lucide-react";

import type {
  SessionMessageView,
  TaskNodeCardView,
} from "../../shared/api/types";
import { Badge, Panel, Text } from "../../shared/components";
import { SessionMessageCard } from "./SessionMessageCard";
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
      tone="surface"
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
            <SessionMessageCard key={message.id} message={message} />
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
