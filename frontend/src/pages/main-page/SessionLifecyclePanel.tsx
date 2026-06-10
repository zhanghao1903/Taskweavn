import type { FormEvent } from "react";

import { Button, Text } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import type { MainPageController } from "./useMainPageController";
import styles from "./MainPage.module.css";

export type SessionLifecyclePanelProps = {
  dialog: MainPageController["sessionDialog"];
  isCreatingSession: boolean;
  isDeletingSession: boolean;
  isRenamingSession: boolean;
  onCancel: () => void;
  onChangeDraft: (draftName: string) => void;
  onSubmit: () => void;
};

export function SessionLifecyclePanel({
  dialog,
  isCreatingSession,
  isDeletingSession,
  isRenamingSession,
  onCancel,
  onChangeDraft,
  onSubmit,
}: SessionLifecyclePanelProps) {
  const uiText = useUiText();

  if (dialog.mode === "idle") {
    return null;
  }

  const isPending =
    (dialog.mode === "create" && isCreatingSession) ||
    (dialog.mode === "rename" && isRenamingSession) ||
    (dialog.mode === "delete" && isDeletingSession);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  if (dialog.mode === "delete") {
    return (
      <div
        aria-label={uiText.main.actions.deleteSession}
        aria-modal="true"
        className={styles.sessionLifecycleOverlay}
        role="dialog"
      >
        <section
          aria-label={uiText.main.sessionDialog.deleteConfirmationAriaLabel}
          className={styles.sessionLifecyclePanel}
        >
          <Text as="h3" variant="subheading">
            {uiText.main.sessionDialog.deleteTitle}
          </Text>
          <Text variant="muted">
            {uiText.main.sessionDialog.deleteConfirmationBody({
              name: dialog.session.name,
            })}
          </Text>
          {dialog.error ? <Text variant="muted">{dialog.error}</Text> : null}
          <div className={styles.sessionLifecycleActions}>
            <Button
              disabled={isPending}
              onClick={onSubmit}
              size="sm"
              variant="danger"
            >
              {isPending
                ? uiText.main.sessionDialog.deleting
                : uiText.main.actions.deleteSession}
            </Button>
            <Button
              disabled={isPending}
              onClick={onCancel}
              size="sm"
              variant="ghost"
            >
              {uiText.common.actions.cancel}
            </Button>
          </div>
        </section>
      </div>
    );
  }

  const title =
    dialog.mode === "create"
      ? uiText.main.sessionDialog.createTitle
      : uiText.main.sessionDialog.renameTitle;
  const submitLabel =
    dialog.mode === "create"
      ? isPending
        ? uiText.main.states.creatingSession
        : uiText.main.sessionDialog.createTitle
      : isPending
        ? uiText.main.sessionDialog.renaming
        : uiText.main.sessionDialog.renameTitle;
  const formLabel =
    dialog.mode === "create"
      ? uiText.main.sessionDialog.createFormAriaLabel
      : uiText.main.sessionDialog.renameFormAriaLabel;

  return (
    <div
      aria-label={title}
      aria-modal="true"
      className={styles.sessionLifecycleOverlay}
      role="dialog"
    >
      <form
        aria-label={formLabel}
        className={styles.sessionLifecyclePanel}
        onSubmit={handleSubmit}
      >
        <Text as="h3" variant="subheading">
          {title}
        </Text>
        <label className={styles.sessionLifecycleField}>
          <span>{uiText.main.sessionDialog.sessionName}</span>
          <input
            aria-label={uiText.main.sessionDialog.sessionName}
            disabled={isPending}
            onChange={(event) => onChangeDraft(event.currentTarget.value)}
            value={dialog.draftName}
          />
        </label>
        {dialog.error ? <Text variant="muted">{dialog.error}</Text> : null}
        <div className={styles.sessionLifecycleActions}>
          <Button disabled={isPending} size="sm" type="submit">
            {submitLabel}
          </Button>
          <Button
            disabled={isPending}
            onClick={onCancel}
            size="sm"
            variant="ghost"
          >
            {uiText.common.actions.cancel}
          </Button>
        </div>
      </form>
    </div>
  );
}
