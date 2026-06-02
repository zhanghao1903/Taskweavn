import type {
  AuditRecordsResult,
  PlatoApi,
} from "../../shared/api/platoApi";
import type {
  ApiError,
  AuditRecord,
  AuditRecordDetail,
  QueryResponse,
} from "../../shared/api/types";
import {
  getAuditMockEvidenceDetailResponse,
  getAuditMockSnapshot,
  type AuditMockScenarioId,
} from "./mockAuditScenarios";

export type AuditMockApi = Pick<
  PlatoApi,
  | "getAuditSnapshot"
  | "listAuditRecords"
  | "getAuditRecordDetail"
  | "getEvidenceDetail"
  | "subscribeSessionEvents"
>;

export function createAuditMockApi(
  scenarioId: AuditMockScenarioId = "a3-records-ready",
): AuditMockApi {
  return {
    async getAuditSnapshot() {
      const snapshot = getAuditMockSnapshot(scenarioId);
      return okResponse(snapshot, snapshot.cursor);
    },
    async listAuditRecords() {
      const snapshot = getAuditMockSnapshot(scenarioId);
      return okResponse<AuditRecordsResult>(
        {
          nextCursor: null,
          records: snapshot.records,
          totalCount: snapshot.records.length,
        },
        snapshot.cursor,
      );
    },
    async getAuditRecordDetail(request) {
      const snapshot = getAuditMockSnapshot(scenarioId);
      const record =
        snapshot.selectedRecord?.id === request.recordId
          ? snapshot.selectedRecord
          : snapshot.records.find((item) => item.id === request.recordId);

      if (record === undefined) {
        return errorResponse("not_found", "Audit record was not found.");
      }

      return okResponse<AuditRecordDetail>(
        toAuditRecordDetail(record),
        snapshot.cursor,
      );
    },
    async getEvidenceDetail(request) {
      return getAuditMockEvidenceDetailResponse(scenarioId, request.evidenceId);
    },
    subscribeSessionEvents() {
      return () => {};
    },
  };
}

function okResponse<T>(data: T, cursor?: string | null): QueryResponse<T> {
  return {
    cursor,
    data,
    error: null,
    generatedAt: "2026-05-24T10:02:00Z",
    ok: true,
    requestId: "request-audit-mock",
  };
}

function toAuditRecordDetail(
  record: AuditRecord | AuditRecordDetail,
): AuditRecordDetail {
  if (isAuditRecordDetail(record)) {
    return record;
  }

  return {
    ...record,
    body: `${record.title} detail body.`,
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
    whyItMatters: "Audit detail explains trust and evidence.",
  };
}

function isAuditRecordDetail(
  record: AuditRecord | AuditRecordDetail,
): record is AuditRecordDetail {
  return "whyItMatters" in record;
}

function errorResponse<T>(code: ApiError["code"], message: string): QueryResponse<T> {
  return {
    data: null,
    error: {
      code,
      details: {},
      message,
      retryable: code !== "not_found",
    },
    generatedAt: "2026-05-24T10:02:00Z",
    ok: false,
    requestId: `request-audit-${code}`,
  };
}
