import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type {
  RuntimeInputMode,
  SessionActivityItemView,
  SessionMessageView,
  WorkspaceId,
} from "../../shared/api/types";
import {
  createInitialPendingRuntimeState,
  mainPagePendingRuntimeReducer,
  projectPendingRuntimeActivityItems,
  type PendingRuntimeCommandScope,
} from "./runtime/mainPagePendingRuntime";

export type UseMainPageInputRuntimeStateOptions = {
  activeSessionId: string | null;
  activeWorkspaceId: WorkspaceId | null;
};

export type MainPageInputRuntimeState = {
  acceptRuntimeInputSubmit: (commandId: string) => void;
  activeRuntimeInputMode: RuntimeInputMode | null;
  changeInputDraft: (draft: string) => void;
  failRuntimeInputSubmit: (context: RuntimeInputSubmitFailureContext) => void;
  hydrateRuntimeInputSnapshot: (context: RuntimeInputSnapshotContext) => void;
  inputDraft: string;
  reconcileRuntimeInputSubmit: (commandId: string) => void;
  rejectRuntimeInputSubmit: (context: RuntimeInputSubmitFailureContext) => void;
  resetInputDraft: () => void;
  runtimeActivityItems: SessionActivityItemView[];
  setActiveRuntimeInputMode: (mode: RuntimeInputMode | null) => void;
  setRuntimeActivityItems: Dispatch<
    SetStateAction<SessionActivityItemView[]>
  >;
  startRuntimeInputSubmit: (context: RuntimeInputSubmitStartContext) => void;
};

export type RuntimeInputSubmitStartContext = {
  body: string;
  commandId: string;
  createdAt: string;
  scope: PendingRuntimeCommandScope;
  sessionId: string;
  workspaceId: WorkspaceId | null;
};

export type RuntimeInputSubmitFailureContext = {
  commandId: string;
  message: string;
  recoveryActions: ProductRecoveryAction[];
};

export type RuntimeInputSnapshotContext = {
  activities?: SessionActivityItemView[];
  messages: SessionMessageView[];
  sessionId: string;
  workspaceId: WorkspaceId | null;
};

export function useMainPageInputRuntimeState({
  activeSessionId,
  activeWorkspaceId,
}: UseMainPageInputRuntimeStateOptions): MainPageInputRuntimeState {
  const [inputDraft, setInputDraft] = useState("");
  const [confirmedRuntimeActivityItems, setRuntimeActivityItems] = useState<
    SessionActivityItemView[]
  >([]);
  const [pendingRuntimeState, dispatchPendingRuntime] = useReducer(
    mainPagePendingRuntimeReducer,
    { sessionId: activeSessionId, workspaceId: activeWorkspaceId },
    createInitialPendingRuntimeState,
  );
  const [activeRuntimeInputMode, setActiveRuntimeInputMode] =
    useState<RuntimeInputMode | null>(null);
  const pendingRuntimeActivityItems = useMemo(
    () => projectPendingRuntimeActivityItems(pendingRuntimeState),
    [pendingRuntimeState],
  );
  const runtimeActivityItems = useMemo(
    () => [
      ...pendingRuntimeActivityItems,
      ...confirmedRuntimeActivityItems,
    ],
    [confirmedRuntimeActivityItems, pendingRuntimeActivityItems],
  );

  const changeInputDraft = useCallback((draft: string) => {
    setInputDraft(draft);
  }, []);

  const resetInputDraft = useCallback(() => {
    setInputDraft("");
  }, []);

  const startRuntimeInputSubmit = useCallback(
    ({
      body,
      commandId,
      createdAt,
      scope,
      sessionId,
      workspaceId,
    }: RuntimeInputSubmitStartContext) => {
      dispatchPendingRuntime({
        body,
        commandId,
        createdAt,
        scope,
        sessionId,
        type: "runtime_input.submit_started",
        workspaceId,
      });
    },
    [],
  );

  const acceptRuntimeInputSubmit = useCallback((commandId: string) => {
    dispatchPendingRuntime({
      commandId,
      type: "runtime_input.command_accepted",
    });
  }, []);

  const reconcileRuntimeInputSubmit = useCallback((commandId: string) => {
    dispatchPendingRuntime({
      commandId,
      type: "runtime_input.command_reconciled",
    });
  }, []);

  const rejectRuntimeInputSubmit = useCallback(
    ({ commandId, message, recoveryActions }: RuntimeInputSubmitFailureContext) => {
      dispatchPendingRuntime({
        commandId,
        message,
        recoveryActions,
        type: "runtime_input.command_rejected",
      });
    },
    [],
  );

  const failRuntimeInputSubmit = useCallback(
    ({ commandId, message, recoveryActions }: RuntimeInputSubmitFailureContext) => {
      dispatchPendingRuntime({
        commandId,
        message,
        recoveryActions,
        type: "runtime_input.command_failed",
      });
    },
    [],
  );

  const hydrateRuntimeInputSnapshot = useCallback(
    ({
      activities = [],
      messages,
      sessionId,
      workspaceId,
    }: RuntimeInputSnapshotContext) => {
      dispatchPendingRuntime({
        activities,
        messages,
        sessionId,
        type: "snapshot.hydrated",
        workspaceId,
      });
    },
    [],
  );

  useEffect(() => {
    setRuntimeActivityItems([]);
    dispatchPendingRuntime({
      sessionId: activeSessionId,
      type: "runtime.reset_scope",
      workspaceId: activeWorkspaceId,
    });
  }, [activeSessionId, activeWorkspaceId]);

  return {
    acceptRuntimeInputSubmit,
    activeRuntimeInputMode,
    changeInputDraft,
    failRuntimeInputSubmit,
    hydrateRuntimeInputSnapshot,
    inputDraft,
    reconcileRuntimeInputSubmit,
    rejectRuntimeInputSubmit,
    resetInputDraft,
    runtimeActivityItems,
    setActiveRuntimeInputMode,
    setRuntimeActivityItems,
    startRuntimeInputSubmit,
  };
}
