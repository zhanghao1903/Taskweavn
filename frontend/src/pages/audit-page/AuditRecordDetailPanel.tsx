import { useEffect, useId, useRef } from "react";

import { Button } from "../../shared/components";
import type {
  AuditDisclosure,
  AuditRecordDetail,
  EffectiveConfigSummary,
  EvidenceDetail,
  RelatedLogsLink,
  SanitizedRawPayload,
} from "../../shared/api/types";
import { cx } from "../../shared/utils/cx";
import { formatAuditTime } from "./auditPageFormat";
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
}: {
  detailState: AuditRecordDetailState;
  effectiveConfig: EffectiveConfigSummary | null;
  onClose?: () => void;
  record: AuditRecordDetail;
  relatedLogs: RelatedLogsLink[];
}) {
  const detailRef = useRef<HTMLElement>(null);
  const detailRegionLabelId = useId();
  const detailTitleId = useId();
  const disclosureNotes = detailDisclosureNotes(record);
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
        Audit record detail
      </span>
      <div className={styles.detailTopLine}>
        <StatusBadge value={record.verdict ?? "not_available"} />
        {onClose !== undefined && (
          <Button onClick={onClose} variant="secondary">
            Back to list
          </Button>
        )}
      </div>
      <h2 className={styles.detailTitle} id={detailTitleId}>
        {record.title}
      </h2>
      <p className={styles.detailBody}>{record.body}</p>
      {detailState.isLoading && (
        <p className={styles.detailState}>Loading complete record detail.</p>
      )}
      {detailState.errorMessage !== null && detailState.errorMessage !== undefined && (
        <p className={cx(styles.detailState, styles.detailStateError)}>
          Record detail could not be loaded: {detailState.errorMessage}
        </p>
      )}
      <section className={styles.detailSection}>
        <h3 className={styles.detailSectionTitle}>What happened</h3>
        <p className={styles.detailBody}>
          {record.sourceLabel} recorded a {record.kind.replaceAll("_", " ")} event
          at {formatAuditTime(record.occurredAt)}.
        </p>
      </section>
      <section className={styles.detailSection}>
        <h3 className={styles.detailSectionTitle}>Why it matters</h3>
        <p className={styles.detailBody}>{record.whyItMatters}</p>
      </section>
      <section className={styles.detailSection}>
        <h3 className={styles.detailSectionTitle}>Evidence</h3>
        {detailState.evidenceIsLoading === true && (
          <p className={styles.detailState}>Loading evidence detail.</p>
        )}
        {detailState.evidenceErrorMessage !== null &&
          detailState.evidenceErrorMessage !== undefined && (
            <p className={cx(styles.detailState, styles.detailStateError)}>
              Evidence detail could not be loaded: {detailState.evidenceErrorMessage}
            </p>
          )}
        {record.evidence.length === 0 ? (
          <p className={styles.detailBody}>No evidence is available for this record.</p>
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
      <section className={styles.detailSection}>
        <h3 className={styles.detailSectionTitle}>Disclosure</h3>
        <RecordFlags record={record} />
        <dl className={styles.disclosureList}>
          <div>
            <dt>Raw payload</dt>
            <dd>
              {record.disclosure.rawPayloadAvailable
                ? "Available by policy"
                : "Hidden by default"}
            </dd>
          </div>
          <div>
            <dt>Evidence visibility</dt>
            <dd>{record.flags.hidden ? "Limited" : "Visible"}</dd>
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
        <h3 className={styles.detailSectionTitle}>Reserved links</h3>
        <div className={styles.reservedGrid}>
          <div className={styles.reservedCard}>
            <strong>Effective configuration</strong>
            <span>
              {effectiveConfig === null
                ? "Configuration summary is not available."
                : `${effectiveConfig.profileLabel}: ${effectiveConfig.summary}`}
            </span>
          </div>
          <div className={styles.reservedCard}>
            <strong>Related logs</strong>
            {logLinks.length === 0 ? (
              <span>No related log link is available yet.</span>
            ) : (
              <ul className={styles.reservedList}>
                {logLinks.map((log) => (
                  <li key={`${log.label}-${log.href}`}>
                    {log.label}
                    {!log.enabled && log.disabledReason !== undefined && (
                      <span> · {log.disabledReason}</span>
                    )}
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

function SanitizedEvidenceSection({
  evidenceDetail,
  record,
}: {
  evidenceDetail: EvidenceDetail | null;
  record: AuditRecordDetail;
}) {
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
      <h3 className={styles.detailSectionTitle}>Sanitized evidence</h3>
      {!hasDisclosure ? (
        <p className={styles.detailBody}>
          No sanitized payload is available for this record.
        </p>
      ) : (
        <div className={styles.sanitizedEvidenceStack}>
          <DisclosureCard
            disclosure={record.disclosure}
            payload={record.rawPayload}
            title="Record payload"
          />
          {record.rawPayload !== null && (
            <SanitizedPayloadBlock
              payload={record.rawPayload}
              title="Sanitized record payload"
            />
          )}
          {evidenceDetail !== null && (
            <DisclosureCard
              disclosure={evidenceDetail.disclosure}
              payload={evidenceDetail.sanitizedPayload}
              title={`Evidence payload · ${evidenceDetail.label}`}
            />
          )}
          {evidenceDetail?.sanitizedPayload !== null &&
            evidenceDetail?.sanitizedPayload !== undefined && (
              <SanitizedPayloadBlock
                payload={evidenceDetail.sanitizedPayload}
                title="Sanitized evidence payload"
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
  const notes = disclosureNotes(disclosure);

  return (
    <div className={styles.disclosureCard}>
      <div>
        <strong>{title}</strong>
        <span>{disclosureStatusLabel(disclosure, payload)}</span>
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
): Array<{ label: string; value: string }> {
  const notes: Array<{ label: string; value: string }> = [];
  if (disclosure.hiddenReason !== null && disclosure.hiddenReason !== undefined) {
    notes.push({ label: "Hidden reason", value: disclosure.hiddenReason });
  }
  if (disclosure.partialReason !== null && disclosure.partialReason !== undefined) {
    notes.push({ label: "Partial reason", value: disclosure.partialReason });
  }
  if (disclosure.redactionReason !== null && disclosure.redactionReason !== undefined) {
    notes.push({ label: "Redaction reason", value: disclosure.redactionReason });
  }
  if (disclosure.permissionReason !== null && disclosure.permissionReason !== undefined) {
    notes.push({ label: "Permission reason", value: disclosure.permissionReason });
  }
  return notes;
}

function disclosureStatusLabel(
  disclosure: AuditDisclosure,
  payload: SanitizedRawPayload | null,
): string {
  if (payload !== null && disclosure.rawPayloadShown) {
    return "Sanitized payload shown";
  }
  if (disclosure.hiddenReason !== null && disclosure.hiddenReason !== undefined) {
    return "Hidden by policy";
  }
  if (disclosure.permissionReason !== null && disclosure.permissionReason !== undefined) {
    return "Hidden by permission";
  }
  if (disclosure.rawPayloadAvailable) {
    return "Payload available, not shown";
  }
  return "No payload available";
}

function detailDisclosureNotes(
  record: AuditRecordDetail,
): Array<{ label: string; value: string }> {
  return disclosureNotes(record.disclosure);
}
