import type { ReactNode } from "react";

import { Badge, Button, Text } from "../../shared/components";
import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type { BadgePresentation } from "./mainPageSelectors";
import { useUiText } from "../../shared/ui-text";
import type { MainPageAuditEntryViewModel } from "./mainPageViewModel";
import { ProductRecoveryActions } from "./ProductRecoveryActions";
import styles from "./MainPage.module.css";

export type MainPageWorkspaceHeaderProps = {
  actionSlot?: ReactNode;
  auditEntry: MainPageAuditEntryViewModel;
  eventError: string | null;
  isPublishingTaskTree: boolean;
  onPublishTaskTree: () => void;
  projectName?: string;
  showPublishTaskTree: boolean;
  sessionName?: string;
  statusActions?: ReactNode;
  statuses?: BadgePresentation[];
  taskTreeCommandError: string | null;
  taskTreeCommandRecoveryActions: ProductRecoveryAction[];
  title: string;
  uiNotice: string | null;
};

export function MainPageWorkspaceHeader({
  actionSlot = null,
  auditEntry,
  eventError,
  isPublishingTaskTree,
  onPublishTaskTree,
  projectName = "",
  showPublishTaskTree,
  sessionName = "",
  statusActions = null,
  statuses = [],
  taskTreeCommandError,
  taskTreeCommandRecoveryActions,
  title,
  uiNotice,
}: MainPageWorkspaceHeaderProps) {
  const uiText = useUiText();

  return (
    <div className={styles.sessionWorkHeader}>
      <div className={styles.sessionWorkStatusRow}>
        <div className={styles.sessionWorkContext}>
          {projectName ? (
            <Text as="span" className={styles.sessionWorkProjectName}>
              {projectName}
            </Text>
          ) : null}
          {sessionName ? (
            <Text as="span" className={styles.sessionWorkSessionName}>
              {uiText.main.labels.sessionName({ name: sessionName })}
            </Text>
          ) : null}
        </div>
        <div className={styles.sessionWorkStatusCluster}>
          {statuses.map((status, index) => (
            <Badge
              className={styles.sessionWorkStatusBadge}
              key={`${status.label}-${index}`}
              tone={status.tone}
            >
              {status.label}
            </Badge>
          ))}
          {statusActions}
        </div>
      </div>
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
          {actionSlot}
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
    </div>
  );
}
