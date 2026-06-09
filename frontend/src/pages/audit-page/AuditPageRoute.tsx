import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { PlatoApi } from "../../shared/api/platoApi";
import type {
  AuditFilterKind,
  AuditRecordDetail,
  AuditRecordId,
} from "../../shared/api/types";
import {
  createAuditApiFromRuntimeEnv,
  type PlatoRuntimeEnv,
} from "../../app/platoRuntime";
import { AuditPage } from "./AuditPage";
import {
  buildAuditLocation,
  parseAuditLocation,
} from "./auditRouteModel";
import {
  projectAuditSnapshot,
  selectedRecordSurvivesFilter,
} from "./auditPageViewModel";
import {
  useAuditPageRuntimeEvents,
  type AuditPageRuntimeState,
} from "./auditRuntimeEvents";

export type AuditApi = Pick<
  PlatoApi,
  | "getAuditSnapshot"
  | "listAuditRecords"
  | "getAuditRecordDetail"
  | "getEvidenceDetail"
  | "subscribeSessionEvents"
>;

export type AuditPageRouteLocation = {
  pathname: string;
  search?: string;
};

export type AuditPageRouteProps = {
  api?: AuditApi;
  location?: AuditPageRouteLocation;
  runtimeEnv?: PlatoRuntimeEnv;
};

export function AuditPageRoute({
  api,
  location,
  runtimeEnv,
}: AuditPageRouteProps = {}) {
  const resolvedLocation = location ?? globalThis.location;
  const parsedRoute = useMemo(
    () => parseAuditLocation(resolvedLocation.pathname, resolvedLocation.search),
    [resolvedLocation.pathname, resolvedLocation.search],
  );
  const [activeFilter, setActiveFilter] = useState<AuditFilterKind>(
    () => parsedRoute?.request.filter ?? "all",
  );
  const [selectedRecordId, setSelectedRecordId] = useState<AuditRecordId | null>(
    () => parsedRoute?.request.recordId ?? null,
  );
  const [liveState, setLiveState] = useState<AuditPageRuntimeState>({
    eventCursor: null,
    message: null,
    status: "connected",
  });
  const auditApi = useMemo<AuditApi>(
    () => api ?? createAuditApiFromRuntimeEnv(runtimeEnv),
    [api, runtimeEnv],
  );
  const workspaceOptions = useMemo(
    () =>
      parsedRoute?.workspaceId
        ? { workspaceId: parsedRoute.workspaceId }
        : undefined,
    [parsedRoute?.workspaceId],
  );
  const activeRequest = useMemo(
    () =>
      parsedRoute === null
        ? null
        : {
            ...parsedRoute.request,
            filter: activeFilter,
            includeDetail: selectedRecordId !== null,
            recordId: selectedRecordId ?? undefined,
          },
    [activeFilter, parsedRoute, selectedRecordId],
  );

  const snapshotQuery = useQuery({
    enabled: activeRequest !== null,
    queryFn: () =>
      workspaceOptions
        ? auditApi.getAuditSnapshot(activeRequest!, workspaceOptions)
        : auditApi.getAuditSnapshot(activeRequest!),
    queryKey: ["audit-page", workspaceOptions?.workspaceId ?? null, activeRequest],
  });

  useEffect(() => {
    if (parsedRoute === null) {
      return;
    }

    setActiveFilter(parsedRoute.request.filter ?? "all");
    setSelectedRecordId(parsedRoute.request.recordId ?? null);
  }, [parsedRoute]);

  const rawSnapshot = snapshotQuery.data?.ok === true ? snapshotQuery.data.data : null;
  const rawSnapshotCursor = rawSnapshot?.cursor ?? null;
  useEffect(() => {
    if (rawSnapshotCursor === null) {
      return;
    }

    setLiveState({
      eventCursor: rawSnapshotCursor,
      message: null,
      status: "connected",
    });
  }, [rawSnapshotCursor]);

  const snapshotSelectedRecord =
    rawSnapshot?.selectedRecord?.id === selectedRecordId
      ? rawSnapshot.selectedRecord
      : null;
  const shouldLoadRecordDetail =
    rawSnapshot !== null &&
    selectedRecordId !== null &&
    snapshotSelectedRecord === null;

  const detailQuery = useQuery({
    enabled: shouldLoadRecordDetail,
    queryFn: () => {
      const request = {
        includeEvidence: true,
        includeSanitizedPayload: true,
        recordId: selectedRecordId!,
        sessionId: rawSnapshot!.session.id,
      };
      return workspaceOptions
        ? auditApi.getAuditRecordDetail(request, workspaceOptions)
        : auditApi.getAuditRecordDetail(request);
    },
    queryKey: [
      "audit-record-detail",
      workspaceOptions?.workspaceId ?? null,
      rawSnapshot?.session.id,
      selectedRecordId,
    ],
  });
  const selectedRecordDetail = resolveDetailResponse(
    snapshotSelectedRecord,
    detailQuery.data?.ok === true ? detailQuery.data.data : null,
    selectedRecordId,
  );
  const selectedEvidenceRef =
    selectedRecordDetail?.evidence[0] ??
    selectedRecordDetail?.evidenceRefs[0] ??
    null;
  const shouldLoadEvidenceDetail =
    rawSnapshot !== null &&
    selectedRecordDetail !== null &&
    selectedEvidenceRef !== null &&
    selectedEvidenceRef.available;

  const evidenceQuery = useQuery({
    enabled: shouldLoadEvidenceDetail,
    queryFn: () => {
      const request = {
        evidenceId: selectedEvidenceRef!.id,
        includeSanitizedPayload: true,
        sessionId: rawSnapshot!.session.id,
      };
      return workspaceOptions
        ? auditApi.getEvidenceDetail(request, workspaceOptions)
        : auditApi.getEvidenceDetail(request);
    },
    queryKey: [
      "audit-evidence-detail",
      workspaceOptions?.workspaceId ?? null,
      rawSnapshot?.session.id,
      selectedRecordId,
      selectedEvidenceRef?.id,
    ],
  });
  useAuditPageRuntimeEvents({
    api: auditApi,
    cursor: rawSnapshot?.cursor ?? null,
    enabled: rawSnapshot !== null,
    onRuntimeStateChange: setLiveState,
    refetchDetail: detailQuery.refetch,
    refetchEvidence: evidenceQuery.refetch,
    refetchSnapshot: snapshotQuery.refetch,
    selectedEvidenceId: selectedEvidenceRef?.id ?? null,
    selectedRecordId,
    sessionId: activeRequest?.sessionId ?? "",
    taskNodeId: activeRequest?.taskNodeId ?? null,
    workspaceId: workspaceOptions?.workspaceId ?? null,
  });
  const snapshot = useMemo(
    () =>
      rawSnapshot === null
        ? null
        : projectAuditSnapshot(rawSnapshot, {
            activeFilter,
            selectedRecordDetail,
            selectedRecordId,
          }),
    [activeFilter, rawSnapshot, selectedRecordDetail, selectedRecordId],
  );
  const updateBrowserLocation = useCallback(
    (filter: AuditFilterKind, recordId: AuditRecordId | null) => {
      if (parsedRoute === null || location !== undefined) {
        return;
      }

      globalThis.history.pushState(
        null,
        "",
        buildAuditLocation(parsedRoute, {
          filter,
          recordId,
        }),
      );
    },
    [location, parsedRoute],
  );

  const handleSelectFilter = useCallback(
    (filter: AuditFilterKind) => {
      const nextSelectedRecordId =
        rawSnapshot !== null &&
        selectedRecordSurvivesFilter(rawSnapshot.records, filter, selectedRecordId)
          ? selectedRecordId
          : null;

      updateBrowserLocation(filter, nextSelectedRecordId);
      setActiveFilter(filter);
      setSelectedRecordId(nextSelectedRecordId);
    },
    [rawSnapshot, selectedRecordId, updateBrowserLocation],
  );

  const handleSelectRecord = useCallback(
    (recordId: AuditRecordId) => {
      updateBrowserLocation(activeFilter, recordId);
      setSelectedRecordId(recordId);
    },
    [activeFilter, updateBrowserLocation],
  );

  const handleCloseDetail = useCallback(() => {
    updateBrowserLocation(activeFilter, null);
    setSelectedRecordId(null);
  }, [activeFilter, updateBrowserLocation]);

  if (parsedRoute === null) {
    return (
      <AuditPage
        errorMessage="Invalid Audit Page route."
        snapshot={null}
      />
    );
  }

  const response = snapshotQuery.data;
  const queryError =
    snapshotQuery.error instanceof Error ? snapshotQuery.error.message : null;
  const responseError = response?.ok === false ? response.error?.message ?? null : null;
  const detailResponseError =
    detailQuery.data?.ok === false ? detailQuery.data.error?.message ?? null : null;
  const detailQueryError =
    detailQuery.error instanceof Error ? detailQuery.error.message : null;
  const evidenceResponseError =
    evidenceQuery.data?.ok === false ? evidenceQuery.data.error?.message ?? null : null;
  const evidenceQueryError =
    evidenceQuery.error instanceof Error ? evidenceQuery.error.message : null;

  return (
    <AuditPage
      detailState={{
        errorMessage: detailQueryError ?? detailResponseError,
        evidenceDetail:
          evidenceQuery.data?.ok === true ? evidenceQuery.data.data : null,
        evidenceErrorMessage: evidenceQueryError ?? evidenceResponseError,
        evidenceIsLoading: shouldLoadEvidenceDetail && evidenceQuery.isPending,
        isLoading: shouldLoadRecordDetail && detailQuery.isPending,
      }}
      errorMessage={queryError ?? responseError}
      isLoading={snapshotQuery.isPending}
      onCloseDetail={handleCloseDetail}
      onSelectFilter={handleSelectFilter}
      onSelectRecord={handleSelectRecord}
      onRetry={() => void snapshotQuery.refetch()}
      selectedRecordId={selectedRecordId}
      liveState={liveState}
      snapshot={snapshot}
    />
  );
}

function resolveDetailResponse(
  snapshotSelectedRecord: AuditRecordDetail | null,
  queriedRecord: AuditRecordDetail | null,
  selectedRecordId: AuditRecordId | null,
): AuditRecordDetail | null {
  if (selectedRecordId === null) {
    return null;
  }

  if (snapshotSelectedRecord?.id === selectedRecordId) {
    return snapshotSelectedRecord;
  }

  if (queriedRecord?.id === selectedRecordId) {
    return queriedRecord;
  }

  return null;
}
