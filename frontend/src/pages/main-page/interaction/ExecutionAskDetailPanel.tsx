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
  const [draftsByAskId, setDraftsByAskId] = useState<DraftsByAskId>({});
  const ask = detail.ask;
  const draft = draftsByAskId[ask.id] ?? emptyDraft();
  const pendingAction = pendingActionFor(detail);
  const isPending = pendingAction !== null;
  const isStale = isStaleAsk(detail);
  const validation = validateAskDraft(ask, draft);
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
        ? formatBatchAnswer(batchQuestions, draft.questionTexts)
        : draft.text.trim() || null,
    });
  }

  return (
    <section className={styles.root} data-ask-id={ask.id}>
      <div className={styles.titleRow}>
        <Text as="strong" variant="label">
          Task input required
        </Text>
        <Badge tone={isStale ? "danger" : "warning"}>
          {askStatusLabel(ask.status)}
        </Badge>
      </div>

      {detail.selectedTask ? (
        <Text variant="muted">
          Task: {detail.selectedTask.title}
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
                  {question.required ? "" : " (optional)"}
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
                  placeholder={question.inputHint ?? "Add your answer."}
                  rows={3}
                  value={draft.questionTexts[question.id] ?? ""}
                />
              </label>
            ))}
          </div>
        ) : null}

        {showTextInput ? (
          <label className={styles.textAnswer}>
            <span>Answer text</span>
            <textarea
              aria-invalid={draft.touched && !validation.valid}
              disabled={isPending || isStale}
              onChange={(event) => updateDraft({ text: event.currentTarget.value })}
              placeholder="Add the missing information."
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
          This question no longer matches the selected task. Refresh or select the
          waiting task before answering.
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
              Answering
            </>
          ) : (
            "Answer"
          )}
        </Button>
        <Button
          disabled={isPending || isStale}
          onClick={() => onDefer({ reason: "user deferred ASK" })}
        >
          {detail.isDeferringAsk ? "Deferring" : "Defer"}
        </Button>
        <Button
          disabled={isPending || isStale}
          onClick={() => onCancel({ reason: "user cancelled ASK" })}
          variant="danger"
        >
          {detail.isCancellingAsk ? "Cancelling" : "Cancel question"}
        </Button>
      </div>
    </section>
  );
}

function askStatusLabel(status: AskRequestView["status"]) {
  const labels: Record<AskRequestView["status"], string> = {
    answered: "Answered",
    cancelled: "Cancelled",
    deferred: "Deferred",
    expired: "Expired",
    pending: "Waiting",
  };

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
  return Boolean(
    detail.selectedTask &&
      detail.ask.taskNodeId &&
      detail.selectedTask.id !== detail.ask.taskNodeId,
  );
}

function validateAskDraft(
  ask: AskRequestView,
  draft: ExecutionAskDraft,
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
        message: "Answer the required questions before submitting.",
        valid: false,
      };
    }
    return { message: "", valid: true };
  }

  if (ask.answerType === "free_text") {
    return hasText
      ? { message: "", valid: true }
      : { message: "Enter an answer before submitting.", valid: false };
  }

  if (hasSelectedOption) {
    return { message: "", valid: true };
  }

  if ((ask.allowFreeText || ask.allowNoOptionWithText) && hasText) {
    return { message: "", valid: true };
  }

  return {
    message: ask.allowFreeText
      ? "Choose an option or enter an answer."
      : "Choose an option before submitting.",
    valid: false,
  };
}

function formatBatchAnswer(
  questions: NonNullable<AskRequestView["questions"]>,
  questionTexts: Record<string, string>,
): string {
  const lines = questions
    .map((question, index) => {
      const answer = questionTexts[question.id]?.trim();
      if (!answer) {
        return null;
      }
      return `${index + 1}. ${question.question}\nAnswer: ${answer}`;
    })
    .filter((line): line is string => line !== null);
  return `Batch ASK answers:\n\n${lines.join("\n\n")}`;
}
