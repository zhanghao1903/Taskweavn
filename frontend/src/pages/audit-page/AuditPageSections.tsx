import type { ReactNode } from "react";

import { Button } from "../../shared/components";
import type { ApiUiBoundaryState } from "../../shared/api/apiUiMapping";
import { navigateApp } from "../../app/navigation";
import type {
  AuditCompleteness,
  AuditFilterKind,
  AuditPageSnapshot,
  AuditRecord,
  AuditRecordId,
  AuditVerdict,
} from "../../shared/api/types";
import { cx } from "../../shared/utils/cx";
import { PlatoProductMark } from "../main-page/PlatoProductMark";
import type { AuditPageRuntimeState } from "./auditRuntimeEvents";
import { formatAuditTime } from "./auditPageFormat";
import {
  auditBoundaryLabel,
  auditCompletenessLabel,
  auditFilterLabel,
  auditLiveStatusCopy,
  auditOverviewMetricFilters,
  auditScopeLabel,
  auditScopeStatusText,
  auditSubjectLabel,
  auditVerdictClassKey,
  auditVerdictLabel,
  auditVerdictNoticeTitle,
  type AuditVerdictClassKey,
} from "./auditPageLabels";
import styles from "./AuditPage.module.css";

const verdictBadgeClassNames: Record<AuditVerdictClassKey, string> = {
  failed: styles.badgeFailed,
  inconclusive: styles.badgeInconclusive,
  passed: styles.badgePassed,
  warning: styles.badgeWarning,
};

export function AuditPageFrame({
  children,
  snapshot,
}: {
  children: ReactNode;
  snapshot: AuditPageSnapshot | null;
}) {
  return (
    <div className={styles.page}>
      <AuditPageChrome snapshot={snapshot} />
      <div className={styles.shell}>{children}</div>
    </div>
  );
}

function AuditPageChrome({ snapshot }: { snapshot: AuditPageSnapshot | null }) {
  return (
    <div className={styles.topBar}>
      <div className={styles.brandBlock}>
        <PlatoProductMark className={styles.brandMark} />
        <div className={styles.brandCopy}>
          <span className={styles.brandName}>Plato</span>
          <span className={styles.brandSubtitle}>Task-first Intelligent Workbench</span>
        </div>
      </div>
      <div className={styles.topBarContextBlock}>
        <span className={styles.topBarLabel}>Project</span>
        <span className={styles.topBarValue}>
          {snapshot?.project?.name ?? "Project"}
        </span>
      </div>
      <span className={styles.workflowPill}>
        {snapshot?.workflow?.name ?? "Audit workflow"}
      </span>
      <div className={styles.sessionContextBlock}>
        <span className={styles.sessionValue}>
          Session: {snapshot?.session.name ?? "Audit"}
        </span>
      </div>
      <div className={styles.topBarActions}>
        <span className={styles.badge}>Read-only</span>
        <span className={styles.badge}>Trust plane</span>
        <Button
          disabled={snapshot === null}
          onClick={() => {
            if (snapshot !== null) {
              navigateApp(snapshot.entryContext.sourceRoute);
            }
          }}
          variant="secondary"
        >
          Return
        </Button>
      </div>
    </div>
  );
}

export function AuditHeader({
  boundary,
  snapshot,
}: {
  boundary: ApiUiBoundaryState;
  snapshot: AuditPageSnapshot;
}) {
  return (
    <header className={styles.header}>
      <div className={styles.headerSubjectCluster}>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>Audit</h1>
          <span className={styles.badge}>{auditScopeLabel(snapshot)}</span>
        </div>
        <div className={styles.headerSubjectMeta}>
          <p className={styles.subject}>{auditSubjectLabel(snapshot)}</p>
          <p className={styles.status}>
            {auditScopeStatusText(snapshot)} · Filter: {auditFilterLabel(snapshot.request.filter)}
          </p>
        </div>
      </div>
      <div className={styles.headerStatus}>
        <span className={styles.badge}>{auditBoundaryLabel(boundary)}</span>
        <span className={styles.badge}>No mutations</span>
      </div>
      <p className={styles.note}>
        Audit is a read-only trust plane. It explains what happened without
        changing the Task or session.
      </p>
    </header>
  );
}

export function Overview({
  boundary,
  onRetry,
  snapshot,
}: {
  boundary: ApiUiBoundaryState;
  onRetry?: () => void;
  snapshot: AuditPageSnapshot;
}) {
  const shouldShowBoundaryNotice = boundary.kind !== "ready";
  const shouldShowVerdictNotice =
    snapshot.overview.verdict !== "passed" &&
    snapshot.overview.verdict !== "not_available";

  return (
    <section aria-label="Audit overview" className={cx(styles.panel, styles.overview)}>
      <div className={styles.overviewPrimary}>
        <div className={styles.overviewHeadingRow}>
          <h2 className={styles.overviewTitle}>Audit Overview</h2>
          <div className={styles.overviewBadgeCluster}>
            <StatusBadge value={snapshot.overview.verdict} />
            <CompletenessBadge value={snapshot.overview.completeness} />
          </div>
        </div>
        <p className={styles.overviewCopy}>{snapshot.overview.summary}</p>
        {snapshot.overview.keyIssue !== null && (
          <p className={styles.overviewIssue}>
            Key issue: {snapshot.overview.keyIssue}
          </p>
        )}
        {(shouldShowBoundaryNotice || shouldShowVerdictNotice) && (
          <div className={styles.overviewNoticeStack}>
            {shouldShowBoundaryNotice && (
              <div className={styles.overviewNotice} role="status">
                <div className={styles.overviewNoticeMain}>
                  <strong>{auditBoundaryLabel(boundary)}</strong>
                  <span>{boundary.message}</span>
                  {boundary.code !== undefined && (
                    <span className={styles.overviewNoticeCode}>
                      Code: {boundary.code}
                    </span>
                  )}
                </div>
                <div className={styles.overviewNoticeActions}>
                  {boundary.shouldResync && (
                    <span className={styles.badge}>Resync suggested</span>
                  )}
                  {boundary.retryable && <span className={styles.badge}>Retryable</span>}
                  {boundary.retryable && onRetry !== undefined && (
                    <Button onClick={onRetry} variant="secondary">
                      {boundary.shouldResync ? "Refresh audit" : "Retry"}
                    </Button>
                  )}
                </div>
              </div>
            )}
            {shouldShowVerdictNotice && (
              <div className={styles.overviewNotice} role="note">
                <StatusBadge value={snapshot.overview.verdict} />
                <div className={styles.overviewNoticeMain}>
                  <strong>{auditVerdictNoticeTitle(snapshot.overview.verdict)}</strong>
                  <span>{snapshot.overview.keyIssue ?? snapshot.overview.summary}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      <div className={styles.overviewMetrics}>
        {auditOverviewMetricFilters.map((item) => (
          <div className={styles.metric} key={item.filter}>
            <span className={styles.metricLabel}>{item.label}</span>
            <strong className={styles.metricValue}>
              {snapshot.overview.recordCounts[item.filter] ?? 0}
            </strong>
            <span className={styles.metricNote}>visible records</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function VerdictNotice({ snapshot }: { snapshot: AuditPageSnapshot }) {
  if (
    snapshot.overview.verdict === "passed" ||
    snapshot.overview.verdict === "not_available"
  ) {
    return null;
  }

  return (
    <section
      aria-label="Audit verdict notice"
      className={cx(styles.panel, styles.verdictNotice)}
      role="note"
    >
      <StatusBadge value={snapshot.overview.verdict} />
      <div>
        <strong>{auditVerdictNoticeTitle(snapshot.overview.verdict)}</strong>
        <p>{snapshot.overview.keyIssue ?? snapshot.overview.summary}</p>
      </div>
    </section>
  );
}

export function LiveStatusNotice({
  liveState,
}: {
  liveState?: AuditPageRuntimeState;
}) {
  if (
    liveState === undefined ||
    liveState.status === "connected" ||
    liveState.status === "refreshing"
  ) {
    return null;
  }

  const copy = auditLiveStatusCopy(liveState);

  return (
    <section
      aria-live="polite"
      className={cx(
        styles.panel,
        styles.liveStatus,
        liveState.status === "stale" && styles.liveStatusStale,
        liveState.status === "disconnected" && styles.liveStatusDisconnected,
      )}
      role="status"
    >
      <div>
        <strong>{copy.title}</strong>
        <p>{copy.message}</p>
      </div>
      {liveState.eventCursor !== null && (
        <span className={styles.liveStatusMeta}>
          Cursor: {liveState.eventCursor}
        </span>
      )}
    </section>
  );
}

export function FilterRail({
  activeFilter,
  filters,
  onSelectFilter,
}: {
  activeFilter: AuditFilterKind;
  filters: AuditPageSnapshot["filters"];
  onSelectFilter?: (filter: AuditFilterKind) => void;
}) {
  return (
    <aside aria-label="Audit record filters" className={cx(styles.panel, styles.filterRail)}>
      <h2 className={styles.sectionTitle}>Record Filters</h2>
      <p className={styles.sectionHint}>Counts stay visible across scopes.</p>
      <div className={styles.filterList}>
        {filters.map((filter) => (
          <button
            aria-current={filter.kind === activeFilter}
            aria-pressed={filter.kind === activeFilter}
            className={styles.filterButton}
            disabled={!filter.enabled}
            key={filter.kind}
            onClick={() => onSelectFilter?.(filter.kind)}
            type="button"
          >
            <span>{auditFilterLabel(filter.kind, filter.label)}</span>
            <span className={styles.filterCount}>{filter.count}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}

export function Timeline({
  activeRecordId,
  onSelectRecord,
  records,
}: {
  activeRecordId: AuditRecordId | null;
  onSelectRecord?: (recordId: AuditRecordId) => void;
  records: AuditRecord[];
}) {
  return (
    <section
      aria-label="Audit records"
      aria-live="polite"
      className={cx(styles.panel, styles.timeline)}
    >
      <div className={styles.timelineHeader}>
        <div>
          <h2 className={styles.sectionTitle}>Evidence Timeline</h2>
          <p className={styles.sectionHint}>User-readable records from events and messages.</p>
        </div>
        <span className={styles.timelineMeta}>{records.length} records</span>
      </div>
      {records.length === 0 ? (
        <div className={styles.emptyList} role="status">
          <div>
            <strong>No audit records yet</strong>
            <p>Audit evidence will appear here as the session produces records.</p>
          </div>
        </div>
      ) : (
        <div className={styles.recordList}>
          {records.map((record) => (
            <button
              aria-label={`Audit record ${record.title}`}
              aria-current={record.id === activeRecordId}
              className={styles.recordCard}
              key={record.id}
              onClick={() => onSelectRecord?.(record.id)}
              type="button"
            >
              <div className={styles.recordTopLine}>
                <div className={styles.recordBadgeCluster}>
                  <span className={styles.badge}>{record.kind.replaceAll("_", " ")}</span>
                  <StatusBadge value={record.verdict ?? "not_available"} />
                </div>
                <span className={styles.recordTime}>{formatAuditTime(record.occurredAt)}</span>
              </div>
              <h3 className={styles.recordTitle}>{record.title}</h3>
              <p className={styles.recordSummary}>{record.summary}</p>
              <p className={styles.recordRefs}>
                {record.sourceLabel} · {auditFilterLabel(record.filterKind)} ·{" "}
                {record.actor}
              </p>
              <div className={styles.recordFooter}>
                <span>Confidence: {record.confidence}</span>
                <span>{record.evidenceRefs.length} evidence refs</span>
                <span>{record.completeness}</span>
              </div>
              <RecordFlags record={record} />
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

export function BoundaryBanner({
  boundary,
  onRetry,
}: {
  boundary: ApiUiBoundaryState;
  onRetry?: () => void;
}) {
  return (
    <section
      aria-live="polite"
      className={cx(styles.panel, styles.boundaryBanner)}
      role="status"
    >
      <div>
        <strong>{auditBoundaryLabel(boundary)}</strong>
        <p>{boundary.message}</p>
        {boundary.code !== undefined && <small>Code: {boundary.code}</small>}
      </div>
      <div className={styles.boundaryActions}>
        {boundary.shouldResync && <span className={styles.badge}>Resync suggested</span>}
        {boundary.retryable && <span className={styles.badge}>Retryable</span>}
        {boundary.retryable && onRetry !== undefined && (
          <Button onClick={onRetry} variant="secondary">
            {boundary.shouldResync ? "Refresh audit" : "Retry"}
          </Button>
        )}
      </div>
    </section>
  );
}

export function RecordFlags({ record }: { record: AuditRecord }) {
  const flags: string[] = [];
  if (record.flags.partial) {
    flags.push("Partial");
  }
  if (record.flags.hidden) {
    flags.push("Hidden");
  }
  if (record.flags.redacted) {
    flags.push("Redacted");
  }
  if (record.flags.stale) {
    flags.push("Stale");
  }

  if (flags.length === 0) {
    return null;
  }

  return (
    <div className={styles.recordFlags}>
      {flags.map((flag) => (
        <span className={styles.badge} key={flag}>
          {flag}
        </span>
      ))}
    </div>
  );
}

export function Boundary({
  action = null,
  message,
  title,
}: {
  action?: ReactNode;
  message: string;
  title: string;
}) {
  return (
    <section
      aria-live="polite"
      className={cx(styles.panel, styles.boundary)}
      role="status"
    >
      <div>
        <h1 className={styles.boundaryTitle}>{title}</h1>
        <p className={styles.boundaryMessage}>{message}</p>
        {action}
      </div>
    </section>
  );
}

export function StatusBadge({ value }: { value: AuditVerdict }) {
  const classKey = auditVerdictClassKey(value);
  return (
    <span
      className={cx(
        styles.badge,
        classKey === null ? null : verdictBadgeClassNames[classKey],
      )}
    >
      {auditVerdictLabel(value)}
    </span>
  );
}

function CompletenessBadge({ value }: { value: AuditCompleteness }) {
  return <span className={styles.badge}>{auditCompletenessLabel(value)}</span>;
}
