import type {
  AuditFilterKind,
  AuditPageSnapshot,
  AuditRecordDetail,
  AuditRecordId,
} from "../../shared/api/types";

export function activeAuditFilter(
  snapshot: AuditPageSnapshot | null,
): AuditFilterKind {
  return snapshot?.request.filter ?? "all";
}

export function activeAuditRecordId(
  snapshot: AuditPageSnapshot | null,
  selectedRecordId: AuditRecordId | null | undefined,
): AuditRecordId | null {
  return selectedRecordId ?? snapshot?.selectedRecord?.id ?? snapshot?.request.recordId ?? null;
}

export function resolveSelectedAuditRecord(
  snapshot: AuditPageSnapshot,
  selectedRecordId: AuditRecordId | null,
): AuditRecordDetail | null {
  if (snapshot.selectedRecord !== null) {
    return snapshot.selectedRecord;
  }

  if (selectedRecordId === null) {
    return null;
  }

  const record = snapshot.records.find((item) => item.id === selectedRecordId);
  if (record === undefined) {
    return null;
  }

  return {
    ...record,
    body: "Record detail is not loaded yet.",
    disclosure: {
      rawPayloadAvailable: false,
      rawPayloadShown: false,
    },
    evidence: record.evidenceRefs.map((item) => ({
      ...item,
      source: "mock",
    })),
    outcome: null,
    rawPayload: null,
    references: [],
    relatedLogs: [],
    whyItMatters: "Select a record route with detail enabled to load complete evidence.",
  };
}
