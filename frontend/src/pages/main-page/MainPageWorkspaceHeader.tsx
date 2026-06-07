import { Button, Text } from "../../shared/components";
import type { ProductRecoveryAction } from "../../shared/api/platoApi";
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
}: MainPageWorkspaceHeaderProps) {
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
            {isPublishingTaskTree ? "Publishing plan" : "Publish plan"}
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
