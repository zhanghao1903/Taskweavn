import { useEffect, useMemo, useState } from "react";
import { LoaderCircle } from "lucide-react";

import type {
  AnswerAskPayload,
  CancelAskPayload,
  DeferAskPayload,
} from "../../../shared/api/platoApi";
import type { AskRequestView } from "../../../shared/api/types";
import { Badge, Button, ChoiceGroup, Text } from "../../../shared/components";
import type { ChoiceGroupMode } from "../../../shared/components";
import { useUiText, type UiTextCatalog } from "../../../shared/ui-text";
import { ProductRecoveryActions } from "../ProductRecoveryActions";
import type { MainPageDetailView } from "../mainPageViewModel";
import styles from "./ExecutionAskDetailPanel.module.css";

type ExecutionAskDetail = Extract<
  MainPageDetailView,
  { kind: "executionAsk" }
>;

export type ExecutionAskDetailPanelProps = {
  detail: ExecutionAskDetail;
  onAnswer: (payload: AnswerAskPayload) => void;
  onCancel: (payload: CancelAskPayload) => void;
  onDefer: (payload: DeferAskPayload) => void;
};

type ExecutionAskDraft = {
  questionTexts: Record<string, string>;
  selectedOptionIds: string[];
  text: string;
  touched: boolean;
};

type DraftsByAskId = Record<string, ExecutionAskDraft>;

export function ExecutionAskDetailPanel({
  detail,
  onAnswer,
  onCancel,
  onDefer,
}: ExecutionAskDetailPanelProps) {
  const uiText = useUiText();
  const askText = uiText.main.interaction.ask;
  const [draftsByAskId, setDraftsByAskId] = useState<DraftsByAskId>({});
  const ask = detail.ask;
  const draft = draftsByAskId[ask.id] ?? emptyDraft();
  const pendingAction = pendingActionFor(detail);
  const isPending = pendingAction !== null;
  const isStale = isStaleAsk(detail);
  const validation = validateAskDraft(ask, draft, askText.messages);
  const canAnswer = validation.valid && !isPending && !isStale;
  const batchQuestions = ask.questions ?? [];
  const hasBatchQuestions = batchQuestions.length > 0;
  const optionChoices = useMemo(
    () =>
      ask.suggestedOptions.map((option) => ({
        description: option.description ?? undefined,
        label: option.label,
        value: option.id,
      })),
    [ask.suggestedOptions],
  );
  const acceptsOptions = ask.answerType !== "free_text";
  const hasOptions =
    !hasBatchQuestions && acceptsOptions && optionChoices.length > 0;
  const showTextInput =
    !hasBatchQuestions && (ask.allowFreeText || ask.answerType === "free_text");

  useEffect(() => {
    setDraftsByAskId((current) => ({
      ...current,
      [ask.id]: current[ask.id] ?? emptyDraft(),
    }));
  }, [ask.id]);

  function updateDraft(nextDraft: Partial<ExecutionAskDraft>) {
    setDraftsByAskId((current) => ({
      ...current,
      [ask.id]: {
        ...emptyDraft(),
        ...current[ask.id],
        ...nextDraft,
        touched: true,
      },
    }));
  }

  function handleAnswer() {
    if (!canAnswer) {
      updateDraft({ touched: true });
      return;
    }

    onAnswer({
      selectedOptionIds: acceptsOptions ? draft.selectedOptionIds : [],
      text: hasBatchQuestions
        ? formatBatchAnswer(batchQuestions, draft.questionTexts, askText.messages)
        : draft.text.trim() || null,
    });
  }

  return (
    <section className={styles.root} data-ask-id={ask.id}>
      <div className={styles.titleRow}>
        <Text as="strong" variant="label">
          {askText.labels.taskInputRequired}
        </Text>
        <Badge tone={isStale ? "danger" : "warning"}>
          {askStatusLabel(ask.status, askText.statuses)}
        </Badge>
      </div>

      {detail.selectedTask ? (
        <Text variant="muted">
          {askText.labels.task({ title: detail.selectedTask.title })}
        </Text>
      ) : null}

      <div className={styles.questionBlock}>
        <Text as="h3" variant="subheading">
          {ask.question}
        </Text>
        {ask.reason ? <Text variant="muted">{ask.reason}</Text> : null}

        {hasOptions ? (
          <ChoiceGroup
            disabled={isPending || isStale}
            error={
              draft.touched && !validation.valid && !showTextInput
                ? validation.message
                : null
            }
            layout={ask.answerType === "boolean" ? "segmented" : "rows"}
            mode={choiceModeFor(ask)}
            onChange={(selectedOptionIds) =>
              updateDraft({ selectedOptionIds })
            }
            options={optionChoices}
            selectedValues={draft.selectedOptionIds}
          />
        ) : null}

        {hasBatchQuestions ? (
          <div className={styles.batchQuestionList}>
            {batchQuestions.map((question, index) => (
              <label className={styles.textAnswer} key={question.id}>
                <span>
                  {index + 1}. {question.question}
                  {question.required ? "" : ` (${askText.labels.optional})`}
                </span>
                <textarea
                  aria-invalid={
                    draft.touched &&
                    question.required &&
                    !draft.questionTexts[question.id]?.trim()
                  }
                  disabled={isPending || isStale}
                  onChange={(event) =>
                    updateDraft({
                      questionTexts: {
                        ...draft.questionTexts,
                        [question.id]: event.currentTarget.value,
                      },
                    })
                  }
                  placeholder={question.inputHint ?? askText.messages.addYourAnswer}
                  rows={3}
                  value={draft.questionTexts[question.id] ?? ""}
                />
              </label>
            ))}
          </div>
        ) : null}

        {showTextInput ? (
          <label className={styles.textAnswer}>
            <span>{askText.labels.answerText}</span>
            <textarea
              aria-invalid={draft.touched && !validation.valid}
              disabled={isPending || isStale}
              onChange={(event) => updateDraft({ text: event.currentTarget.value })}
              placeholder={askText.messages.addMissingInformation}
              rows={4}
              value={draft.text}
            />
          </label>
        ) : null}

        {draft.touched && !validation.valid ? (
          <Text className={styles.error} role="alert" variant="muted">
            {validation.message}
          </Text>
        ) : null}
      </div>

      {isStale ? (
        <Text className={styles.error} role="alert" variant="muted">
          {askText.messages.staleAsk}
        </Text>
      ) : null}

      {detail.commandError ? (
        <div className={styles.commandErrorBlock}>
          <Text className={styles.error} role="alert" variant="muted">
            {detail.commandError}
          </Text>
          <ProductRecoveryActions actions={detail.commandRecoveryActions} />
        </div>
      ) : null}

      <div className={styles.actionRow}>
        <Button
          aria-busy={detail.isAnsweringAsk ? true : undefined}
          className={detail.isAnsweringAsk ? styles.submitButtonPending : undefined}
          disabled={!canAnswer}
          onClick={handleAnswer}
          variant="primary"
        >
          {detail.isAnsweringAsk ? (
            <>
              <LoaderCircle
                aria-hidden="true"
                className={styles.pendingSpinner}
                size={16}
              />
              {askText.actions.answering}
            </>
          ) : (
            askText.actions.answer
          )}
        </Button>
        <Button
          disabled={isPending || isStale}
          onClick={() => onDefer({ reason: "user deferred ASK" })}
        >
          {detail.isDeferringAsk ? askText.actions.deferring : askText.actions.defer}
        </Button>
        <Button
          disabled={isPending || isStale}
          onClick={() => onCancel({ reason: "user cancelled ASK" })}
          variant="danger"
        >
          {detail.isCancellingAsk
            ? askText.actions.cancelling
            : askText.actions.cancelQuestion}
        </Button>
      </div>
    </section>
  );
}

function askStatusLabel(
  status: AskRequestView["status"],
  labels: UiTextCatalog["main"]["interaction"]["ask"]["statuses"],
) {
  return labels[status];
}

function emptyDraft(): ExecutionAskDraft {
  return {
    questionTexts: {},
    selectedOptionIds: [],
    text: "",
    touched: false,
  };
}

function choiceModeFor(ask: AskRequestView): ChoiceGroupMode {
  return ask.answerType === "multi_choice" ? "multi" : "single";
}

function pendingActionFor(
  detail: ExecutionAskDetail,
): "answer" | "defer" | "cancel" | null {
  if (detail.isAnsweringAsk) {
    return "answer";
  }

  if (detail.isDeferringAsk) {
    return "defer";
  }

  if (detail.isCancellingAsk) {
    return "cancel";
  }

  return null;
}

function isStaleAsk(detail: ExecutionAskDetail): boolean {
  if (!detail.selectedTask || !detail.ask.taskNodeId) {
    return false;
  }

  return !selectedTaskMatchesAsk(detail.selectedTask, detail.ask);
}

function selectedTaskMatchesAsk(
  selectedTask: NonNullable<ExecutionAskDetail["selectedTask"]>,
  ask: AskRequestView,
): boolean {
  return (
    selectedTask.id === ask.taskNodeId ||
    selectedTask.taskRef?.id === ask.taskNodeId ||
    ask.taskRef?.id === selectedTask.id ||
    (ask.taskRef?.id !== undefined && ask.taskRef.id === selectedTask.taskRef?.id)
  );
}

function validateAskDraft(
  ask: AskRequestView,
  draft: ExecutionAskDraft,
  messages: UiTextCatalog["main"]["interaction"]["ask"]["messages"],
): { message: string; valid: boolean } {
  const hasSelectedOption = draft.selectedOptionIds.length > 0;
  const hasText = draft.text.trim().length > 0;
  const batchQuestions = ask.questions ?? [];

  if (batchQuestions.length > 0) {
    const hasAnyAnswer = batchQuestions.some((question) =>
      draft.questionTexts[question.id]?.trim(),
    );
    const hasMissingRequired = batchQuestions.some(
      (question) =>
        question.required && !draft.questionTexts[question.id]?.trim(),
    );
    if (!hasAnyAnswer || hasMissingRequired) {
      return {
        message: messages.requiredQuestions,
        valid: false,
      };
    }
    return { message: "", valid: true };
  }

  if (ask.answerType === "free_text") {
    return hasText
      ? { message: "", valid: true }
      : { message: messages.enterAnswer, valid: false };
  }

  if (hasSelectedOption) {
    return { message: "", valid: true };
  }

  if ((ask.allowFreeText || ask.allowNoOptionWithText) && hasText) {
    return { message: "", valid: true };
  }

  return {
    message: ask.allowFreeText
      ? messages.chooseOptionOrEnterAnswer
      : messages.chooseOption,
    valid: false,
  };
}

function formatBatchAnswer(
  questions: NonNullable<AskRequestView["questions"]>,
  questionTexts: Record<string, string>,
  messages: UiTextCatalog["main"]["interaction"]["ask"]["messages"],
): string {
  const lines = questions
    .map((question, index) => {
      const answer = questionTexts[question.id]?.trim();
      if (!answer) {
        return null;
      }
      return messages.batchAnswerItem({
        answer,
        index: index + 1,
        question: question.question,
      });
    })
    .filter((line): line is string => line !== null);
  return `${messages.batchAnswerHeader}\n\n${lines.join("\n\n")}`;
}
