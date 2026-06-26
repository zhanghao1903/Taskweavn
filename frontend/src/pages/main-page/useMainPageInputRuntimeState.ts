import { useCallback, useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type {
  RuntimeInputMode,
  SessionActivityItemView,
  WorkspaceId,
} from "../../shared/api/types";

export type UseMainPageInputRuntimeStateOptions = {
  activeSessionId: string | null;
  activeWorkspaceId: WorkspaceId | null;
};

export type MainPageInputRuntimeState = {
  activeRuntimeInputMode: RuntimeInputMode | null;
  changeInputDraft: (draft: string) => void;
  inputDraft: string;
  resetInputDraft: () => void;
  runtimeActivityItems: SessionActivityItemView[];
  setActiveRuntimeInputMode: (mode: RuntimeInputMode | null) => void;
  setRuntimeActivityItems: Dispatch<
    SetStateAction<SessionActivityItemView[]>
  >;
};

export function useMainPageInputRuntimeState({
  activeSessionId,
  activeWorkspaceId,
}: UseMainPageInputRuntimeStateOptions): MainPageInputRuntimeState {
  const [inputDraft, setInputDraft] = useState("");
  const [runtimeActivityItems, setRuntimeActivityItems] = useState<
    SessionActivityItemView[]
  >([]);
  const [activeRuntimeInputMode, setActiveRuntimeInputMode] =
    useState<RuntimeInputMode | null>(null);

  const changeInputDraft = useCallback((draft: string) => {
    setInputDraft(draft);
  }, []);

  const resetInputDraft = useCallback(() => {
    setInputDraft("");
  }, []);

  useEffect(() => {
    setRuntimeActivityItems([]);
  }, [activeSessionId, activeWorkspaceId]);

  return {
    activeRuntimeInputMode,
    changeInputDraft,
    inputDraft,
    resetInputDraft,
    runtimeActivityItems,
    setActiveRuntimeInputMode,
    setRuntimeActivityItems,
  };
}
