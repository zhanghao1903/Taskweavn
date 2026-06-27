import type { ReactNode, RefObject, UIEventHandler } from "react";

import type { SessionMessageView } from "../../shared/api/types";
import { Button, Panel, Text } from "../../shared/components";
import { cx } from "../../shared/utils/cx";
import { SessionMessageCard } from "./SessionMessageCard";
import styles from "./MainPage.module.css";

export type ConversationLayerProps = {
  bottomSentinelRef?: RefObject<HTMLDivElement | null>;
  className?: string;
  headerActions?: ReactNode;
  messageListRef?: RefObject<HTMLDivElement | null>;
  messages: readonly SessionMessageView[];
  onOpenActivity?: (trigger: HTMLElement) => void;
  onMessageListScroll?: UIEventHandler<HTMLDivElement>;
  rootRef?: RefObject<HTMLElement | null>;
  totalActivityCount: number;
};

export function ConversationLayer({
  bottomSentinelRef,
  className,
  headerActions = null,
  messageListRef,
  messages,
  onMessageListScroll,
  onOpenActivity,
  rootRef,
  totalActivityCount,
}: ConversationLayerProps) {
  return (
    <Panel
      as="section"
      className={cx(styles.conversationLayer, className)}
      aria-label="Conversation"
      ref={rootRef}
      tabIndex={-1}
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
            <Button
              onClick={(event) => onOpenActivity(event.currentTarget)}
              size="sm"
              variant="secondary"
            >
              Activity {totalActivityCount}
            </Button>
          ) : null}
        </div>
      </div>

      {messages.length > 0 ? (
        <div
          className={styles.conversationMessageList}
          data-plato-conversation-list="true"
          onScroll={onMessageListScroll}
          ref={messageListRef}
        >
          {messages.map((message) => (
            <SessionMessageCard key={message.id} message={message} />
          ))}
          <div
            aria-hidden="true"
            className={styles.conversationBottomSentinel}
            data-plato-conversation-end="true"
            ref={bottomSentinelRef}
          />
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
