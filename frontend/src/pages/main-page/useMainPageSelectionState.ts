import { useCallback, useState } from "react";

import type { TaskNodeId } from "../../shared/api/types";
import type {
  DetailOverride,
  MainPageSelectionTarget,
} from "./mainPageUiTypes";

export type MainPageSelectionStateController = {
  detailOverride: DetailOverride;
  selectedTaskNodeId: TaskNodeId | null;
  selectionTarget: MainPageSelectionTarget;
  actions: {
    selectTask: (nodeId: TaskNodeId) => void;
    selectTaskPlan: () => void;
    showFileChanges: () => void;
    showResult: () => void;
  };
  resetSelection: (selectedTaskNodeId?: TaskNodeId | null) => void;
  setDetailOverride: (detailOverride: DetailOverride) => void;
  setSelectedTaskNodeId: (nodeId: TaskNodeId | null) => void;
  setSelectionTarget: (target: MainPageSelectionTarget) => void;
};

export function useMainPageSelectionState(
  onUserVisibleSelectionChange: () => void,
): MainPageSelectionStateController {
  const [selectedTaskNodeId, setSelectedTaskNodeId] =
    useState<TaskNodeId | null>(null);
  const [selectionTarget, setSelectionTarget] =
    useState<MainPageSelectionTarget>("auto");
  const [detailOverride, setDetailOverride] =
    useState<DetailOverride>("auto");

  const resetSelection = useCallback(
    (nextSelectedTaskNodeId: TaskNodeId | null = null) => {
      setSelectedTaskNodeId(nextSelectedTaskNodeId);
      setSelectionTarget("auto");
      setDetailOverride("auto");
    },
    [],
  );

  const selectTask = useCallback(
    (nodeId: TaskNodeId) => {
      setSelectedTaskNodeId(nodeId);
      setSelectionTarget("task");
      setDetailOverride("auto");
      onUserVisibleSelectionChange();
    },
    [onUserVisibleSelectionChange],
  );

  const selectTaskPlan = useCallback(
    () => {
      setSelectedTaskNodeId(null);
      setSelectionTarget("plan");
      setDetailOverride("auto");
      onUserVisibleSelectionChange();
    },
    [onUserVisibleSelectionChange],
  );

  const showFileChanges = useCallback(() => {
    setDetailOverride("fileChanges");
  }, []);

  const showResult = useCallback(() => {
    setDetailOverride("result");
  }, []);

  return {
    detailOverride,
    selectedTaskNodeId,
    selectionTarget,
    actions: {
      selectTask,
      selectTaskPlan,
      showFileChanges,
      showResult,
    },
    resetSelection,
    setDetailOverride,
    setSelectedTaskNodeId,
    setSelectionTarget,
  };
}
