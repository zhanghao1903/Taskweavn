import { useState } from "react";

import type { SessionActivityItemView } from "../../shared/api/types";
import { Badge, Button, MarkdownContent, Text } from "../../shared/components";
import styles from "./MainPage.module.css";

export type ArchivedPlansPanelProps = {
  auditHref: string;
  items: readonly SessionActivityItemView[];
  onClose: () => void;
};

export function ArchivedPlansPanel({
  auditHref,
  items,
  onClose,
}: ArchivedPlansPanelProps) {
  const [readerItem, setReaderItem] = useState<SessionActivityItemView | null>(
    null,
  );

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
          <h2>{readerItem ? archivedPlanTitle(readerItem) : "Archived Plans"}</h2>
          <p>
            {readerItem
              ? "Read-only record of the archived plan."
              : "Plans moved out of the active workspace remain available here."}
          </p>
        </div>
        <Button onClick={onClose} size="sm" variant="secondary">
          Close
        </Button>
      </div>

      {readerItem ? (
        <ArchivedPlanReader
          auditHref={auditHref}
          item={readerItem}
          onBack={() => setReaderItem(null)}
        />
      ) : items.length === 0 ? (
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
                <time dateTime={item.occurredAt}>
                  {formatArchivedPlanTime(item.occurredAt)}
                </time>
              </div>
              <h3>{archivedPlanTitle(item)}</h3>
              <MarkdownContent
                className={styles.archivedPlanPreview}
                maxLines={4}
                source={item.body}
                variant="activity"
              />
              <div className={styles.archivedPlanActions}>
                <Button
                  onClick={() => setReaderItem(item)}
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

function ArchivedPlanReader({
  auditHref,
  item,
  onBack,
}: {
  auditHref: string;
  item: SessionActivityItemView;
  onBack: () => void;
}) {
  return (
    <section
      aria-label="Archived plan detail"
      className={styles.archivedPlanReader}
    >
      <div className={styles.archivedPlanReaderActions}>
        <Button onClick={onBack} size="sm" variant="secondary">
          Back to plans
        </Button>
        <Button asChild size="sm" variant="ghost">
          <a href={auditHref}>View audit</a>
        </Button>
      </div>
      <MarkdownContent
        className={styles.archivedPlanBody}
        source={item.body}
        variant="activity"
      />
    </section>
  );
}

function archivedPlanTitle(item: SessionActivityItemView): string {
  const titleMatch = item.body.match(/^\s*\*\*(.+?)\*\*/m);
  if (titleMatch?.[1]) {
    return titleMatch[1].trim();
  }

  const firstLine = item.body
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.length > 0);

  return firstLine?.replaceAll("*", "").trim() || item.title;
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
