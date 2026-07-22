import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import { productRecoveryActionText } from "../../shared/api/productErrors";
import { Badge, Button } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import styles from "./ProductRecoveryActions.module.css";

export type ProductRecoveryActionsProps = {
  actions: readonly ProductRecoveryAction[];
  ariaLabel?: string;
  isActionEnabled?: (action: ProductRecoveryAction) => boolean;
  onAction?: (action: ProductRecoveryAction) => void;
};

export function ProductRecoveryActions({
  actions,
  ariaLabel,
  isActionEnabled,
  onAction,
}: ProductRecoveryActionsProps) {
  const uiText = useUiText();

  if (actions.length === 0) {
    return null;
  }

  return (
    <div
      aria-label={ariaLabel ?? uiText.productError.recoveryAriaLabel}
      className={styles.root}
    >
      {actions.map((action, index) => {
        const actionText = productRecoveryActionText(action, uiText);
        const isInteractive =
          onAction !== undefined && (isActionEnabled?.(action) ?? true);
        if (isInteractive) {
          return (
            <Button
              className={styles.actionButton}
              data-recovery-action={action}
              key={`${action}-${index}`}
              onClick={() => onAction(action)}
              size="sm"
              title={actionText.description}
              variant={action === "none" ? "ghost" : "secondary"}
            >
              {actionText.label}
            </Button>
          );
        }
        return (
          <Badge
            className={styles.action}
            data-recovery-action={action}
            key={`${action}-${index}`}
            size="sm"
            title={actionText.description}
            tone={action === "none" ? "neutral" : "blue"}
          >
            {actionText.label}
          </Badge>
        );
      })}
    </div>
  );
}
