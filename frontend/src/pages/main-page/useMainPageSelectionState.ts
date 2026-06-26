import { useCallback, useRef, useState } from "react";

import type { TaskNodeId } from "../../shared/api/types";
import type {
  DetailOverride,
  MainPageSelectionTarget,
} from "./mainPageUiTypes";
import type { MainPageRuntimeSnapshot } from "./runtime/adapter";

export function useMainPageSelectionState(
  initialTaskNodeId: TaskNodeId | null,
) {
  const [selectedTaskNodeId, setSelectedTaskNodeId] =
    useState<TaskNodeId | null>(null);
  const [selectionTarget, setSelectionTarget] =
    useState<MainPageSelectionTarget>("auto");
  const [detailOverride, setDetailOverride] =
    useState<DetailOverride>("auto");
  const initialTaskNodeIdRef = useRef<TaskNodeId | null>(initialTaskNodeId);

  const resetSelection = useCallback(() => {
    setSelectedTaskNodeId(null);
    setSelectionTarget("auto");
    setDetailOverride("auto");
  }, []);

  const applySnapshotSelection = useCallback(
    (snapshot: MainPageRuntimeSnapshot) => {
      const routeTaskNodeId = initialTaskNodeIdRef.current;
      const nextSelectedTaskNodeId =
        routeTaskNodeId !== null &&
        snapshot.snapshot.taskTree?.nodes.some(
          (node) => node.id === routeTaskNodeId,
        )
          ? routeTaskNodeId
          : snapshot.metadata.initialSelectedTaskNodeId;
      initialTaskNodeIdRef.current = null;
      setSelectedTaskNodeId(nextSelectedTaskNodeId);
      setSelectionTarget("auto");
      setDetailOverride("auto");
    },
    [],
  );

  const selectTask = useCallback((nodeId: TaskNodeId) => {
    setSelectedTaskNodeId(nodeId);
    setSelectionTarget("task");
    setDetailOverride("auto");
  }, []);

  const selectTaskPlan = useCallback(() => {
    setSelectedTaskNodeId(null);
    setSelectionTarget("plan");
    setDetailOverride("auto");
  }, []);

  const showFileChanges = useCallback(() => {
    setDetailOverride("fileChanges");
  }, []);

  const showResult = useCallback(() => {
    setDetailOverride("result");
  }, []);

  return {
    applySnapshotSelection,
    detailOverride,
    resetSelection,
    selectedTaskNodeId,
    selectionTarget,
    selectTask,
    selectTaskPlan,
    showFileChanges,
    showResult,
  };
}
