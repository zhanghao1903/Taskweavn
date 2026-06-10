import { useEffect, useId, useRef } from "react";

import { Button } from "../../shared/components";
import { navigateApp } from "../../app/navigation";
import { buildWorkspaceInspectionRoute } from "../../app/routes";
import type {
  AuditDisclosure,
  AuditRecordDetail,
  EffectiveConfigSummary,
  EvidenceDetail,
  RelatedLogsLink,
  SanitizedRawPayload,
  WorkspaceId,
} from "../../shared/api/types";
import { cx } from "../../shared/utils/cx";
import { useUiText } from "../../shared/ui-text";
import { formatAuditTime } from "./auditPageFormat";
import { auditRecordKindLabel, auditSourceLabel } from "./auditPageLabels";
import styles from "./AuditPage.module.css";
import { RecordFlags, StatusBadge } from "./AuditPageSections";

export type AuditRecordDetailState = {
  errorMessage?: string | null;
  evidenceDetail?: EvidenceDetail | null;
  evidenceErrorMessage?: string | null;
  evidenceIsLoading?: boolean;
  isLoading: boolean;
};

export function DetailPanel({
  detailState,
  effectiveConfig,
  onClose,
  record,
  relatedLogs,
  workspaceId,
}: {
  detailState: AuditRecordDetailState;
  effectiveConfig: EffectiveConfigSummary | null;
  onClose?: () => void;
  record: AuditRecordDetail;
  relatedLogs: RelatedLogsLink[];
  workspaceId?: WorkspaceId | null;
}) {
  const detailRef = useRef<HTMLElement>(null);
  const detailRegionLabelId = useId();
  const detailTitleId = useId();
  const uiText = useUiText();
  const disclosureNotes = detailDisclosureNotes(record, uiText);
  const evidenceDetail = detailState.evidenceDetail ?? null;
  const logLinks = record.relatedLogs.length > 0 ? record.relatedLogs : relatedLogs;

  useEffect(() => {
    detailRef.current?.focus({ preventScroll: true });
  }, [record.id]);

  return (
    <aside
      aria-describedby={detailTitleId}
      aria-labelledby={detailRegionLabelId}
      className={cx(styles.panel, styles.detail)}
      ref={detailRef}
      tabIndex={-1}
    >
      <span className={styles.srOnly} id={detailRegionLabelId}>
        {uiText.audit.detail.labels.auditRecordDetail}
      </span>
      <div className={styles.detailTopLine}>
        <StatusBadge value={record.verdict ?? "not_available"} />
        {onClose !== undefined && (
          <Button onClick={onClose} variant="secondary">
            {uiText.audit.detail.actions.backToList}
          </Button>
        )}
      </div>
      <h2 className={styles.detailTitle} id={detailTitleId}>
        {record.title}
      </h2>
      <p className={styles.detailBody}>{record.body}</p>
      {detailState.isLoading && (
        <p className={styles.detailState}>
          {uiText.audit.detail.messages.loadingCompleteRecordDetail}
        </p>
      )}
      {detailState.errorMessage !== null && detailState.errorMessage !== undefined && (
        <p className={cx(styles.detailState, styles.detailStateError)}>
          {uiText.audit.detail.messages.recordDetailLoadError({
            message: detailState.errorMessage,
          })}
        </p>
      )}
      <section className={styles.detailSection}>
        <h3 className={styles.detailSectionTitle}>
          {uiText.audit.detail.labels.whatHappened}
        </h3>
        <p className={styles.detailBody}>
          {uiText.audit.detail.messages.recordEventSummary({
            kind: auditRecordKindLabel(record.kind, uiText),
            source: auditSourceLabel(record.sourceLabel, uiText),
            time: formatAuditTime(record.occurredAt),
          })}
        </p>
      </section>
      <section className={styles.detailSection}>
        <h3 className={styles.detailSectionTitle}>
          {uiText.audit.detail.labels.whyItMatters}
        </h3>
        <p className={styles.detailBody}>{record.whyItMatters}</p>
      </section>
      <section className={styles.detailSection}>
        <h3 className={styles.detailSectionTitle}>
          {uiText.audit.labels.evidence}
        </h3>
        {detailState.evidenceIsLoading === true && (
          <p className={styles.detailState}>
            {uiText.audit.detail.messages.evidenceDetailLoading}
          </p>
        )}
        {detailState.evidenceErrorMessage !== null &&
          detailState.evidenceErrorMessage !== undefined && (
            <p className={cx(styles.detailState, styles.detailStateError)}>
              {uiText.audit.detail.messages.evidenceDetailLoadError({
                message: detailState.evidenceErrorMessage,
              })}
            </p>
          )}
        {record.evidence.length === 0 ? (
          <p className={styles.detailBody}>
            {uiText.audit.detail.messages.noEvidenceForRecord}
          </p>
        ) : (
          <ul className={styles.evidenceList}>
            {record.evidence.map((evidence) => (
              <li key={evidence.id}>
                {evidence.label}: {evidence.summary}
              </li>
            ))}
          </ul>
        )}
      </section>
      <WorkspaceEvidenceLinks record={record} workspaceId={workspaceId} />
      <section className={styles.detailSection}>
        <h3 className={styles.detailSectionTitle}>
          {uiText.audit.detail.labels.disclosure}
        </h3>
        <RecordFlags record={record} />
        <dl className={styles.disclosureList}>
          <div>
            <dt>{uiText.audit.detail.labels.rawPayload}</dt>
            <dd>
              {record.disclosure.rawPayloadAvailable
                ? uiText.audit.detail.messages.availableByPolicy
                : uiText.audit.detail.messages.hiddenByDefault}
            </dd>
          </div>
          <div>
            <dt>{uiText.audit.detail.labels.evidenceVisibility}</dt>
            <dd>
              {record.flags.hidden
                ? uiText.audit.detail.messages.limited
                : uiText.audit.detail.messages.visible}
            </dd>
          </div>
          {disclosureNotes.map((note) => (
            <div key={note.label}>
              <dt>{note.label}</dt>
              <dd>{note.value}</dd>
            </div>
          ))}
        </dl>
      </section>
      <SanitizedEvidenceSection
        evidenceDetail={evidenceDetail}
        record={record}
      />
      <section className={styles.detailSection}>
        <h3 className={styles.detailSectionTitle}>
          {uiText.audit.detail.labels.reservedLinks}
        </h3>
        <div className={styles.reservedGrid}>
          <div className={styles.reservedCard}>
            <strong>{uiText.audit.detail.labels.effectiveConfiguration}</strong>
            <span>
              {effectiveConfig === null
                ? uiText.audit.detail.messages.configurationSummaryUnavailable
                : `${effectiveConfig.profileLabel}: ${effectiveConfig.summary}`}
            </span>
          </div>
          <div className={styles.reservedCard}>
            <strong>{uiText.audit.detail.labels.relatedLogs}</strong>
            {logLinks.length === 0 ? (
              <span>{uiText.audit.detail.messages.noRelatedLogLink}</span>
            ) : (
              <ul className={styles.reservedList}>
                {logLinks.map((log) => (
                  <li key={`${log.label}-${log.href}`}>
                    <RelatedLogLink link={log} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>
    </aside>
  );
}

function WorkspaceEvidenceLinks({
  record,
  workspaceId,
}: {
  record: AuditRecordDetail;
  workspaceId?: WorkspaceId | null;
}) {
  const uiText = useUiText();

  if (!record.filePath) {
    return null;
  }

  const sessionId = sessionIdForRecord(record);
  const resolvedWorkspaceId = workspaceId ?? "current";
  const routeContext = {
    path: record.filePath,
    returnSessionId: sessionId ?? undefined,
    returnTaskNodeId: record.taskNodeId ?? undefined,
    sessionId: sessionId ?? undefined,
    taskNodeId: record.taskNodeId ?? undefined,
    workspaceId: resolvedWorkspaceId,
  };

  return (
    <section className={styles.detailSection}>
      <h3 className={styles.detailSectionTitle}>
        {uiText.audit.detail.labels.workspaceEvidence}
      </h3>
      <div className={styles.workspaceEvidenceActions}>
        <Button asChild size="sm" variant="ghost">
          <a
            href={buildWorkspaceInspectionRoute({
              ...routeContext,
              view: "file",
            })}
            onClick={(event) => {
              event.preventDefault();
              navigateApp(event.currentTarget.href.replace(globalThis.location.origin, ""));
            }}
          >
            {uiText.audit.detail.actions.openFile}
          </a>
        </Button>
        <Button asChild size="sm" variant="ghost">
          <a
            href={buildWorkspaceInspectionRoute({
              ...routeContext,
              view: "diff",
            })}
            onClick={(event) => {
              event.preventDefault();
              navigateApp(event.currentTarget.href.replace(globalThis.location.origin, ""));
            }}
          >
            {uiText.audit.detail.actions.viewDiff}
          </a>
        </Button>
      </div>
    </section>
  );
}

function sessionIdForRecord(record: AuditRecordDetail): string | null {
  switch (record.scope.kind) {
    case "action":
    case "confirmation":
    case "file":
    case "log_evidence":
    case "result":
    case "session":
    case "task":
      return record.scope.sessionId;
    case "config":
      return record.scope.sessionId ?? null;
    case "workflow":
      return null;
  }
}

function RelatedLogLink({ link }: { link: RelatedLogsLink }) {
  if (!link.enabled) {
    return (
      <>
        <span>{link.label}</span>
        {link.disabledReason !== undefined && (
          <span> · {link.disabledReason}</span>
        )}
      </>
    );
  }

  return (
    <Button
      asChild
      size="sm"
      variant="ghost"
    >
      <a
        href={link.href}
        onClick={(event) => {
          event.preventDefault();
          navigateApp(link.href);
        }}
      >
        {link.label}
      </a>
    </Button>
  );
}

function SanitizedEvidenceSection({
  evidenceDetail,
  record,
}: {
  evidenceDetail: EvidenceDetail | null;
  record: AuditRecordDetail;
}) {
  const uiText = useUiText();
  const hasRecordPayload = record.rawPayload !== null;
  const hasEvidencePayload =
    evidenceDetail?.sanitizedPayload !== null &&
    evidenceDetail?.sanitizedPayload !== undefined;
  const hasRecordHiddenReason =
    record.disclosure.hiddenReason !== null &&
    record.disclosure.hiddenReason !== undefined;
  const hasEvidenceHiddenReason =
    evidenceDetail?.disclosure.hiddenReason !== null &&
    evidenceDetail?.disclosure.hiddenReason !== undefined;
  const hasDisclosure =
    hasRecordPayload ||
    hasEvidencePayload ||
    record.disclosure.rawPayloadAvailable ||
    evidenceDetail?.disclosure.rawPayloadAvailable === true ||
    hasRecordHiddenReason ||
    hasEvidenceHiddenReason;

  return (
    <section className={styles.detailSection}>
      <h3 className={styles.detailSectionTitle}>
        {uiText.audit.detail.labels.sanitizedEvidence}
      </h3>
      {!hasDisclosure ? (
        <p className={styles.detailBody}>
          {uiText.audit.detail.messages.noSanitizedPayloadForRecord}
        </p>
      ) : (
        <div className={styles.sanitizedEvidenceStack}>
          <DisclosureCard
            disclosure={record.disclosure}
            payload={record.rawPayload}
            title={uiText.audit.detail.labels.recordPayload}
          />
          {record.rawPayload !== null && (
            <SanitizedPayloadBlock
              payload={record.rawPayload}
              title={uiText.audit.detail.labels.sanitizedRecordPayload}
            />
          )}
          {evidenceDetail !== null && (
            <DisclosureCard
              disclosure={evidenceDetail.disclosure}
              payload={evidenceDetail.sanitizedPayload}
              title={uiText.audit.detail.messages.evidencePayloadTitle({
                label: evidenceDetail.label,
              })}
            />
          )}
          {evidenceDetail?.sanitizedPayload !== null &&
            evidenceDetail?.sanitizedPayload !== undefined && (
              <SanitizedPayloadBlock
                payload={evidenceDetail.sanitizedPayload}
                title={uiText.audit.detail.labels.sanitizedEvidencePayload}
              />
            )}
        </div>
      )}
    </section>
  );
}

function DisclosureCard({
  disclosure,
  payload,
  title,
}: {
  disclosure: AuditDisclosure;
  payload: SanitizedRawPayload | null;
  title: string;
}) {
  const uiText = useUiText();
  const notes = disclosureNotes(disclosure, uiText);

  return (
    <div className={styles.disclosureCard}>
      <div>
        <strong>{title}</strong>
        <span>{disclosureStatusLabel(disclosure, payload, uiText)}</span>
      </div>
      {notes.length > 0 && (
        <dl className={styles.disclosureMiniList}>
          {notes.map((note) => (
            <div key={note.label}>
              <dt>{note.label}</dt>
              <dd>{note.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

function SanitizedPayloadBlock({
  payload,
  title,
}: {
  payload: SanitizedRawPayload;
  title: string;
}) {
  return (
    <div className={styles.payloadBlock}>
      <div className={styles.payloadHeader}>
        <strong>{title}</strong>
        <span>{payload.format}</span>
      </div>
      <pre className={styles.payloadPre}>{payload.content}</pre>
      {payload.redactions.length > 0 && (
        <div className={styles.redactionList} aria-label={`${title} redactions`}>
          {payload.redactions.map((redaction) => (
            <span className={styles.badge} key={redaction}>
              {redaction}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function disclosureNotes(
  disclosure: AuditDisclosure,
  uiText: ReturnType<typeof useUiText>,
): Array<{ label: string; value: string }> {
  const notes: Array<{ label: string; value: string }> = [];
  if (disclosure.hiddenReason !== null && disclosure.hiddenReason !== undefined) {
    notes.push({
      label: uiText.audit.detail.labels.hiddenReason,
      value: disclosure.hiddenReason,
    });
  }
  if (disclosure.partialReason !== null && disclosure.partialReason !== undefined) {
    notes.push({
      label: uiText.audit.detail.labels.partialReason,
      value: disclosure.partialReason,
    });
  }
  if (disclosure.redactionReason !== null && disclosure.redactionReason !== undefined) {
    notes.push({
      label: uiText.audit.detail.labels.redactionReason,
      value: disclosure.redactionReason,
    });
  }
  if (disclosure.permissionReason !== null && disclosure.permissionReason !== undefined) {
    notes.push({
      label: uiText.audit.detail.labels.permissionReason,
      value: disclosure.permissionReason,
    });
  }
  return notes;
}

function disclosureStatusLabel(
  disclosure: AuditDisclosure,
  payload: SanitizedRawPayload | null,
  uiText: ReturnType<typeof useUiText>,
): string {
  if (payload !== null && disclosure.rawPayloadShown) {
    return uiText.audit.detail.messages.sanitizedPayloadShown;
  }
  if (disclosure.hiddenReason !== null && disclosure.hiddenReason !== undefined) {
    return uiText.audit.detail.messages.hiddenByPolicy;
  }
  if (disclosure.permissionReason !== null && disclosure.permissionReason !== undefined) {
    return uiText.audit.detail.messages.hiddenByPermission;
  }
  if (disclosure.rawPayloadAvailable) {
    return uiText.audit.detail.messages.payloadAvailableNotShown;
  }
  return uiText.audit.detail.messages.noPayloadAvailable;
}

function detailDisclosureNotes(
  record: AuditRecordDetail,
  uiText: ReturnType<typeof useUiText>,
): Array<{ label: string; value: string }> {
  return disclosureNotes(record.disclosure, uiText);
}
