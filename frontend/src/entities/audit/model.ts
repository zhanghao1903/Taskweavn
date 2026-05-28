import type {
  AuditCompleteness,
  AuditEntryContext,
  AuditFilterKind,
  AuditPageSnapshot,
  AuditRecord,
  AuditRecordDetail,
  AuditRecordId,
  AuditScope,
  AuditVerdict,
  EvidenceDetail,
  EvidenceRef,
  EvidenceId,
  MainPageReturnTarget,
} from "../../shared/api/types";

export type AuditEntryLink = {
  label: string;
  href: string;
};

export type {
  AuditCompleteness,
  AuditEntryContext,
  AuditFilterKind,
  AuditPageSnapshot,
  AuditRecord,
  AuditRecordDetail,
  AuditRecordId,
  AuditScope,
  AuditVerdict,
  EvidenceDetail,
  EvidenceId,
  EvidenceRef,
  MainPageReturnTarget,
};
