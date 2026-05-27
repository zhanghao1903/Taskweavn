import { Button, Text } from "../../shared/components";
import styles from "./MainPage.module.css";

export type MainPageWorkspaceHeaderProps = {
  eventError: string | null;
  isPublishingTaskTree: boolean;
  onPublishTaskTree: () => void;
  onViewAudit: () => void;
  showPublishTaskTree: boolean;
  taskTreeCommandError: string | null;
  title: string;
  uiNotice: string | null;
};

export function MainPageWorkspaceHeader({
  eventError,
  isPublishingTaskTree,
  onPublishTaskTree,
  onViewAudit,
  showPublishTaskTree,
  taskTreeCommandError,
  title,
  uiNotice,
}: MainPageWorkspaceHeaderProps) {
  return (
    <div className={styles.sectionHeader}>
      <div>
        <Text variant="eyebrow">Session workspace</Text>
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
            {isPublishingTaskTree ? "Publishing" : "Publish TaskTree"}
          </Button>
        ) : null}
        <Button onClick={onViewAudit}>View audit</Button>
      </div>
    </div>
  );
}
