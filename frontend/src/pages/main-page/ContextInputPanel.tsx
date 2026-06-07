import { SendHorizontal } from "lucide-react";
import type { FormEvent } from "react";

import { Button, Panel, Text } from "../../shared/components";
import type { MainPageInputViewModel } from "./mainPageViewModel";
import styles from "./MainPage.module.css";

export type ContextInputPanelProps = {
  draft: string;
  error: string | null;
  input: MainPageInputViewModel;
  isFloating?: boolean;
  onDraftChange: (draft: string) => void;
  onSubmit: () => void;
};

export function ContextInputPanel({
  draft,
  error,
  input,
  isFloating = false,
  onDraftChange,
  onSubmit,
}: ContextInputPanelProps) {
  const scopeLabel = splitWritingScopeLabel(input.scope.label);
  const helperText = error ?? null;
  const scopeDescription = helperText ?? input.scope.description;
  const inputPlaceholder =
    input.disabled && input.disabledReason
      ? input.disabledReason
      : input.scope.placeholder;

  function handleSubmit(event: FormEvent<HTMLElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <Panel
      as="form"
      className={
        isFloating
          ? `${styles.contextInput} ${styles.floatingContextInput}`
          : styles.contextInput
      }
      onSubmit={handleSubmit}
    >
      <div className={styles.contextInputScope}>
        {scopeLabel ? (
          <>
            <Text
              as="span"
              className={styles.contextInputScopePrefix}
              variant="label"
            >
              Writing to
            </Text>
            <Text
              as="strong"
              className={styles.contextInputScopeTarget}
              variant="label"
            >
              {scopeLabel.target}
            </Text>
          </>
        ) : (
          <Text as="strong" variant="label">
            {input.scope.label}
          </Text>
        )}
        {helperText ? (
          <Text variant="muted">{helperText}</Text>
        ) : scopeDescription && !scopeLabel ? (
          <Text variant="muted">{scopeDescription}</Text>
        ) : null}
      </div>
      <div className={styles.contextInputField}>
        <input
          aria-label="Context message"
          disabled={input.disabled}
          onChange={(event) => onDraftChange(event.currentTarget.value)}
          placeholder={inputPlaceholder}
          value={draft}
        />
        <Button
          disabled={!draft.trim() || input.disabled}
          type="submit"
          aria-label="Send message"
          size="icon"
          variant="primary"
        >
          <SendHorizontal size={18} aria-hidden="true" />
        </Button>
      </div>
    </Panel>
  );
}

function splitWritingScopeLabel(label: string): { target: string } | null {
  const prefix = "Writing to ";
  if (!label.startsWith(prefix)) {
    return null;
  }

  const target = label.slice(prefix.length).trim();
  return target ? { target } : null;
}
