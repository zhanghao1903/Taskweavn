import type {
  AuditFilterKind,
  AuditPageSnapshot,
  AuditRecord,
  AuditRecordDetail,
  AuditRecordId,
} from "../../shared/api/types";

export type AuditSnapshotProjectionOptions = {
  activeFilter: AuditFilterKind;
  selectedRecordId: AuditRecordId | null;
  selectedRecordDetail?: AuditRecordDetail | null;
};

export function projectAuditSnapshot(
  snapshot: AuditPageSnapshot,
  options: AuditSnapshotProjectionOptions,
): AuditPageSnapshot {
  const records = filterAuditRecords(snapshot.records, options.activeFilter);
  const selectedRecord = resolveSelectedRecordDetail(snapshot, options);

  return {
    ...snapshot,
    records,
    request: {
      ...snapshot.request,
      filter: options.activeFilter,
      includeDetail: options.selectedRecordId !== null,
      recordId: options.selectedRecordId,
    },
    selectedRecord,
  };
}

function resolveSelectedRecordDetail(
  snapshot: AuditPageSnapshot,
  options: AuditSnapshotProjectionOptions,
): AuditRecordDetail | null {
  if (options.selectedRecordId === null) {
    return null;
  }

  const candidates = [
    options.selectedRecordDetail,
    snapshot.selectedRecord,
  ];

  return candidates.find(
    (record): record is AuditRecordDetail =>
      record !== null &&
      record !== undefined &&
      record.id === options.selectedRecordId &&
      recordMatchesFilter(record, options.activeFilter),
  ) ?? null;
}

export function filterAuditRecords(
  records: AuditRecord[],
  filter: AuditFilterKind,
): AuditRecord[] {
  if (filter === "all") {
    return records;
  }

  return records.filter((record) => recordMatchesFilter(record, filter));
}

export function recordMatchesFilter(
  record: AuditRecord,
  filter: AuditFilterKind,
): boolean {
  return filter === "all" || record.filterKind === filter;
}

export function selectedRecordSurvivesFilter(
  records: AuditRecord[],
  filter: AuditFilterKind,
  selectedRecordId: AuditRecordId | null,
): boolean {
  if (selectedRecordId === null) {
    return false;
  }

  return records.some(
    (record) =>
      record.id === selectedRecordId && recordMatchesFilter(record, filter),
  );
}
