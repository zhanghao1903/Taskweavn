import { useCallback, useMemo, useState } from "react";

import type {
  ConversationAskDraftStore,
  ConversationAskQuestionDrafts,
} from "./conversationAskInteraction";

type DraftsByCardId = Record<string, ConversationAskQuestionDrafts>;
type DraftsBySessionId = Record<string, DraftsByCardId>;

const EMPTY_DRAFTS_BY_CARD_ID: DraftsByCardId = {};

export function useConversationAskDraftStore(
  sessionId: string,
): ConversationAskDraftStore {
  const [draftsBySessionId, setDraftsBySessionId] =
    useState<DraftsBySessionId>({});
  const draftsByCardId =
    draftsBySessionId[sessionId] ?? EMPTY_DRAFTS_BY_CARD_ID;
  const onDraftsChange = useCallback(
    (
      cardId: string,
      drafts: ConversationAskQuestionDrafts | null,
    ) => {
      setDraftsBySessionId((current) => {
        const sessionDrafts = current[sessionId] ?? {};
        if (drafts === null) {
          if (!(cardId in sessionDrafts)) {
            return current;
          }
          const nextSessionDrafts = { ...sessionDrafts };
          delete nextSessionDrafts[cardId];
          if (Object.keys(nextSessionDrafts).length === 0) {
            const next = { ...current };
            delete next[sessionId];
            return next;
          }
          return {
            ...current,
            [sessionId]: nextSessionDrafts,
          };
        }
        return {
          ...current,
          [sessionId]: {
            ...sessionDrafts,
            [cardId]: drafts,
          },
        };
      });
    },
    [sessionId],
  );

  return useMemo(
    () => ({
      draftsByCardId,
      onDraftsChange,
    }),
    [draftsByCardId, onDraftsChange],
  );
}
