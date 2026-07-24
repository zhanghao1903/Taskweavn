import type {
  AnswerAskPayload,
  AnswerAuthoringAskItemPayload,
  ProductRecoveryAction,
} from "../../../shared/api/platoApi";

export type AuthoringAskConversationCommandState = {
  commandError: string | null;
  commandRecoveryActions: ProductRecoveryAction[];
  isSubmitting: boolean;
  rawTaskId: string;
};

export type ExecutionAskConversationCommandState = {
  askId: string;
  commandError: string | null;
  commandRecoveryActions: ProductRecoveryAction[];
  isAnswering: boolean;
  isCancelling: boolean;
  isDeferring: boolean;
};

export type ConversationAskQuestionDraft = {
  selectedOptionIds: string[];
  text: string;
  touched: boolean;
};

export type ConversationAskQuestionDrafts = Record<
  string,
  ConversationAskQuestionDraft
>;

export type ConversationAskDraftStore = {
  draftsByCardId: Readonly<
    Record<string, ConversationAskQuestionDrafts>
  >;
  onDraftsChange: (
    cardId: string,
    drafts: ConversationAskQuestionDrafts | null,
  ) => void;
};

export type ConversationAskInteraction = {
  authoring?: AuthoringAskConversationCommandState | null;
  draftStore?: ConversationAskDraftStore;
  executionByAskId?: Readonly<
    Record<string, ExecutionAskConversationCommandState>
  >;
  hasExecutionCommandPending?: boolean;
  onAnswerExecution: (askId: string, payload: AnswerAskPayload) => void;
  onCancelExecution: (askId: string) => void;
  onDeferExecution: (askId: string) => void;
  onSubmitAuthoring: (
    rawTaskId: string,
    answers: AnswerAuthoringAskItemPayload[],
  ) => void;
};
