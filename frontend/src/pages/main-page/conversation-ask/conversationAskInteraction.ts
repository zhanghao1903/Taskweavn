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

export type ConversationAskInteraction = {
  authoring?: AuthoringAskConversationCommandState | null;
  execution?: ExecutionAskConversationCommandState | null;
  onAnswerExecution: (askId: string, payload: AnswerAskPayload) => void;
  onCancelExecution: (askId: string) => void;
  onDeferExecution: (askId: string) => void;
  onSubmitAuthoring: (
    rawTaskId: string,
    answers: AnswerAuthoringAskItemPayload[],
  ) => void;
};
