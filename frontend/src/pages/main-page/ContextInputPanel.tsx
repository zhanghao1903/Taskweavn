import { SendHorizontal } from "lucide-react";
import type { FormEvent } from "react";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import { Button, Panel, Text } from "../../shared/components";
import { ProductRecoveryActions } from "./ProductRecoveryActions";
import type { MainPageInputViewModel } from "./mainPageViewModel";
import styles from "./MainPage.module.css";

export type ContextInputPanelProps = {
  draft: string;
  error: string | null;
  input: MainPageInputViewModel;
  onDraftChange: (draft: string) => void;
  onSubmit: () => void;
  recoveryActions: ProductRecoveryAction[];
};

export function ContextInputPanel({
  draft,
  error,
  input,
  onDraftChange,
  onSubmit,
  recoveryActions,
}: ContextInputPanelProps) {
  const helperText = error ?? input.disabledReason;
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
    <Panel as="form" className={styles.contextInput} onSubmit={handleSubmit}>
      <div className={styles.contextInputScope}>
        <Text as="strong" variant="label">
          {input.scope.label}
        </Text>
        {scopeDescription ? <Text variant="muted">{scopeDescription}</Text> : null}
        {error ? <ProductRecoveryActions actions={recoveryActions} /> : null}
      </div>
      <label className={styles.contextInputField}>
        <input
          aria-label="Context message"
          disabled={input.disabled}
          onChange={(event) => onDraftChange(event.currentTarget.value)}
          placeholder={inputPlaceholder}
          value={draft}
        />
      </label>
      <Button
        disabled={!draft.trim() || input.disabled}
        type="submit"
        aria-label="Send message"
        size="icon"
        variant="primary"
      >
        <SendHorizontal size={18} aria-hidden="true" />
      </Button>
    </Panel>
  );
}
