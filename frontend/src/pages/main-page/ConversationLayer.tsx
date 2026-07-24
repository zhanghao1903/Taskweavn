import type { ReactNode, RefObject, UIEventHandler } from "react";

import type { SessionMessageView } from "../../shared/api/types";
import { Button, Panel, Text } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import { cx } from "../../shared/utils/cx";
import type { ConversationAskInteraction } from "./conversation-ask/conversationAskInteraction";
import { SessionMessageCard } from "./SessionMessageCard";
import styles from "./MainPage.module.css";

export type ConversationLayerProps = {
  activeAskIdentity?: string | null;
  askCardRef?: RefObject<HTMLElement | null>;
  askInteraction?: ConversationAskInteraction;
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
  activeAskIdentity = null,
  askCardRef,
  askInteraction,
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
  const uiText = useUiText();

  return (
    <Panel
      as="section"
      className={cx(styles.conversationLayer, className)}
      aria-label={uiText.main.detail.labels.conversation}
      ref={rootRef}
      tabIndex={-1}
      tone="surface"
    >
      <div className={styles.conversationHeader}>
        <div>
          <Text as="h2" variant="subheading">
            {uiText.main.detail.labels.conversation}
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
              {uiText.main.activity.labels.activityCount({
                count: totalActivityCount,
              })}
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
            <SessionMessageCard
              askInteraction={askInteraction}
              focusRef={
                conversationAskIdentity(message) === activeAskIdentity
                  ? askCardRef
                  : undefined
              }
              key={message.id}
              message={message}
            />
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
            {uiText.main.detail.messages.conversationEmpty}
          </Text>
        </div>
      )}
    </Panel>
  );
}

function conversationAskIdentity(
  message: SessionMessageView,
): string | null {
  const card = message.conversationRender?.askCard;
  if (message.conversationRender?.renderKind !== "ask_card" || !card) {
    return null;
  }
  if (card.domain === "authoring" && card.rawTaskId) {
    return `authoring:${card.rawTaskId}`;
  }
  if (card.domain === "execution" && card.askId) {
    return `execution:${card.askId}`;
  }
  return null;
}
