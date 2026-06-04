import { Button } from "../../shared/components";
import { mapAuditSnapshotToUiBoundary } from "../../shared/api/apiUiMapping";
import type {
  AuditFilterKind,
  AuditPageSnapshot,
  AuditRecordId,
} from "../../shared/api/types";
import { cx } from "../../shared/utils/cx";
import type { AuditPageRuntimeState } from "./auditRuntimeEvents";
import {
  DetailPanel,
  type AuditRecordDetailState,
} from "./AuditRecordDetailPanel";
import {
  activeAuditFilter,
  activeAuditRecordId,
  resolveSelectedAuditRecord,
} from "./auditPageSelection";
import styles from "./AuditPage.module.css";
import {
  AuditHeader,
  AuditPageFrame,
  Boundary,
  FilterRail,
  LiveStatusNotice,
  Overview,
  Timeline,
} from "./AuditPageSections";

export type { AuditRecordDetailState } from "./AuditRecordDetailPanel";

export type AuditPageProps = {
  detailState?: AuditRecordDetailState;
  errorMessage?: string | null;
  isLoading?: boolean;
  liveState?: AuditPageRuntimeState;
  onCloseDetail?: () => void;
  onRetry?: () => void;
  onSelectFilter?: (filter: AuditFilterKind) => void;
  onSelectRecord?: (recordId: AuditRecordId) => void;
  selectedRecordId?: AuditRecordId | null;
  snapshot: AuditPageSnapshot | null;
};

export function AuditPage({
  detailState = { errorMessage: null, isLoading: false },
  errorMessage = null,
  isLoading = false,
  liveState,
  onCloseDetail,
  onRetry,
  onSelectFilter,
  onSelectRecord,
  selectedRecordId,
  snapshot,
}: AuditPageProps) {
  const activeFilter = activeAuditFilter(snapshot);
  const activeRecordId = activeAuditRecordId(snapshot, selectedRecordId);

  if (isLoading) {
    return (
      <AuditPageFrame snapshot={snapshot}>
        <Boundary title="Loading audit" message="Reading audit records and evidence." />
      </AuditPageFrame>
    );
  }

  if (errorMessage !== null || snapshot === null) {
    return (
      <AuditPageFrame snapshot={snapshot}>
        <Boundary
          action={onRetry === undefined ? null : (
            <Button onClick={onRetry} variant="secondary">
              Retry
            </Button>
          )}
          message={errorMessage ?? "Audit snapshot is not available."}
          title="Audit unavailable"
        />
      </AuditPageFrame>
    );
  }

  const selectedRecord = resolveSelectedAuditRecord(snapshot, activeRecordId);
  const boundary = mapAuditSnapshotToUiBoundary(snapshot);
  const shouldHideContent =
    boundary.kind === "permission_denied" || !snapshot.permissions.canViewAudit;

  return (
    <AuditPageFrame snapshot={snapshot}>
      <AuditHeader boundary={boundary} snapshot={snapshot} />

      <LiveStatusNotice liveState={liveState} />

      <Overview
        boundary={boundary}
        onRetry={onRetry}
        snapshot={snapshot}
      />

      {shouldHideContent ? (
        <Boundary
          message={boundary.message}
          title="Permission limited"
        />
      ) : (
        <main
          aria-label="Audit evidence workspace"
          className={cx(
            styles.content,
            selectedRecord !== null && styles.contentWithDetail,
          )}
        >
          <FilterRail
            activeFilter={activeFilter}
            filters={snapshot.filters}
            onSelectFilter={onSelectFilter}
          />
          <Timeline
            activeRecordId={activeRecordId}
            onSelectRecord={onSelectRecord}
            records={snapshot.records}
          />
          {selectedRecord !== null && (
            <DetailPanel
              detailState={detailState}
              effectiveConfig={snapshot.effectiveConfig}
              onClose={onCloseDetail}
              record={selectedRecord}
              relatedLogs={snapshot.relatedLogs}
            />
          )}
        </main>
      )}
    </AuditPageFrame>
  );
}
