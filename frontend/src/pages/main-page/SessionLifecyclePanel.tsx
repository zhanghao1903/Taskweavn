import type { FormEvent } from "react";

import { Button, Text } from "../../shared/components";
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
        aria-label="Delete session"
        aria-modal="true"
        className={styles.sessionLifecycleOverlay}
        role="dialog"
      >
        <section
          aria-label="Delete session confirmation"
          className={styles.sessionLifecyclePanel}
        >
          <Text as="h3" variant="subheading">
            Delete session?
          </Text>
          <Text variant="muted">
            Delete session "{dialog.session.name}"? Plato will archive the local
            workspace state and move to the next available session.
          </Text>
          {dialog.error ? <Text variant="muted">{dialog.error}</Text> : null}
          <div className={styles.sessionLifecycleActions}>
            <Button
              disabled={isPending}
              onClick={onSubmit}
              size="sm"
              variant="danger"
            >
              {isPending ? "Deleting" : "Delete session"}
            </Button>
            <Button
              disabled={isPending}
              onClick={onCancel}
              size="sm"
              variant="ghost"
            >
              Cancel
            </Button>
          </div>
        </section>
      </div>
    );
  }

  const title = dialog.mode === "create" ? "Create session" : "Rename session";
  const submitLabel =
    dialog.mode === "create"
      ? isPending
        ? "Creating"
        : "Create session"
      : isPending
        ? "Renaming"
        : "Rename session";

  return (
    <div
      aria-label={title}
      aria-modal="true"
      className={styles.sessionLifecycleOverlay}
      role="dialog"
    >
      <form
        aria-label={`${title} form`}
        className={styles.sessionLifecyclePanel}
        onSubmit={handleSubmit}
      >
        <Text as="h3" variant="subheading">
          {title}
        </Text>
        <label className={styles.sessionLifecycleField}>
          <span>Session name</span>
          <input
            aria-label="Session name"
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
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
