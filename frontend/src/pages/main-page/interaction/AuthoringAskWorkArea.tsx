import type { FormEvent, Ref } from "react";
import { useEffect, useMemo, useState } from "react";
import { LoaderCircle } from "lucide-react";

import type { AnswerAuthoringAskItemPayload } from "../../../shared/api/platoApi";
import type {
  ConfirmationOptionView,
  PlanningAskView,
} from "../../../shared/api/types";
import { Badge, Button, ChoiceGroup, Text } from "../../../shared/components";
import type { ChoiceOptionTone } from "../../../shared/components";
import { ProductRecoveryActions } from "../ProductRecoveryActions";
import type { MainPageAuthoringAskViewModel } from "../mainPageViewModel";
import styles from "./AuthoringAskWorkArea.module.css";

export type AuthoringAskSubmitContext = {
  answers: AnswerAuthoringAskItemPayload[];
  rawTaskId: string;
};

export type AuthoringAskWorkAreaProps = {
  focusRef?: Ref<HTMLElement>;
  onSubmit: (context: AuthoringAskSubmitContext) => void;
  view: MainPageAuthoringAskViewModel;
};

type AnswerDraft = {
  touched: boolean;
  value: string;
};

type DraftsByAskId = Record<string, AnswerDraft>;

export function AuthoringAskWorkArea({
  focusRef,
  onSubmit,
  view,
}: AuthoringAskWorkAreaProps) {
  const [drafts, setDrafts] = useState<DraftsByAskId>({});
  const askIdentity = useMemo(
    () => view.asks.map((ask) => ask.id).join("|"),
    [view.asks],
  );

  useEffect(() => {
    setDrafts((current) => {
      const nextDrafts: DraftsByAskId = {};

      for (const ask of view.asks) {
        nextDrafts[ask.id] = current[ask.id] ?? {
          touched: false,
          value: "",
        };
      }

      return nextDrafts;
    });
  }, [askIdentity, view.asks, view.rawTaskId]);

  const validAnswerCount = view.asks.filter((ask) =>
    isAskDraftValid(drafts[ask.id]),
  ).length;
  const answers = buildAnswers(view.asks, drafts);
  const hasIncompleteAnswers = validAnswerCount < view.asks.length;
  const canSubmit =
    answers.length === view.asks.length && !hasIncompleteAnswers && !view.isSubmitting;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!canSubmit) {
      setDrafts((current) => touchAllDrafts(view.asks, current));
      return;
    }

    onSubmit({
      answers,
      rawTaskId: view.rawTaskId,
    });
  }

  function updateDraft(askId: string, value: string) {
    setDrafts((current) => ({
      ...current,
      [askId]: {
        touched: true,
        value,
      },
    }));
  }

  return (
    <form
      aria-label="Authoring questions"
      className={styles.root}
      onSubmit={handleSubmit}
      ref={focusRef as Ref<HTMLFormElement>}
      tabIndex={-1}
    >
      <header className={styles.header}>
        <div className={styles.titleGroup}>
          <Text as="p" variant="eyebrow">
            Clarification questions
          </Text>
          <h2>{view.title}</h2>
          {view.summary ? <Text variant="muted">{view.summary}</Text> : null}
        </div>
        <Badge tone="warning">
          {validAnswerCount}/{view.asks.length} answered
        </Badge>
      </header>

      <div className={styles.questionList}>
        {view.asks.map((ask, index) => (
          <AuthoringAskQuestion
            ask={ask}
            disabled={view.isSubmitting}
            draft={drafts[ask.id]}
            key={ask.id}
            number={index + 1}
            onChange={(value) => updateDraft(ask.id, value)}
          />
        ))}
      </div>

      <footer className={styles.footer}>
        <div className={styles.footerCopy}>
          <Text as="strong" variant="label">
            {answers.length} answer{answers.length === 1 ? "" : "s"} ready
          </Text>
          <Text variant="muted">
            {hasIncompleteAnswers
              ? "Complete all questions before submitting."
              : "Review the questions, then submit all answers together."}
          </Text>
          {view.commandError ? (
            <div className={styles.commandErrorBlock}>
              <Text className={styles.error} role="alert" variant="muted">
                {view.commandError}
              </Text>
              <ProductRecoveryActions
                actions={view.commandRecoveryActions}
              />
            </div>
          ) : null}
        </div>
        <Button
          aria-busy={view.isSubmitting ? true : undefined}
          className={view.isSubmitting ? styles.submitButtonPending : undefined}
          disabled={!canSubmit}
          type="submit"
          variant="primary"
        >
          {view.isSubmitting ? (
            <>
              <LoaderCircle
                aria-hidden="true"
                className={styles.pendingSpinner}
                size={16}
              />
              Submitting
            </>
          ) : (
            "Submit all answers"
          )}
        </Button>
      </footer>
    </form>
  );
}

type AuthoringAskQuestionProps = {
  ask: PlanningAskView;
  disabled: boolean;
  draft: AnswerDraft | undefined;
  number: number;
  onChange: (value: string) => void;
};

function AuthoringAskQuestion({
  ask,
  disabled,
  draft,
  number,
  onChange,
}: AuthoringAskQuestionProps) {
  const value = draft?.value ?? "";
  const showValidation = draft?.touched === true && value.trim() === "";
  const optionChoices = ask.options.map((option) => ({
    label: option.label,
    tone: choiceTone(option),
    value: option.value,
  }));
  const hasOptions = optionChoices.length > 0;

  return (
    <section className={styles.questionBlock}>
      <div className={styles.questionHeader}>
        <Badge tone={ask.required ? "warning" : "neutral"}>
          {ask.required ? "Required" : "Optional"}
        </Badge>
        <Text as="span" variant="muted">
          Question {number}
        </Text>
      </div>
      <Text as="h3" variant="subheading">
        {ask.question}
      </Text>
      {ask.reason ? <Text variant="muted">{ask.reason}</Text> : null}

      {hasOptions ? (
        <ChoiceGroup
          disabled={disabled}
          error={showValidation ? "Choose one option." : null}
          layout={optionChoices.length <= 2 ? "segmented" : "rows"}
          onChange={(selectedValues) => onChange(selectedValues[0] ?? "")}
          options={optionChoices}
          selectedValues={value ? [value] : []}
        />
      ) : (
        <label className={styles.textAnswer}>
          <span>Answer</span>
          <textarea
            aria-invalid={showValidation}
            disabled={disabled}
            onChange={(event) => onChange(event.currentTarget.value)}
            placeholder="Type a concise answer."
            rows={3}
            value={value}
          />
          {showValidation ? (
            <span className={styles.error} role="alert">
              Enter an answer.
            </span>
          ) : null}
        </label>
      )}
    </section>
  );
}

function buildAnswers(
  asks: PlanningAskView[],
  drafts: DraftsByAskId,
): AnswerAuthoringAskItemPayload[] {
  return asks
    .map((ask) => ({
      askId: ask.id,
      value: drafts[ask.id]?.value.trim() ?? "",
    }))
    .filter((answer) => answer.value.length > 0);
}

function isAskDraftValid(draft: AnswerDraft | undefined): boolean {
  return (draft?.value.trim() ?? "").length > 0;
}

function touchAllDrafts(
  asks: PlanningAskView[],
  drafts: DraftsByAskId,
): DraftsByAskId {
  const nextDrafts: DraftsByAskId = {};

  for (const ask of asks) {
    nextDrafts[ask.id] = {
      touched: true,
      value: drafts[ask.id]?.value ?? "",
    };
  }

  return nextDrafts;
}

function choiceTone(option: ConfirmationOptionView): ChoiceOptionTone {
  if (option.tone === "primary" || option.tone === "danger") {
    return option.tone;
  }

  return "neutral";
}
