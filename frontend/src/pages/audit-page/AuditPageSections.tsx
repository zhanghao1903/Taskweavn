import { useLayoutEffect, useRef, type ReactNode } from "react";

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
import { useUiText } from "../../shared/ui-text";
import { PlatoProductMark } from "../main-page/PlatoProductMark";
import type { AuditPageRuntimeState } from "./auditRuntimeEvents";
import { formatAuditTime } from "./auditPageFormat";
import {
  auditBoundaryLabel,
  auditCompletenessLabel,
  auditConfidenceLabel,
  auditFilterLabel,
  auditLiveStatusCopy,
  auditOverviewMetricFilterItems,
  auditActorLabel,
  auditFlagLabel,
  auditRecordKindLabel,
  auditScopeLabel,
  auditScopeStatusText,
  auditSourceLabel,
  auditSubjectLabel,
  auditWorkflowLabel,
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
  returnRoute,
  snapshot,
}: {
  children: ReactNode;
  returnRoute?: string | null;
  snapshot: AuditPageSnapshot | null;
}) {
  return (
    <div className={styles.page}>
      <AuditPageChrome returnRoute={returnRoute} snapshot={snapshot} />
      <div className={styles.shell}>{children}</div>
    </div>
  );
}

function AuditPageChrome({
  returnRoute,
  snapshot,
}: {
  returnRoute?: string | null;
  snapshot: AuditPageSnapshot | null;
}) {
  const uiText = useUiText();
  const resolvedReturnRoute = returnRoute ?? snapshot?.entryContext.sourceRoute ?? null;

  return (
    <div className={styles.topBar}>
      <div className={styles.brandBlock}>
        <PlatoProductMark className={styles.brandMark} />
        <div className={styles.brandCopy}>
          <span className={styles.brandName}>Plato</span>
          <span className={styles.brandSubtitle}>
            {uiText.audit.labels.productSubtitle}
          </span>
        </div>
      </div>
      <div className={styles.topBarContextBlock}>
        <span className={styles.topBarLabel}>{uiText.audit.labels.project}</span>
        <span className={styles.topBarValue}>
          {snapshot?.project?.name ?? uiText.audit.labels.project}
        </span>
      </div>
      <span className={styles.workflowPill}>
        {auditWorkflowLabel(snapshot?.workflow?.name, uiText)}
      </span>
      <div className={styles.sessionContextBlock}>
        <span className={styles.sessionValue}>
          {uiText.audit.labels.sessionName({
            name: snapshot?.session.name ?? uiText.audit.labels.audit,
          })}
        </span>
      </div>
      <div className={styles.topBarActions}>
        <span className={styles.badge}>{uiText.audit.labels.readOnly}</span>
        <span className={styles.badge}>{uiText.audit.labels.trustPlane}</span>
        <Button
          disabled={resolvedReturnRoute === null}
          onClick={() => {
            if (resolvedReturnRoute !== null) {
              navigateApp(resolvedReturnRoute);
            }
          }}
          variant="secondary"
        >
          {uiText.audit.actions.return}
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
  const uiText = useUiText();

  return (
    <header className={styles.header}>
      <div className={styles.headerSubjectCluster}>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>{uiText.audit.labels.audit}</h1>
          <span className={styles.badge}>
            {auditScopeLabel(snapshot, uiText)}
          </span>
        </div>
        <div className={styles.headerSubjectMeta}>
          <p className={styles.subject}>{auditSubjectLabel(snapshot)}</p>
          <p className={styles.status}>
            {auditScopeStatusText(snapshot, uiText)} ·{" "}
            {uiText.audit.labels.filter}:{" "}
            {auditFilterLabel(snapshot.request.filter, undefined, uiText)}
          </p>
        </div>
      </div>
      <div className={styles.headerStatus}>
        <span className={styles.badge}>{auditBoundaryLabel(boundary, uiText)}</span>
        <span className={styles.badge}>{uiText.audit.labels.noMutations}</span>
      </div>
      <p className={styles.note}>
        {uiText.audit.messages.readOnlyTrustPlane}
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
  const uiText = useUiText();
  const shouldShowBoundaryNotice = boundary.kind !== "ready";
  const shouldShowVerdictNotice =
    snapshot.overview.verdict !== "passed" &&
    snapshot.overview.verdict !== "not_available";

  return (
    <section
      aria-label={uiText.audit.labels.auditOverview}
      className={cx(styles.panel, styles.overview)}
    >
      <div className={styles.overviewPrimary}>
        <div className={styles.overviewHeadingRow}>
          <h2 className={styles.overviewTitle}>
            {uiText.audit.labels.auditOverview}
          </h2>
          <div className={styles.overviewBadgeCluster}>
            <StatusBadge value={snapshot.overview.verdict} />
            <CompletenessBadge value={snapshot.overview.completeness} />
          </div>
        </div>
        <p className={styles.overviewCopy}>{snapshot.overview.summary}</p>
        {snapshot.overview.keyIssue !== null && (
          <p className={styles.overviewIssue}>
            {uiText.audit.labels.keyIssue}: {snapshot.overview.keyIssue}
          </p>
        )}
        {(shouldShowBoundaryNotice || shouldShowVerdictNotice) && (
          <div className={styles.overviewNoticeStack}>
            {shouldShowBoundaryNotice && (
              <div className={styles.overviewNotice} role="status">
                <div className={styles.overviewNoticeMain}>
                  <strong>{auditBoundaryLabel(boundary, uiText)}</strong>
                  <span>{boundary.message}</span>
                  {boundary.code !== undefined && (
                    <span className={styles.overviewNoticeCode}>
                      {uiText.audit.labels.code}: {boundary.code}
                    </span>
                  )}
                </div>
                <div className={styles.overviewNoticeActions}>
                  {boundary.shouldResync && (
                    <span className={styles.badge}>
                      {uiText.audit.labels.resyncSuggested}
                    </span>
                  )}
                  {boundary.retryable && (
                    <span className={styles.badge}>
                      {uiText.audit.labels.retryable}
                    </span>
                  )}
                  {boundary.retryable && onRetry !== undefined && (
                    <Button onClick={onRetry} variant="secondary">
                      {boundary.shouldResync
                        ? uiText.audit.actions.refreshAudit
                        : uiText.common.actions.retry}
                    </Button>
                  )}
                </div>
              </div>
            )}
            {shouldShowVerdictNotice && (
              <div className={styles.overviewNotice} role="note">
                <StatusBadge value={snapshot.overview.verdict} />
                <div className={styles.overviewNoticeMain}>
                  <strong>
                    {auditVerdictNoticeTitle(snapshot.overview.verdict, uiText)}
                  </strong>
                  <span>{snapshot.overview.keyIssue ?? snapshot.overview.summary}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      <div className={styles.overviewMetrics}>
        {auditOverviewMetricFilterItems(uiText).map((item) => (
          <div className={styles.metric} key={item.filter}>
            <span className={styles.metricLabel}>{item.label}</span>
            <strong className={styles.metricValue}>
              {snapshot.overview.recordCounts[item.filter] ?? 0}
            </strong>
            <span className={styles.metricNote}>
              {uiText.audit.labels.visibleRecords}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function VerdictNotice({ snapshot }: { snapshot: AuditPageSnapshot }) {
  const uiText = useUiText();

  if (
    snapshot.overview.verdict === "passed" ||
    snapshot.overview.verdict === "not_available"
  ) {
    return null;
  }

  return (
    <section
      aria-label={uiText.audit.labels.auditVerdictNotice}
      className={cx(styles.panel, styles.verdictNotice)}
      role="note"
    >
      <StatusBadge value={snapshot.overview.verdict} />
      <div>
        <strong>{auditVerdictNoticeTitle(snapshot.overview.verdict, uiText)}</strong>
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
  const uiText = useUiText();

  if (
    liveState === undefined ||
    liveState.status === "connected" ||
    liveState.status === "refreshing"
  ) {
    return null;
  }

  const copy = auditLiveStatusCopy(liveState, uiText);

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
          {uiText.audit.labels.cursor}: {liveState.eventCursor}
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
  const uiText = useUiText();

  return (
    <aside
      aria-label={uiText.audit.labels.auditRecordFilters}
      className={cx(styles.panel, styles.filterRail)}
    >
      <h2 className={styles.sectionTitle}>{uiText.audit.labels.recordFilters}</h2>
      <p className={styles.sectionHint}>{uiText.audit.labels.filterCountsHelp}</p>
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
            <span>{auditFilterLabel(filter.kind, filter.label, uiText)}</span>
            <span className={styles.filterCount}>{filter.count}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}

export function Timeline({
  activeRecordId,
  onScrollPositionChange,
  onSelectRecord,
  records,
  restoreScrollTop,
}: {
  activeRecordId: AuditRecordId | null;
  onScrollPositionChange?: (scrollTop: number) => void;
  onSelectRecord?: (recordId: AuditRecordId) => void;
  records: AuditRecord[];
  restoreScrollTop?: number;
}) {
  const timelineRef = useRef<HTMLElement>(null);
  const uiText = useUiText();

  useLayoutEffect(() => {
    const timeline = timelineRef.current;
    if (timeline === null || restoreScrollTop === undefined) {
      return;
    }

    timeline.scrollTop = restoreScrollTop;
  }, [activeRecordId, records.length, restoreScrollTop]);

  const handleSelectRecord = (recordId: AuditRecordId) => {
    onScrollPositionChange?.(timelineRef.current?.scrollTop ?? 0);
    onSelectRecord?.(recordId);
  };

  return (
    <section
      aria-label={uiText.audit.labels.auditRecords}
      aria-live="polite"
      className={cx(styles.panel, styles.timeline)}
      ref={timelineRef}
    >
      <div className={styles.timelineHeader}>
        <div>
          <h2 className={styles.sectionTitle}>
            {uiText.audit.labels.evidenceTimeline}
          </h2>
          <p className={styles.sectionHint}>
            {uiText.audit.messages.evidenceTimelineHelp}
          </p>
        </div>
        <span className={styles.timelineMeta}>
          {uiText.audit.labels.recordCount({ count: records.length })}
        </span>
      </div>
      {records.length === 0 ? (
        <div className={styles.emptyList} role="status">
          <div>
            <strong>{uiText.audit.messages.auditRecordEmptyTitle}</strong>
            <p>{uiText.audit.messages.auditRecordEmptyBody}</p>
          </div>
        </div>
      ) : (
        <div className={styles.recordList}>
          {records.map((record) => (
            <button
              aria-label={`${uiText.audit.labels.audit} record ${record.title}`}
              aria-current={record.id === activeRecordId}
              className={styles.recordCard}
              key={record.id}
              onClick={() => handleSelectRecord(record.id)}
              type="button"
            >
              <div className={styles.recordTopLine}>
                <div className={styles.recordBadgeCluster}>
                  <span className={styles.badge}>
                    {auditRecordKindLabel(record.kind, uiText)}
                  </span>
                  <StatusBadge value={record.verdict ?? "not_available"} />
                </div>
                <span className={styles.recordTime}>{formatAuditTime(record.occurredAt)}</span>
              </div>
              <h3 className={styles.recordTitle}>{record.title}</h3>
              <p className={styles.recordSummary}>{record.summary}</p>
              <p className={styles.recordRefs}>
                {auditSourceLabel(record.sourceLabel, uiText)} ·{" "}
                {auditFilterLabel(record.filterKind, undefined, uiText)} ·{" "}
                {auditActorLabel(record.actor, uiText)}
              </p>
              <div className={styles.recordFooter}>
                <span>
                  {uiText.audit.labels.confidence({
                    value: auditConfidenceLabel(record.confidence, uiText),
                  })}
                </span>
                <span>
                  {uiText.audit.labels.evidenceRefCount({
                    count: record.evidenceRefs.length,
                  })}
                </span>
                <span>{auditCompletenessLabel(record.completeness, uiText)}</span>
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
  const uiText = useUiText();

  return (
    <section
      aria-live="polite"
      className={cx(styles.panel, styles.boundaryBanner)}
      role="status"
    >
      <div>
        <strong>{auditBoundaryLabel(boundary, uiText)}</strong>
        <p>{boundary.message}</p>
        {boundary.code !== undefined && (
          <small>
            {uiText.audit.labels.code}: {boundary.code}
          </small>
        )}
      </div>
      <div className={styles.boundaryActions}>
        {boundary.shouldResync && (
          <span className={styles.badge}>
            {uiText.audit.labels.resyncSuggested}
          </span>
        )}
        {boundary.retryable && (
          <span className={styles.badge}>{uiText.audit.labels.retryable}</span>
        )}
        {boundary.retryable && onRetry !== undefined && (
          <Button onClick={onRetry} variant="secondary">
            {boundary.shouldResync
              ? uiText.audit.actions.refreshAudit
              : uiText.common.actions.retry}
          </Button>
        )}
      </div>
    </section>
  );
}

export function RecordFlags({ record }: { record: AuditRecord }) {
  const uiText = useUiText();
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
          {auditFlagLabel(flag.toLowerCase(), uiText)}
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
  const uiText = useUiText();
  const classKey = auditVerdictClassKey(value);
  return (
    <span
      className={cx(
        styles.badge,
        classKey === null ? null : verdictBadgeClassNames[classKey],
      )}
    >
      {auditVerdictLabel(value, uiText)}
    </span>
  );
}

function CompletenessBadge({ value }: { value: AuditCompleteness }) {
  const uiText = useUiText();
  return (
    <span className={styles.badge}>
      {auditCompletenessLabel(value, uiText)}
    </span>
  );
}
