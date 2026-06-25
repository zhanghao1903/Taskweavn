import type { PlanView } from "../../shared/api/types";
import { Badge, Button, Text } from "../../shared/components";
import styles from "./MainPage.module.css";

export type ArchivedPlansPanelProps = {
  auditHref: string;
  items: readonly PlanView[];
  onClose: () => void;
  onOpenPlan: (planId: string) => void;
};

export function ArchivedPlansPanel({
  auditHref,
  items,
  onClose,
  onOpenPlan,
}: ArchivedPlansPanelProps) {
  return (
    <aside
      aria-label="Archived Plans"
      className={styles.archivedPlansPanel}
      role="dialog"
    >
      <div className={styles.archivedPlansHeader}>
        <div>
          <Text as="span" variant="eyebrow">
            Plan archive
          </Text>
          <h2>Archived Plans</h2>
          <p>Plans moved out of the active workspace remain available here.</p>
        </div>
        <Button onClick={onClose} size="sm" variant="secondary">
          Close
        </Button>
      </div>

      {items.length === 0 ? (
        <div className={styles.archivedPlansEmpty}>
          <strong>No archived plans</strong>
          <p>Archived plan records will appear here after a plan is archived.</p>
        </div>
      ) : (
        <ol className={styles.archivedPlanList}>
          {items.map((item) => (
            <li className={styles.archivedPlanItem} key={item.id}>
              <div className={styles.archivedPlanItemHeader}>
                <Badge size="sm" tone="neutral">
                  Archived
                </Badge>
                {item.archivedAt ? (
                  <time dateTime={item.archivedAt}>
                    {formatArchivedPlanTime(item.archivedAt)}
                  </time>
                ) : (
                  <span className={styles.archivedPlanTimeFallback}>
                    Archived time unavailable
                  </span>
                )}
              </div>
              <h3>{item.title}</h3>
              <p
                className={styles.archivedPlanPreview}
              >
                {item.summary}
              </p>
              <Text variant="muted">
                {archivedPlanTaskCount(item.taskCount)}
              </Text>
              <div className={styles.archivedPlanActions}>
                <Button
                  onClick={() => onOpenPlan(item.id)}
                  size="sm"
                  variant="secondary"
                >
                  Open plan
                </Button>
                <Button asChild size="sm" variant="ghost">
                  <a href={auditHref}>View audit</a>
                </Button>
              </div>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}

function formatArchivedPlanTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString(undefined, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function archivedPlanTaskCount(count: number): string {
  return `${count} task${count === 1 ? "" : "s"} moved to Session history.`;
}
