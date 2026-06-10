import { Button } from "../../shared/components";
import { mapAuditSnapshotToUiBoundary } from "../../shared/api/apiUiMapping";
import { useUiText } from "../../shared/ui-text";
import type {
  AuditFilterKind,
  AuditPageSnapshot,
  AuditRecordId,
  WorkspaceId,
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
  returnRoute?: string | null;
  selectedRecordId?: AuditRecordId | null;
  snapshot: AuditPageSnapshot | null;
  workspaceId?: WorkspaceId | null;
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
  returnRoute = null,
  selectedRecordId,
  snapshot,
  workspaceId,
}: AuditPageProps) {
  const uiText = useUiText();
  const activeFilter = activeAuditFilter(snapshot);
  const activeRecordId = activeAuditRecordId(snapshot, selectedRecordId);

  if (isLoading) {
    return (
      <AuditPageFrame returnRoute={returnRoute} snapshot={snapshot}>
        <Boundary
          title={uiText.common.status.loading}
          message={uiText.audit.messages.loadingAudit}
        />
      </AuditPageFrame>
    );
  }

  if (errorMessage !== null || snapshot === null) {
    return (
      <AuditPageFrame returnRoute={returnRoute} snapshot={snapshot}>
        <Boundary
          action={onRetry === undefined ? null : (
            <Button onClick={onRetry} variant="secondary">
              {uiText.common.actions.retry}
            </Button>
          )}
          message={errorMessage ?? uiText.audit.messages.snapshotUnavailable}
          title={uiText.audit.messages.unavailable}
        />
      </AuditPageFrame>
    );
  }

  const selectedRecord = resolveSelectedAuditRecord(snapshot, activeRecordId);
  const boundary = mapAuditSnapshotToUiBoundary(snapshot);
  const shouldHideContent =
    boundary.kind === "permission_denied" || !snapshot.permissions.canViewAudit;

  return (
    <AuditPageFrame returnRoute={returnRoute} snapshot={snapshot}>
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
          title={uiText.audit.messages.permissionLimited}
        />
      ) : (
        <main
          aria-label={uiText.audit.labels.auditEvidenceWorkspace}
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
          {selectedRecord === null ? (
            <Timeline
              activeRecordId={activeRecordId}
              onSelectRecord={onSelectRecord}
              records={snapshot.records}
            />
          ) : (
            <div className={styles.recordDetailGrid}>
              <Timeline
                activeRecordId={activeRecordId}
                onSelectRecord={onSelectRecord}
                records={snapshot.records}
              />
              <DetailPanel
                detailState={detailState}
                effectiveConfig={snapshot.effectiveConfig}
                onClose={onCloseDetail}
                record={selectedRecord}
                relatedLogs={snapshot.relatedLogs}
                workspaceId={workspaceId ?? snapshot.session.workspaceId ?? null}
              />
            </div>
          )}
        </main>
      )}
    </AuditPageFrame>
  );
}
