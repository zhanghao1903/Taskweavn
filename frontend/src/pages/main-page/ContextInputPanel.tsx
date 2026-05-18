import { SendHorizontal } from "lucide-react";
import type { FormEvent } from "react";

import { Button, Panel, Text } from "../../shared/components";
import type { MainPageInputScopeView } from "./mainPageUiTypes";
import styles from "./MainPage.module.css";

export type ContextInputPanelProps = {
  disabled: boolean;
  draft: string;
  error: string | null;
  inputScope: MainPageInputScopeView;
  onDraftChange: (draft: string) => void;
  onSubmit: () => void;
};

export function ContextInputPanel({
  disabled,
  draft,
  error,
  inputScope,
  onDraftChange,
  onSubmit,
}: ContextInputPanelProps) {
  function handleSubmit(event: FormEvent<HTMLElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <Panel as="form" className={styles.contextInput} onSubmit={handleSubmit}>
      <div>
        <Text as="strong" variant="label">
          {inputScope.label}
        </Text>
        {error ? (
          <Text variant="muted">{error}</Text>
        ) : (
          <Text variant="muted">{inputScope.placeholder}</Text>
        )}
      </div>
      <label className={styles.contextInputField}>
        <span>Message</span>
        <input
          aria-label="Context message"
          disabled={disabled}
          onChange={(event) => onDraftChange(event.currentTarget.value)}
          placeholder={inputScope.placeholder}
          value={draft}
        />
      </label>
      <Button
        disabled={!draft.trim() || disabled}
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
