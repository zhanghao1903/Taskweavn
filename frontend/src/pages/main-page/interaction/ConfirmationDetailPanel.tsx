import { useEffect, useMemo, useState } from "react";

import type { ConfirmationActionView } from "../../../shared/api/types";
import { Badge, Button, ChoiceGroup, Text } from "../../../shared/components";
import type { ChoiceOptionTone } from "../../../shared/components";
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
  const confirmation = detail.confirmation;
  const [drafts, setDrafts] = useState<DraftsByConfirmationId>({});
  const optionValues = useMemo(
    () => (confirmation?.options ?? fallbackConfirmationOptions).map((option) => option.value),
    [confirmation?.options],
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
          Decision unavailable
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
            Confirmation {confirmation.status}
          </Text>
          <Badge tone={confirmation.status === "resolved" ? "success" : "danger"}>
            {confirmation.status}
          </Badge>
        </div>
        <Text variant="muted">This decision is read-only.</Text>
      </section>
    );
  }

  const options = (confirmation.options.length > 0
    ? confirmation.options
    : fallbackConfirmationOptions
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
          {isResolving ? "Resolving decision" : "Decision needed"}
        </Text>
        <Badge tone="warning">{confirmation.status}</Badge>
      </div>
      <div className={styles.impactSummary}>
        <Badge size="sm" tone="warning">
          Impact
        </Badge>
        <Text variant="muted">
          {confirmation.riskLabel ?? "Execution waits for this decision."}
        </Text>
      </div>

      <ChoiceGroup
        disabled={isResolving}
        error={
          draft.touched && !hasValidSelection
            ? "Select one confirmation option."
            : null
        }
        layout={options.length <= 3 ? "segmented" : "rows"}
        onChange={selectOption}
        options={options}
        selectedValues={selectedValue ? [selectedValue] : []}
      />

      {detail.commandError ? (
        <Text className={styles.error} role="alert" variant="muted">
          {detail.commandError}
        </Text>
      ) : null}

      <div className={styles.actionRow}>
        <div className={styles.footerCopy}>
          <Text as="strong" variant="label">
            {hasValidSelection ? "1 option selected" : "No option selected"}
          </Text>
        </div>
        <Button disabled={!canResolve} onClick={handleResolve} variant="primary">
          {isResolving ? "Resolving" : "Resolve decision"}
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

const fallbackConfirmationOptions: NonNullable<
  ConfirmationActionView["options"]
> = [
  { value: "confirmed", label: "Confirm", tone: "primary" },
  { value: "revise", label: "Revise task", tone: "secondary" },
  { value: "skipped", label: "Skip", tone: "danger" },
];
