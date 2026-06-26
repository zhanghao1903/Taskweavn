import { useQuery } from "@tanstack/react-query";
import type { MutableRefObject } from "react";
import { useEffect, useRef } from "react";

import type { WorkspaceCatalogResult } from "../../shared/api/platoApi";
import type { TaskNodeId, WorkspaceId } from "../../shared/api/types";
import { summarizeMainPageSnapshot } from "../../shared/api/traceSummary";
import {
  createFrontendLogger,
  summarizeLoggableError,
  toLoggableError,
} from "../../shared/logging/frontendLogger";
import type { MainPageStateId } from "./mockPlatoApi";
import type {
  MainPageAdapter,
  MainPageRuntimeSnapshot,
} from "./runtime/adapter";
import {
  mainPageSnapshotIdentity,
  mainPageSnapshotQueryKey,
} from "./runtime/adapter";

const mainPageSnapshotLogger = createFrontendLogger("main-page");

export type UseMainPageSnapshotQueryOptions = {
  activeSessionId: string | null;
  activeWorkspaceId: WorkspaceId | null;
  adapter: MainPageAdapter;
  initialTaskNodeId: TaskNodeId | null;
  stateId: MainPageStateId;
};

export type SnapshotRefetchResult = {
  data?: MainPageRuntimeSnapshot;
  status: string;
};

export type MainPageSnapshotQueryController = {
  initialTaskNodeIdRef: MutableRefObject<TaskNodeId | null>;
  isSnapshotError: boolean;
  isSnapshotPending: boolean;
  refetchSnapshot: () => Promise<SnapshotRefetchResult>;
  refetchWorkspaceCatalog: () => void;
  snapshotData: MainPageRuntimeSnapshot | undefined;
  snapshotDataRef: MutableRefObject<MainPageRuntimeSnapshot | undefined>;
  snapshotError: unknown;
  snapshotIdentity: string | null;
  workspaceCatalog: WorkspaceCatalogResult | null;
};

export function useMainPageSnapshotQuery({
  activeSessionId,
  activeWorkspaceId,
  adapter,
  initialTaskNodeId,
  stateId,
}: UseMainPageSnapshotQueryOptions): MainPageSnapshotQueryController {
  const workspaceCatalogQuery = useQuery({
    enabled: adapter.loadWorkspaceCatalog !== undefined,
    queryKey: ["main-page", "workspaces", adapter.runtimeKind],
    queryFn: () => {
      if (adapter.loadWorkspaceCatalog === undefined) {
        throw new Error("Workspace catalog is unavailable.");
      }
      return adapter.loadWorkspaceCatalog();
    },
  });
  const workspaceCatalog = workspaceCatalogQuery.data ?? null;

  const snapshotQuery = useQuery<MainPageRuntimeSnapshot>({
    queryKey: mainPageSnapshotQueryKey(
      adapter,
      stateId,
      activeSessionId,
      activeWorkspaceId,
    ),
    queryFn: () => adapter.loadSnapshot(stateId, activeSessionId, activeWorkspaceId),
  });
  const snapshotData = snapshotQuery.data;
  const snapshotDataRef = useRef(snapshotData);
  const initialTaskNodeIdRef = useRef<TaskNodeId | null>(initialTaskNodeId);
  snapshotDataRef.current = snapshotData;
  const snapshotIdentity = snapshotData
    ? mainPageSnapshotIdentity(
        adapter,
        stateId,
        snapshotData,
        activeSessionId,
        activeWorkspaceId,
      )
    : null;
  const refetchSnapshot = snapshotQuery.refetch;

  function refetchWorkspaceCatalog() {
    if (adapter.loadWorkspaceCatalog === undefined) {
      return;
    }
    void workspaceCatalogQuery.refetch();
  }

  useEffect(() => {
    if (!snapshotQuery.isError) {
      return;
    }

    mainPageSnapshotLogger.error(
      `snapshot.query.failed ${stateId} -> ${summarizeLoggableError(
        snapshotQuery.error,
      )}`,
      {
        error: toLoggableError(snapshotQuery.error),
        runtimeKind: adapter.runtimeKind,
        stateId,
      },
    );
  }, [adapter.runtimeKind, snapshotQuery.error, snapshotQuery.isError, stateId]);

  useEffect(() => {
    if (!snapshotData) {
      return;
    }

    mainPageSnapshotLogger.info("snapshot.query.data", {
      ...summarizeMainPageSnapshot(snapshotData.snapshot),
      activeSessionId,
      runtimeKind: adapter.runtimeKind,
      stateId,
    });
  }, [activeSessionId, adapter.runtimeKind, snapshotData, stateId]);

  return {
    initialTaskNodeIdRef,
    isSnapshotError: snapshotQuery.isError,
    isSnapshotPending: snapshotQuery.isPending,
    refetchSnapshot,
    refetchWorkspaceCatalog,
    snapshotData,
    snapshotDataRef,
    snapshotError: snapshotQuery.error,
    snapshotIdentity,
    workspaceCatalog,
  };
}
