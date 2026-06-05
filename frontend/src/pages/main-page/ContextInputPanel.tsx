import { SendHorizontal } from "lucide-react";
import type { FormEvent } from "react";

import { Button, Panel, Text } from "../../shared/components";
import type { MainPageInputViewModel } from "./mainPageViewModel";
import styles from "./MainPage.module.css";

export type ContextInputPanelProps = {
  draft: string;
  error: string | null;
  input: MainPageInputViewModel;
  onDraftChange: (draft: string) => void;
  onSubmit: () => void;
};

export function ContextInputPanel({
  draft,
  error,
  input,
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
          {input.scope.label}
        </Text>
        <Text variant="muted">
          {error ?? input.disabledReason ?? input.scope.placeholder}
        </Text>
      </div>
      <label className={styles.contextInputField}>
        <input
          aria-label="Context message"
          disabled={input.disabled}
          onChange={(event) => onDraftChange(event.currentTarget.value)}
          placeholder={input.scope.placeholder}
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
