import { useEffect, useMemo, useState } from "react";

import type { ConfirmationActionView } from "../../../shared/api/types";
import { Badge, Button, ChoiceGroup, Text } from "../../../shared/components";
import type { ChoiceOptionTone } from "../../../shared/components";
import { useUiText, type UiTextCatalog } from "../../../shared/ui-text";
import { ProductRecoveryActions } from "../ProductRecoveryActions";
import type { MainPageDetailView } from "../mainPageViewModel";
import styles from "./ConfirmationDetailPanel.module.css";

type ConfirmationDetail = Extract<
  MainPageDetailView,
  { kind: "confirmation" }
>;

export type ConfirmationDetailPanelProps = {
  detail: ConfirmationDetail;
  onResolve: (value: string) => void;
};

type ConfirmationDraft = {
  selectedOptionValue: string | null;
  touched: boolean;
};

type DraftsByConfirmationId = Record<string, ConfirmationDraft>;

export function ConfirmationDetailPanel({
  detail,
  onResolve,
}: ConfirmationDetailPanelProps) {
  const uiText = useUiText();
  const confirmationText = uiText.main.interaction.confirmation;
  const confirmation = detail.confirmation;
  const [drafts, setDrafts] = useState<DraftsByConfirmationId>({});
  const fallbackOptions = useMemo(
    () => fallbackConfirmationOptions(confirmationText.actions),
    [confirmationText.actions],
  );
  const optionValues = useMemo(
    () =>
      (confirmation && confirmation.options.length > 0
        ? confirmation.options
        : fallbackOptions
      ).map((option) => option.value),
    [confirmation, fallbackOptions],
  );
  const draft =
    confirmation === undefined
      ? emptyDraft()
      : drafts[confirmation.id] ?? emptyDraft();
  const isPending = confirmation?.status === "pending";
  const isTerminal =
    confirmation?.status === "resolved" || confirmation?.status === "expired";
  const isResolving = detail.isResolvingConfirmation;
  const selectedValue = draft.selectedOptionValue;
  const hasValidSelection =
    selectedValue !== null && optionValues.includes(selectedValue);
  const canResolve = Boolean(isPending && hasValidSelection && !isResolving);

  useEffect(() => {
    if (!confirmation || confirmation.status !== "pending") {
      return;
    }

    setDrafts((current) => ({
      ...current,
      [confirmation.id]: current[confirmation.id] ?? emptyDraft(),
    }));
  }, [confirmation]);

  function selectOption(selectedValues: string[]) {
    if (!confirmation) {
      return;
    }

    setDrafts((current) => ({
      ...current,
      [confirmation.id]: {
        selectedOptionValue: selectedValues[0] ?? null,
        touched: true,
      },
    }));
  }

  function handleResolve() {
    if (!confirmation) {
      return;
    }

    if (!canResolve) {
      setDrafts((current) => ({
        ...current,
        [confirmation.id]: {
          ...emptyDraft(),
          ...current[confirmation.id],
          touched: true,
        },
      }));
      return;
    }

    if (selectedValue !== null) {
      onResolve(selectedValue);
    }
  }

  if (confirmation === undefined) {
    return (
      <section className={styles.root}>
        <Text as="strong" variant="label">
          {confirmationText.labels.decisionUnavailable}
        </Text>
        <Text variant="muted">{detail.fallbackBody}</Text>
      </section>
    );
  }

  if (isTerminal) {
    return (
      <section className={styles.root} data-confirmation-id={confirmation.id}>
        <div className={styles.titleRow}>
          <Text as="strong" variant="label">
            {confirmationText.labels.confirmationStatus({
              status: confirmationText.statuses[confirmation.status],
            })}
          </Text>
          <Badge
            tone={confirmation.status === "resolved" ? "success" : "danger"}
          >
            {confirmationText.statuses[confirmation.status]}
          </Badge>
        </div>
        <Text variant="muted">{confirmationText.messages.decisionReadOnly}</Text>
      </section>
    );
  }

  const options = (confirmation.options.length > 0
    ? confirmation.options
    : fallbackOptions
  ).map((option) => ({
    label: option.label,
    recommended: option.value === confirmation.defaultOptionValue,
    tone: choiceTone(option),
    value: option.value,
  }));

  return (
    <section className={styles.root} data-confirmation-id={confirmation.id}>
      <div className={styles.titleRow}>
        <Text as="strong" variant="label">
          {isResolving
            ? confirmationText.labels.resolvingDecision
            : confirmationText.labels.decisionNeeded}
        </Text>
        <Badge tone="warning">
          {confirmationText.statuses[confirmation.status]}
        </Badge>
      </div>
      <div className={styles.impactSummary}>
        <Badge size="sm" tone="warning">
          {confirmationText.labels.impact}
        </Badge>
        <Text variant="muted">
          {confirmation.riskLabel ?? confirmationText.messages.executionWaits}
        </Text>
      </div>

      <ChoiceGroup
        disabled={isResolving}
        error={
          draft.touched && !hasValidSelection
            ? confirmationText.messages.selectOneOption
            : null
        }
        layout={options.length <= 3 ? "segmented" : "rows"}
        onChange={selectOption}
        options={options}
        selectedValues={selectedValue ? [selectedValue] : []}
      />

      {detail.commandError ? (
        <div className={styles.commandErrorBlock}>
          <Text className={styles.error} role="alert" variant="muted">
            {detail.commandError}
          </Text>
          <ProductRecoveryActions actions={detail.commandRecoveryActions} />
        </div>
      ) : null}

      <div className={styles.actionRow}>
        <Button disabled={!canResolve} onClick={handleResolve} variant="primary">
          {isResolving
            ? confirmationText.actions.resolving
            : confirmationText.actions.resolveDecision}
        </Button>
      </div>
    </section>
  );
}

function emptyDraft(): ConfirmationDraft {
  return {
    selectedOptionValue: null,
    touched: false,
  };
}

function choiceTone(option: ConfirmationActionView["options"][number]): ChoiceOptionTone {
  if (option.tone === "primary" || option.tone === "danger") {
    return option.tone;
  }

  return "neutral";
}

function fallbackConfirmationOptions(
  actions: UiTextCatalog["main"]["interaction"]["confirmation"]["actions"],
): NonNullable<ConfirmationActionView["options"]> {
  return [
    { value: "confirmed", label: actions.confirm, tone: "primary" },
    { value: "revise", label: actions.reviseTask, tone: "secondary" },
    { value: "skipped", label: actions.skip, tone: "danger" },
  ];
}
