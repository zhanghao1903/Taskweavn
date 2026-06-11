import { Button, Text } from "../../shared/components";
import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import { useUiText } from "../../shared/ui-text";
import type { MainPageAuditEntryViewModel } from "./mainPageViewModel";
import { ProductRecoveryActions } from "./ProductRecoveryActions";
import styles from "./MainPage.module.css";

export type MainPageWorkspaceHeaderProps = {
  auditEntry: MainPageAuditEntryViewModel;
  eventError: string | null;
  isPublishingTaskTree: boolean;
  onPublishTaskTree: () => void;
  showPublishTaskTree: boolean;
  taskTreeCommandError: string | null;
  taskTreeCommandRecoveryActions: ProductRecoveryAction[];
  title: string;
  uiNotice: string | null;
  usageHref?: string | null;
};

export function MainPageWorkspaceHeader({
  auditEntry,
  eventError,
  isPublishingTaskTree,
  onPublishTaskTree,
  showPublishTaskTree,
  taskTreeCommandError,
  taskTreeCommandRecoveryActions,
  title,
  uiNotice,
  usageHref = null,
}: MainPageWorkspaceHeaderProps) {
  const uiText = useUiText();

  return (
    <div className={styles.sectionHeader}>
      <div>
        <Text as="h1" variant="heading">
          {title}
        </Text>
        {taskTreeCommandError ? (
          <div className={styles.commandErrorBlock}>
            <Text variant="muted">{taskTreeCommandError}</Text>
            <ProductRecoveryActions
              actions={taskTreeCommandRecoveryActions}
            />
          </div>
        ) : null}
        {eventError ? <Text variant="muted">{eventError}</Text> : null}
        {uiNotice ? <Text variant="muted">{uiNotice}</Text> : null}
      </div>
      <div className={styles.actionRow}>
        {showPublishTaskTree ? (
          <Button
            disabled={isPublishingTaskTree}
            onClick={onPublishTaskTree}
          >
            {isPublishingTaskTree
              ? uiText.main.states.publishingPlan
              : uiText.main.actions.publishPlan}
          </Button>
        ) : null}
        {usageHref ? (
          <Button asChild>
            <a href={usageHref}>{uiText.usage.actions.openUsage}</a>
          </Button>
        ) : null}
        {auditEntry.isEnabled ? (
          <Button asChild>
            <a href={auditEntry.href}>{auditEntry.label}</a>
          </Button>
        ) : (
          <Button disabled title={auditEntry.disabledReason ?? undefined}>
            {auditEntry.label}
          </Button>
        )}
      </div>
    </div>
  );
}
