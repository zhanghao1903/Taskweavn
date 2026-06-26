import { useCallback, useEffect, useState } from "react";

import type {
  SessionSummary,
  WorkspaceId,
} from "../../shared/api/types";

export type UseMainPageSessionIdentityStateOptions = {
  initialSessionId: string | null;
  initialWorkspaceId: WorkspaceId | null;
  setUiNotice: (notice: string | null) => void;
};

export type MainPageSessionIdentityState = {
  activeSessionId: string | null;
  activeWorkspaceId: WorkspaceId | null;
  adoptSessionId: (sessionId: string) => void;
  adoptWorkspaceId: (workspaceId: WorkspaceId) => void;
  selectSession: (session: SessionSummary, currentSessionId: string) => void;
  setActiveSessionId: (sessionId: string | null) => void;
  setActiveWorkspaceId: (workspaceId: WorkspaceId | null) => void;
};

export type UseMainPageSessionIdentityAdoptionOptions = {
  adoptSessionId: (sessionId: string) => void;
  adoptWorkspaceId: (workspaceId: WorkspaceId) => void;
  catalogWorkspaceId: WorkspaceId | null;
  snapshotSessionId: string | null;
};

export function useMainPageSessionIdentityState({
  initialSessionId,
  initialWorkspaceId,
  setUiNotice,
}: UseMainPageSessionIdentityStateOptions): MainPageSessionIdentityState {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(
    initialSessionId,
  );
  const [activeWorkspaceId, setActiveWorkspaceId] =
    useState<WorkspaceId | null>(initialWorkspaceId);

  const adoptSessionId = useCallback((sessionId: string) => {
    setActiveSessionId((currentSessionId) => currentSessionId ?? sessionId);
  }, []);

  const adoptWorkspaceId = useCallback((workspaceId: WorkspaceId) => {
    setActiveWorkspaceId(
      (currentWorkspaceId) => currentWorkspaceId ?? workspaceId,
    );
  }, []);

  const selectSession = useCallback(
    (session: SessionSummary, currentSessionId: string) => {
      const nextWorkspaceId = session.workspaceId ?? activeWorkspaceId;
      if (
        session.id === currentSessionId &&
        nextWorkspaceId === activeWorkspaceId
      ) {
        setUiNotice("This session is already open.");
        return;
      }

      setActiveWorkspaceId(nextWorkspaceId ?? null);
      setActiveSessionId(session.id);
    },
    [activeWorkspaceId, setUiNotice],
  );

  return {
    activeSessionId,
    activeWorkspaceId,
    adoptSessionId,
    adoptWorkspaceId,
    selectSession,
    setActiveSessionId,
    setActiveWorkspaceId,
  };
}

export function useMainPageSessionIdentityAdoption({
  adoptSessionId,
  adoptWorkspaceId,
  catalogWorkspaceId,
  snapshotSessionId,
}: UseMainPageSessionIdentityAdoptionOptions) {
  useEffect(() => {
    if (snapshotSessionId === null) {
      return;
    }
    adoptSessionId(snapshotSessionId);
  }, [adoptSessionId, snapshotSessionId]);

  useEffect(() => {
    if (catalogWorkspaceId === null) {
      return;
    }
    adoptWorkspaceId(catalogWorkspaceId);
  }, [adoptWorkspaceId, catalogWorkspaceId]);
}
