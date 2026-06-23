import type { ConfirmationActionView } from "../../shared/api/types";
import { Badge, Button, Panel, Text } from "../../shared/components";
import styles from "./MainPage.module.css";

export type ConfirmationDockProps = {
  error: string | null;
  confirmations: readonly ConfirmationActionView[];
  isResolving: boolean;
  onResolve: (confirmation: ConfirmationActionView, value: string) => void;
};

export function ConfirmationDock({
  error,
  confirmations,
  isResolving,
  onResolve,
}: ConfirmationDockProps) {
  if (confirmations.length === 0) {
    return null;
  }

  return (
    <Panel
      aria-label="Pending confirmations"
      className={styles.confirmationDock}
      title="Decision required"
    >
      <div className={styles.confirmationDockHeader}>
        <Text variant="muted">
          Agent execution is waiting for user authorization.
        </Text>
        <Badge size="sm" tone="warning">
          {confirmations.length} pending
        </Badge>
      </div>
      <div className={styles.confirmationDockList}>
        {confirmations.map((confirmation) => (
          <article
            className={styles.confirmationDockItem}
            key={confirmation.id}
          >
            <div className={styles.confirmationDockCopy}>
              <Text as="strong" variant="label">
                {confirmation.title}
              </Text>
              <Text variant="muted">{confirmation.body}</Text>
              {confirmation.riskLabel ? (
                <Badge size="sm" tone="warning">
                  {confirmation.riskLabel}
                </Badge>
              ) : null}
            </div>
            <div className={styles.confirmationDockActions}>
              {confirmation.options.map((option) => (
                <Button
                  aria-label={`Quick decision: ${option.label}`}
                  disabled={isResolving}
                  key={option.value}
                  onClick={() => onResolve(confirmation, option.value)}
                  size="sm"
                  variant={buttonVariant(option.tone)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
          </article>
        ))}
      </div>
      {error ? (
        <Text className={styles.confirmationDockError}>
          {error}
        </Text>
      ) : null}
    </Panel>
  );
}

function buttonVariant(
  tone: ConfirmationActionView["options"][number]["tone"],
) {
  if (tone === "primary" || tone === "danger") {
    return tone;
  }
  return "secondary";
}
