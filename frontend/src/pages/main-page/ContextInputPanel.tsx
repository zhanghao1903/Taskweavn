import { LoaderCircle, SendHorizontal } from "lucide-react";
import type { FormEvent, Ref } from "react";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import { Button, Panel, Text } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import { ProductRecoveryActions } from "./ProductRecoveryActions";
import type { MainPageInputViewModel } from "./mainPageViewModel";
import styles from "./MainPage.module.css";

export type ContextInputPanelProps = {
  draft: string;
  error: string | null;
  input: MainPageInputViewModel;
  inputRef?: Ref<HTMLInputElement>;
  isFloating?: boolean;
  isSubmitting?: boolean;
  onDraftChange: (draft: string) => void;
  onSubmit: () => void;
  recoveryActions: ProductRecoveryAction[];
};

export function ContextInputPanel({
  draft,
  error,
  input,
  inputRef,
  isFloating = false,
  isSubmitting = false,
  onDraftChange,
  onSubmit,
  recoveryActions,
}: ContextInputPanelProps) {
  const uiText = useUiText();
  const scopeLabel = splitWritingScopeLabel(input.scope.label);
  const inputPlaceholder =
    input.disabled && input.disabledReason
      ? input.disabledReason
      : input.scope.placeholder;
  const className = [
    styles.contextInput,
    isFloating ? styles.floatingContextInput : null,
    error ? styles.contextInputWithError : null,
  ]
    .filter(Boolean)
    .join(" ");

  function handleSubmit(event: FormEvent<HTMLElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <Panel
      as="form"
      className={className}
      onSubmit={handleSubmit}
    >
      {error ? (
        <div
          aria-live="polite"
          className={styles.contextInputError}
          role="alert"
        >
          <Text as="span" variant="body">
            {error}
          </Text>
          <ProductRecoveryActions actions={recoveryActions} />
        </div>
      ) : null}
      <div className={styles.contextInputScope}>
        {scopeLabel ? (
          <>
            <Text
              as="span"
              className={styles.contextInputScopePrefix}
              variant="label"
            >
              {uiText.main.input.writingToPrefix}
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
        {input.scope.description && !scopeLabel ? (
          <Text variant="muted">{input.scope.description}</Text>
        ) : null}
      </div>
      <div className={styles.contextInputField}>
        <input
          aria-label={uiText.main.input.contextMessageAriaLabel}
          disabled={input.disabled}
          onChange={(event) => onDraftChange(event.currentTarget.value)}
          placeholder={inputPlaceholder}
          ref={inputRef}
          value={draft}
        />
        <Button
          disabled={!draft.trim() || input.disabled || isSubmitting}
          type="submit"
          aria-busy={isSubmitting ? true : undefined}
          aria-label={uiText.main.input.sendMessageAriaLabel}
          className={isSubmitting ? styles.contextInputSubmitPending : undefined}
          size="icon"
          variant="primary"
        >
          {isSubmitting ? (
            <LoaderCircle
              className={styles.contextInputSubmitSpinner}
              size={18}
              aria-hidden="true"
            />
          ) : (
            <SendHorizontal size={18} aria-hidden="true" />
          )}
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
