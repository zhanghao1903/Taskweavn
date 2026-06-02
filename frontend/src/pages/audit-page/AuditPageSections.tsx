import type { ReactNode } from "react";

import { Button } from "../../shared/components";
import type { ApiUiBoundaryState } from "../../shared/api/apiUiMapping";
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
import styles from "./AuditPage.module.css";

const filterLabels: Record<AuditFilterKind, string> = {
  actions: "Actions",
  all: "All records",
  config: "Config",
  confirmations: "Confirmations",
  files: "Files",
  logs: "Logs",
  results: "Results",
  risks: "Risks",
  system: "System",
};

const metricFilters: Array<{ filter: AuditFilterKind; label: string }> = [
  { filter: "confirmations", label: "Confirmations" },
  { filter: "risks", label: "Risks" },
  { filter: "files", label: "Files" },
  { filter: "results", label: "Results" },
];

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
              globalThis.history.pushState(null, "", snapshot.entryContext.sourceRoute);
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
      <div>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>Audit</h1>
          <span className={styles.badge}>{scopeLabel(snapshot)}</span>
        </div>
        <p className={styles.subject}>{subjectLabel(snapshot)}</p>
        <p className={styles.status}>
          {scopeStatusText(snapshot)} · Filter: {filterLabels[snapshot.request.filter]}
        </p>
      </div>
      <div className={styles.headerStatus}>
        <span className={styles.badge}>{boundaryLabel(boundary)}</span>
        <span className={styles.badge}>No mutations</span>
      </div>
      <p className={styles.note}>
        Audit is a read-only trust plane. It explains what happened without
        changing the Task or session.
      </p>
    </header>
  );
}

export function Overview({ snapshot }: { snapshot: AuditPageSnapshot }) {
  return (
    <section aria-label="Audit overview" className={cx(styles.panel, styles.overview)}>
      <div>
        <h2 className={styles.overviewTitle}>Audit Overview</h2>
        <p className={styles.overviewCopy}>{snapshot.overview.summary}</p>
        <p className={styles.overviewCopy}>
          <StatusBadge value={snapshot.overview.verdict} />{" "}
          <CompletenessBadge value={snapshot.overview.completeness} />
        </p>
        {snapshot.overview.keyIssue !== null && (
          <p className={styles.overviewIssue}>
            Key issue: {snapshot.overview.keyIssue}
          </p>
        )}
      </div>
      {metricFilters.map((item) => (
        <div className={styles.metric} key={item.filter}>
          <span className={styles.metricLabel}>{item.label}</span>
          <strong className={styles.metricValue}>
            {snapshot.overview.recordCounts[item.filter] ?? 0}
          </strong>
          <span className={styles.metricNote}>visible records</span>
        </div>
      ))}
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
        <strong>{verdictNoticeTitle(snapshot.overview.verdict)}</strong>
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
  if (liveState === undefined || liveState.status === "connected") {
    return null;
  }

  const copy = liveStatusCopy(liveState);

  return (
    <section
      aria-live="polite"
      className={cx(
        styles.panel,
        styles.liveStatus,
        liveState.status === "refreshing" && styles.liveStatusRefreshing,
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

function liveStatusCopy(
  liveState: AuditPageRuntimeState,
): { message: string; title: string } {
  switch (liveState.status) {
    case "refreshing":
      return {
        message:
          liveState.message ?? "Live audit stream is applying new records.",
        title: "Updating audit evidence",
      };
    case "stale":
      return {
        message:
          liveState.message ??
          "Refreshing from source; current evidence remains readable.",
        title: "Audit snapshot may be stale",
      };
    case "disconnected":
      return {
        message:
          liveState.message ??
          "Manual refresh still works; this page may not update automatically.",
        title: "Live audit updates unavailable",
      };
    case "connected":
      return {
        message: "",
        title: "",
      };
  }
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
            <span>{filterLabels[filter.kind] ?? filter.label}</span>
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
                {record.sourceLabel} · {filterLabels[record.filterKind]} ·{" "}
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
        <strong>{boundaryLabel(boundary)}</strong>
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
  return <span className={cx(styles.badge, verdictClass(value))}>{verdictLabel(value)}</span>;
}

function CompletenessBadge({ value }: { value: AuditCompleteness }) {
  return <span className={styles.badge}>{completenessLabel(value)}</span>;
}

function scopeLabel(snapshot: AuditPageSnapshot): string {
  if (snapshot.scope.kind === "task") {
    return "Scope: Task";
  }

  if (snapshot.scope.kind === "session") {
    return "Scope: Session";
  }

  return `Scope: ${snapshot.scope.kind}`;
}

function subjectLabel(snapshot: AuditPageSnapshot): string {
  return snapshot.selectedTask?.title ?? snapshot.session.name;
}

function scopeStatusText(snapshot: AuditPageSnapshot): string {
  if (snapshot.scope.kind === "task") {
    return `Task audit · ${snapshot.session.status}`;
  }

  if (snapshot.scope.kind === "session") {
    return `Session audit · ${snapshot.session.status}`;
  }

  return `${snapshot.scope.kind} audit · ${snapshot.session.status}`;
}

function boundaryLabel(boundary: ApiUiBoundaryState): string {
  switch (boundary.kind) {
    case "backend_busy":
      return "Backend busy";
    case "empty":
      return "Empty";
    case "fatal_error":
      return "Fatal error";
    case "hidden_evidence":
      return "Hidden evidence";
    case "loading":
      return "Loading";
    case "partial":
      return "Partial evidence";
    case "permission_denied":
      return "Permission denied";
    case "ready":
      return "Ready";
    case "recoverable_error":
      return "Recoverable error";
    case "stale_resync":
      return "Stale snapshot";
  }
}

function verdictNoticeTitle(value: AuditVerdict): string {
  switch (value) {
    case "failed":
      return "Audit found a blocking issue.";
    case "inconclusive":
      return "Audit cannot establish confidence yet.";
    case "warning":
      return "Audit found a non-blocking concern.";
    case "not_available":
    case "passed":
      return "";
  }
}

function verdictClass(value: AuditVerdict): string | null {
  switch (value) {
    case "failed":
      return styles.badgeFailed;
    case "inconclusive":
      return styles.badgeInconclusive;
    case "passed":
      return styles.badgePassed;
    case "warning":
      return styles.badgeWarning;
    case "not_available":
      return null;
  }
}

function verdictLabel(value: AuditVerdict): string {
  switch (value) {
    case "failed":
      return "Verdict: Failed";
    case "inconclusive":
      return "Verdict: Inconclusive";
    case "not_available":
      return "Verdict: Not available";
    case "passed":
      return "Verdict: Passed";
    case "warning":
      return "Verdict: Warning";
  }
}

function completenessLabel(value: AuditCompleteness): string {
  switch (value) {
    case "complete":
      return "Complete";
    case "failed":
      return "Failed";
    case "hidden":
      return "Hidden";
    case "not_started":
      return "Not started";
    case "partial":
      return "Partial";
    case "running":
      return "Running";
  }
}
