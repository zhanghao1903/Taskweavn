import type { FormEvent } from "react";
import { useEffect, useId, useMemo, useState } from "react";
import { LoaderCircle } from "lucide-react";

import type {
  ConversationAskCardView,
  ConversationAskQuestionView,
} from "../../../shared/api/types";
import {
  Badge,
  Button,
  ChoiceGroup,
  MarkdownContent,
  Text,
} from "../../../shared/components";
import { useUiText, type UiTextCatalog } from "../../../shared/ui-text";
import { ProductRecoveryActions } from "../ProductRecoveryActions";
import type {
  ConversationAskInteraction,
  ConversationAskQuestionDraft,
  ConversationAskQuestionDrafts,
} from "./conversationAskInteraction";
import styles from "./ConversationAskCard.module.css";

export type ConversationAskCardProps = {
  card: ConversationAskCardView;
  interaction?: ConversationAskInteraction;
};

export function ConversationAskCard({
  card,
  interaction,
}: ConversationAskCardProps) {
  const uiText = useUiText();
  const askText = uiText.main.interaction.ask;
  const onDraftsChange = interaction?.draftStore?.onDraftsChange;
  const storedDrafts =
    interaction?.draftStore?.draftsByCardId[card.cardId] ?? null;
  const [drafts, setDrafts] = useState<ConversationAskQuestionDrafts>(() =>
    card.status === "pending"
      ? preservePendingDrafts(card.questions, storedDrafts ?? {})
      : draftsFromCard(card),
  );
  const answerIdentity = useMemo(
    () =>
      card.questions
        .map(
          (question) =>
            `${question.id}:${question.answered}:${question.answerText ?? ""}:${question.options
              .filter((option) => option.selected)
              .map((option) => option.id)
              .join(",")}`,
        )
        .join("|"),
    [card.questions],
  );

  useEffect(() => {
    setDrafts((current) =>
      card.status === "pending"
        ? preservePendingDrafts(card.questions, current)
        : draftsFromQuestions(card.questions),
    );
  }, [answerIdentity, card.cardId, card.questions, card.status]);

  useEffect(() => {
    onDraftsChange?.(
      card.cardId,
      card.status === "pending" ? drafts : null,
    );
  }, [card.cardId, card.status, drafts, onDraftsChange]);

  const authoringState =
    card.domain === "authoring" &&
    card.rawTaskId &&
    interaction?.authoring?.rawTaskId === card.rawTaskId
      ? interaction.authoring
      : null;
  const executionState =
    card.domain === "execution" &&
    card.askId
      ? interaction?.executionByAskId?.[card.askId] ?? null
      : null;
  const isCardCommandPending =
    authoringState?.isSubmitting === true ||
    executionState?.isAnswering === true ||
    executionState?.isCancelling === true ||
    executionState?.isDeferring === true;
  const isInteractionLocked =
    isCardCommandPending ||
    (card.domain === "execution" &&
      interaction?.hasExecutionCommandPending === true);
  const isInteractive =
    card.status === "pending" && card.canAnswer && interaction !== undefined;
  const validation = validateCard(card, drafts);
  const commandError =
    authoringState?.commandError ?? executionState?.commandError ?? null;
  const recoveryActions =
    authoringState?.commandRecoveryActions ??
    executionState?.commandRecoveryActions ??
    [];

  function updateDraft(
    questionId: string,
    update: Partial<ConversationAskQuestionDraft>,
  ) {
    setDrafts((current) => ({
      ...current,
      [questionId]: {
        ...emptyDraft(),
        ...current[questionId],
        ...update,
        touched: true,
      },
    }));
  }

  function touchAllDrafts() {
    setDrafts((current) =>
      Object.fromEntries(
        card.questions.map((question) => [
          question.id,
          question.answered
            ? current[question.id] ?? emptyDraft()
            : {
                ...emptyDraft(),
                ...current[question.id],
                touched: true,
              },
        ]),
      ),
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validation.valid || isInteractionLocked) {
      touchAllDrafts();
      return;
    }

    if (
      card.domain === "authoring" &&
      card.rawTaskId &&
      interaction?.onSubmitAuthoring
    ) {
      interaction.onSubmitAuthoring(
        card.rawTaskId,
        card.questions
          .filter((question) => !question.answered)
          .map((question) => ({
            askId: question.id,
            value: authoringAnswerValue(question, drafts[question.id]),
          })),
      );
      return;
    }

    if (
      card.domain === "execution" &&
      card.askId &&
      interaction?.onAnswerExecution
    ) {
      interaction.onAnswerExecution(
        card.askId,
        executionAnswerPayload(card, drafts, askText.messages),
      );
    }
  }

  return (
    <form
      aria-label={card.title}
      className={styles.root}
      data-conversation-ask-domain={card.domain}
      data-conversation-ask-id={card.askId ?? card.rawTaskId ?? card.cardId}
      onSubmit={handleSubmit}
    >
      <header className={styles.header}>
        <div className={styles.titleGroup}>
          <Text as="strong" variant="subheading">
            {card.domain === "authoring"
              ? askText.labels.planningQuestions
              : card.title}
          </Text>
          {card.body ? <Text variant="muted">{card.body}</Text> : null}
        </div>
        <Badge size="sm" tone={statusTone(card.status)}>
          {askText.statuses[card.status]}
        </Badge>
      </header>

      <div className={styles.questionList}>
        {card.questions.map((question, index) => (
          <Question
            disabled={
              !isInteractive ||
              isInteractionLocked ||
              question.answered
            }
            draft={drafts[question.id] ?? emptyDraft()}
            key={question.id}
            number={index + 1}
            onChange={(update) => updateDraft(question.id, update)}
            question={question}
            showValidation={
              drafts[question.id]?.touched === true &&
              !question.answered &&
              !questionDraftIsValid(card, question, drafts[question.id])
            }
            uiText={uiText}
          />
        ))}
      </div>

      {card.answerText ? (
        <div className={styles.answerSummary}>
          <Text as="strong" variant="label">
            {askText.labels.selectedAnswer}
          </Text>
          <MarkdownContent
            source={card.answerText}
            title={card.answerText}
            variant="conversation"
          />
        </div>
      ) : null}

      {card.readonlyReason && card.status !== "pending" ? (
        <Text className={styles.readonlyReason} variant="muted">
          {card.readonlyReason}
        </Text>
      ) : null}

      {commandError ? (
        <div className={styles.commandErrorBlock}>
          <Text className={styles.error} role="alert" variant="muted">
            {commandError}
          </Text>
          <ProductRecoveryActions actions={recoveryActions} />
        </div>
      ) : null}

      {isInteractive ? (
        <footer className={styles.footer}>
          <Button
            aria-busy={isCardCommandPending || undefined}
            disabled={!validation.valid || isInteractionLocked}
            type="submit"
            variant="primary"
          >
            {isCardCommandPending ? (
              <>
                <LoaderCircle
                  aria-hidden="true"
                  className={styles.pendingSpinner}
                  size={16}
                />
                {card.domain === "authoring"
                  ? askText.actions.submittingAllAnswers
                  : askText.actions.answering}
              </>
            ) : card.domain === "authoring" ? (
              askText.actions.submitAllAnswers
            ) : (
              askText.actions.answer
            )}
          </Button>
          {card.domain === "execution" && card.askId ? (
            <div className={styles.secondaryActions}>
              {card.canDefer ? (
                <Button
                  disabled={isInteractionLocked}
                  onClick={() => interaction?.onDeferExecution(card.askId!)}
                  type="button"
                >
                  {executionState?.isDeferring
                    ? askText.actions.deferring
                    : askText.actions.defer}
                </Button>
              ) : null}
              {card.canCancel ? (
                <Button
                  disabled={isInteractionLocked}
                  onClick={() => interaction?.onCancelExecution(card.askId!)}
                  type="button"
                  variant="danger"
                >
                  {executionState?.isCancelling
                    ? askText.actions.cancelling
                    : askText.actions.cancelQuestion}
                </Button>
              ) : null}
            </div>
          ) : null}
        </footer>
      ) : null}
    </form>
  );
}

function Question({
  disabled,
  draft,
  number,
  onChange,
  question,
  showValidation,
  uiText,
}: {
  disabled: boolean;
  draft: ConversationAskQuestionDraft;
  number: number;
  onChange: (update: Partial<ConversationAskQuestionDraft>) => void;
  question: ConversationAskQuestionView;
  showValidation: boolean;
  uiText: UiTextCatalog;
}) {
  const askText = uiText.main.interaction.ask;
  const questionHeadingId = useId();
  const hasOptions = question.options.length > 0;
  const showTextInput =
    question.answerType === "free_text" || question.allowFreeText;
  const validationMessage =
    hasOptions && showTextInput
      ? askText.messages.chooseOptionOrEnterAnswer
      : hasOptions
        ? askText.messages.chooseOption
        : askText.messages.enterAnswer;

  return (
    <section className={styles.question}>
      <div className={styles.questionMeta}>
        <Text as="span" variant="label">
          {askText.labels.question({ index: number })}
        </Text>
        {!question.required ? (
          <Badge size="sm" tone="neutral">
            {askText.labels.optional}
          </Badge>
        ) : null}
        {question.answered ? (
          <Badge size="sm" tone="success">
            {askText.statuses.answered}
          </Badge>
        ) : null}
      </div>
      <Text as="h3" id={questionHeadingId} variant="subheading">
        {question.prompt}
      </Text>
      {question.reason ? <Text variant="muted">{question.reason}</Text> : null}

      {hasOptions ? (
        <ChoiceGroup
          aria-labelledby={questionHeadingId}
          disabled={disabled}
          error={showValidation && !showTextInput ? validationMessage : null}
          layout={question.answerType === "boolean" ? "segmented" : "rows"}
          mode={question.answerType === "multi_choice" ? "multi" : "single"}
          onChange={(selectedOptionIds) => onChange({ selectedOptionIds })}
          options={question.options.map((option) => ({
            description: option.description ?? undefined,
            label: option.label,
            value: option.id,
          }))}
          selectedIndicator={askText.labels.selectedOption}
          selectedValues={draft.selectedOptionIds}
        />
      ) : null}

      {showTextInput ? (
        <label className={styles.textAnswer}>
          <span>{askText.labels.answerText}</span>
          <textarea
            aria-invalid={showValidation}
            disabled={disabled}
            onChange={(event) => onChange({ text: event.currentTarget.value })}
            placeholder={
              question.answerType === "free_text"
                ? askText.messages.addYourAnswer
                : askText.messages.addMissingInformation
            }
            rows={3}
            value={draft.text}
          />
        </label>
      ) : null}

      {showValidation ? (
        <Text className={styles.error} role="alert" variant="muted">
          {validationMessage}
        </Text>
      ) : null}
    </section>
  );
}

function draftsFromCard(
  card: ConversationAskCardView,
): ConversationAskQuestionDrafts {
  return draftsFromQuestions(card.questions);
}

function preservePendingDrafts(
  questions: ConversationAskCardView["questions"],
  current: ConversationAskQuestionDrafts,
): ConversationAskQuestionDrafts {
  const projected = draftsFromQuestions(questions);
  return Object.fromEntries(
    questions.map((question) => [
      question.id,
      question.answered
        ? projected[question.id] ?? emptyDraft()
        : current[question.id] ?? projected[question.id] ?? emptyDraft(),
    ]),
  );
}

function draftsFromQuestions(
  questions: ConversationAskCardView["questions"],
): ConversationAskQuestionDrafts {
  return Object.fromEntries(
    questions.map((question) => [
      question.id,
      {
        selectedOptionIds: question.options
          .filter((option) => option.selected)
          .map((option) => option.id),
        text: question.answerText ?? "",
        touched: false,
      },
    ]),
  );
}

function emptyDraft(): ConversationAskQuestionDraft {
  return {
    selectedOptionIds: [],
    text: "",
    touched: false,
  };
}

function validateCard(
  card: ConversationAskCardView,
  drafts: ConversationAskQuestionDrafts,
): { valid: boolean } {
  const questionsToAnswer =
    card.domain === "authoring"
      ? card.questions.filter((question) => !question.answered)
      : card.questions;
  const hasAnyAnswer = questionsToAnswer.some((question) => {
    const draft = drafts[question.id];
    return (
      (draft?.selectedOptionIds.length ?? 0) > 0 ||
      (draft?.text.trim().length ?? 0) > 0
    );
  });
  return {
    valid:
      questionsToAnswer.length > 0 &&
      (card.domain === "authoring" || hasAnyAnswer) &&
      questionsToAnswer.every((question) =>
        questionDraftIsValid(card, question, drafts[question.id]),
      ),
  };
}

function questionDraftIsValid(
  card: ConversationAskCardView,
  question: ConversationAskQuestionView,
  draft: ConversationAskQuestionDraft | undefined,
): boolean {
  if (question.answered) {
    return true;
  }
  if (card.domain === "execution" && !question.required) {
    return true;
  }
  return (
    (draft?.selectedOptionIds.length ?? 0) > 0 ||
    (draft?.text.trim().length ?? 0) > 0
  );
}

function authoringAnswerValue(
  question: ConversationAskQuestionView,
  draft: ConversationAskQuestionDraft | undefined,
): string {
  const selectedId = draft?.selectedOptionIds[0];
  const selectedOption = question.options.find(
    (option) => option.id === selectedId,
  );
  return selectedOption?.value ?? draft?.text.trim() ?? "";
}

function executionAnswerPayload(
  card: ConversationAskCardView,
  drafts: ConversationAskQuestionDrafts,
  messages: UiTextCatalog["main"]["interaction"]["ask"]["messages"],
) {
  if (card.questions.length > 1) {
    const lines = card.questions
      .map((question, index) => {
        const answer = drafts[question.id]?.text.trim();
        return answer
          ? messages.batchAnswerItem({
              answer,
              index: index + 1,
              question: question.prompt,
            })
          : null;
      })
      .filter((line): line is string => line !== null);
    return {
      selectedOptionIds: [],
      text: `${messages.batchAnswerHeader}\n\n${lines.join("\n\n")}`,
    };
  }

  const question = card.questions[0];
  const draft = question ? drafts[question.id] : undefined;
  return {
    selectedOptionIds: draft?.selectedOptionIds ?? [],
    text: draft?.text.trim() || null,
  };
}

function statusTone(
  status: ConversationAskCardView["status"],
): "danger" | "neutral" | "success" | "warning" {
  if (status === "pending") {
    return "warning";
  }
  if (status === "answered") {
    return "success";
  }
  if (status === "cancelled" || status === "expired") {
    return "danger";
  }
  return "neutral";
}
