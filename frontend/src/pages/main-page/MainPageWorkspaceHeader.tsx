import { Button, Text } from "../../shared/components";
import type { MainPageAuditEntryViewModel } from "./mainPageViewModel";
import styles from "./MainPage.module.css";

export type MainPageWorkspaceHeaderProps = {
  auditEntry: MainPageAuditEntryViewModel;
  eventError: string | null;
  isPublishingTaskTree: boolean;
  onPublishTaskTree: () => void;
  showPublishTaskTree: boolean;
  taskTreeCommandError: string | null;
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
  title,
  uiNotice,
}: MainPageWorkspaceHeaderProps) {
  return (
    <div className={styles.sectionHeader}>
      <div>
        <Text variant="eyebrow">Session</Text>
        <Text as="h1" variant="heading">
          {title}
        </Text>
        {taskTreeCommandError ? (
          <Text variant="muted">{taskTreeCommandError}</Text>
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
            {isPublishingTaskTree ? "Publishing tasks" : "Publish tasks"}
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
