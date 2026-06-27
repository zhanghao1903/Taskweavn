import type { MutableRefObject } from "react";
import { useEffect } from "react";

import type { TaskNodeId, WorkspaceId } from "../../shared/api/types";
import type { MainPageRuntimeSnapshot } from "./runtime/adapter";
import type { RuntimeInputSnapshotContext } from "./useMainPageInputRuntimeState";

export type UseMainPageSnapshotEffectsOptions = {
  activeWorkspaceId: WorkspaceId | null;
  clearEventError: () => void;
  clearPendingRuntimeClarification: () => void;
  hydrateRuntimeInputSnapshot: (context: RuntimeInputSnapshotContext) => void;
  initialTaskNodeIdRef: MutableRefObject<TaskNodeId | null>;
  resetCommandErrorState: () => void;
  resetInputDraft: () => void;
  resetSelection: (selectedTaskNodeId?: TaskNodeId | null) => void;
  resetSessionDialog: () => void;
  setUiNotice: (notice: string | null) => void;
  snapshotData: MainPageRuntimeSnapshot | undefined;
  snapshotDataRef: MutableRefObject<MainPageRuntimeSnapshot | undefined>;
  snapshotIdentity: string | null;
};

export function useMainPageSnapshotEffects({
  activeWorkspaceId,
  clearEventError,
  clearPendingRuntimeClarification,
  hydrateRuntimeInputSnapshot,
  initialTaskNodeIdRef,
  resetCommandErrorState,
  resetInputDraft,
  resetSelection,
  resetSessionDialog,
  setUiNotice,
  snapshotData,
  snapshotDataRef,
  snapshotIdentity,
}: UseMainPageSnapshotEffectsOptions) {
  useEffect(() => {
    const currentSnapshot = snapshotDataRef.current;

    if (!currentSnapshot) {
      return;
    }

    const routeTaskNodeId = initialTaskNodeIdRef.current;
    const nextSelectedTaskNodeId =
      routeTaskNodeId !== null &&
      currentSnapshot.snapshot.taskTree?.nodes.some(
        (node) => node.id === routeTaskNodeId,
      )
        ? routeTaskNodeId
        : currentSnapshot.metadata.initialSelectedTaskNodeId;
    initialTaskNodeIdRef.current = null;
    resetSelection(nextSelectedTaskNodeId);
    resetInputDraft();
    clearPendingRuntimeClarification();
    resetCommandErrorState();
    setUiNotice(null);
    resetSessionDialog();
    clearEventError();
  }, [
    clearEventError,
    clearPendingRuntimeClarification,
    initialTaskNodeIdRef,
    resetCommandErrorState,
    resetInputDraft,
    resetSelection,
    resetSessionDialog,
    setUiNotice,
    snapshotDataRef,
    snapshotIdentity,
  ]);

  useEffect(() => {
    const currentSnapshot = snapshotData?.snapshot;

    if (!currentSnapshot) {
      return;
    }

    hydrateRuntimeInputSnapshot({
      messages: currentSnapshot.messages,
      sessionId: currentSnapshot.session.id,
      workspaceId: activeWorkspaceId,
    });
  }, [
    activeWorkspaceId,
    hydrateRuntimeInputSnapshot,
    snapshotData?.snapshot,
  ]);
}
