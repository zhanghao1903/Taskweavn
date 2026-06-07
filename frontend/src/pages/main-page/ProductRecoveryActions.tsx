import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import {
  productRecoveryActionDescription,
  productRecoveryActionLabel,
} from "../../shared/api/productErrors";
import { Badge } from "../../shared/components";
import styles from "./ProductRecoveryActions.module.css";

export type ProductRecoveryActionsProps = {
  actions: readonly ProductRecoveryAction[];
  ariaLabel?: string;
};

export function ProductRecoveryActions({
  actions,
  ariaLabel = "Suggested recovery actions",
}: ProductRecoveryActionsProps) {
  if (actions.length === 0) {
    return null;
  }

  return (
    <div aria-label={ariaLabel} className={styles.root}>
      {actions.map((action, index) => (
        <Badge
          className={styles.action}
          data-recovery-action={action}
          key={`${action}-${index}`}
          size="sm"
          title={productRecoveryActionDescription(action)}
          tone={action === "none" ? "neutral" : "blue"}
        >
          {productRecoveryActionLabel(action)}
        </Badge>
      ))}
    </div>
  );
}
