import type { ReactNode } from "react";

import type { SessionMessageView } from "../../shared/api/types";
import { Button, Panel, Text } from "../../shared/components";
import { cx } from "../../shared/utils/cx";
import { SessionMessageCard } from "./SessionMessageCard";
import styles from "./MainPage.module.css";

export type ConversationLayerProps = {
  className?: string;
  headerActions?: ReactNode;
  messages: readonly SessionMessageView[];
  onOpenActivity?: () => void;
  totalActivityCount: number;
};

export function ConversationLayer({
  className,
  headerActions = null,
  messages,
  onOpenActivity,
  totalActivityCount,
}: ConversationLayerProps) {
  return (
    <Panel
      as="section"
      className={cx(styles.conversationLayer, className)}
      aria-label="Conversation"
      tone="surface"
    >
      <div className={styles.conversationHeader}>
        <div>
          <Text as="h2" variant="subheading">
            Conversation
          </Text>
        </div>
        <div className={styles.conversationHeaderActions}>
          {headerActions}
          {onOpenActivity ? (
            <Button onClick={onOpenActivity} size="sm" variant="secondary">
              Activity {totalActivityCount}
            </Button>
          ) : null}
        </div>
      </div>

      {messages.length > 0 ? (
        <div className={styles.conversationMessageList}>
          {messages.map((message) => (
            <SessionMessageCard key={message.id} message={message} />
          ))}
        </div>
      ) : (
        <div className={styles.emptyState}>
          <Text as="h3" variant="subheading">
            No conversation yet
          </Text>
        </div>
      )}
    </Panel>
  );
}
