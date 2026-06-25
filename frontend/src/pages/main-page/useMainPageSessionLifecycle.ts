import { useMutation } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import type { SessionSummary, WorkspaceId } from "../../shared/api/types";
import type {
  MainPageAdapter,
  MainPageRuntimeSnapshot,
} from "./runtime/adapter";

export type SessionLifecycleDialog =
  | {
      mode: "idle";
    }
  | {
      draftName: string;
      error: string | null;
      mode: "create";
    }
  | {
      draftName: string;
      error: string | null;
      mode: "rename";
      session: SessionSummary;
    }
  | {
      error: string | null;
      mode: "delete";
      session: SessionSummary;
    };

export type UseMainPageSessionLifecycleOptions = {
  activeWorkspaceId: WorkspaceId | null;
  adapter: MainPageAdapter;
  getSnapshotData: () => MainPageRuntimeSnapshot | undefined;
  refetchSnapshot: () => Promise<unknown>;
  refetchWorkspaceCatalog: () => void;
  setActiveSessionId: (sessionId: string | null) => void;
  setActiveWorkspaceId: (workspaceId: WorkspaceId | null) => void;
  setUiNotice: (notice: string | null) => void;
};

export type MainPageSessionLifecycleController = {
  isCreatingSession: boolean;
  isDeletingSession: boolean;
  isRenamingSession: boolean;
  resetSessionDialog: () => void;
  resetSessionLifecycle: () => void;
  sessionDialog: SessionLifecycleDialog;
  actions: {
    cancelSessionDialog: () => void;
    changeSessionDialogDraft: (draftName: string) => void;
    createSession: (workspaceId?: WorkspaceId | null) => void;
    deleteSession: (session: SessionSummary) => void;
    renameSession: (session: SessionSummary) => void;
    submitSessionDialog: () => void;
  };
};

export function useMainPageSessionLifecycle({
  activeWorkspaceId,
  adapter,
  getSnapshotData,
  refetchSnapshot,
  refetchWorkspaceCatalog,
  setActiveSessionId,
  setActiveWorkspaceId,
  setUiNotice,
}: UseMainPageSessionLifecycleOptions): MainPageSessionLifecycleController {
  const [sessionDialog, setSessionDialog] = useState<SessionLifecycleDialog>({
    mode: "idle",
  });

  function setSessionDialogError(message: string) {
    setSessionDialog((current) => {
      if (current.mode === "idle") {
        return current;
      }

      return {
        ...current,
        error: message,
      };
    });
  }

  const createSessionMutation = useMutation({
    mutationFn: async ({
      name,
      workspaceId,
    }: {
      name: string;
      workspaceId: WorkspaceId | null;
    }) =>
      adapter.createSession(
        {
          name,
        },
        workspaceId,
      ),
    onError: () => {
      setSessionDialogError("Create session failed. Please retry.");
    },
    onSuccess: (result) => {
      const nextSessionId = result.sessionId ?? result.session?.id ?? null;
      if (nextSessionId === null) {
        setSessionDialogError("Created session was unavailable. Please retry.");
        return;
      }

      if (result.session?.workspaceId) {
        setActiveWorkspaceId(result.session.workspaceId);
      }
      setActiveSessionId(nextSessionId);
      setUiNotice(`Created session ${result.session?.name ?? nextSessionId}.`);
      setSessionDialog({ mode: "idle" });
      refetchWorkspaceCatalog();
    },
  });

  const renameSessionMutation = useMutation({
    mutationFn: async ({
      name,
      sessionId,
      workspaceId,
    }: {
      name: string;
      sessionId: string;
      workspaceId: WorkspaceId | null;
    }) =>
      adapter.renameSession(
        {
          name,
          sessionId,
        },
        workspaceId,
      ),
    onError: () => {
      setSessionDialogError("Rename session failed. Please retry.");
    },
    onSuccess: (result) => {
      setUiNotice(`Renamed session to ${result.session?.name ?? "new name"}.`);
      setSessionDialog({ mode: "idle" });
      refetchWorkspaceCatalog();
      void refetchSnapshot();
    },
  });

  const deleteSessionMutation = useMutation({
    mutationFn: async ({
      sessionId,
      workspaceId,
    }: {
      sessionId: string;
      workspaceId: WorkspaceId | null;
    }) => adapter.deleteSession(sessionId, workspaceId),
    onError: () => {
      setSessionDialogError("Delete session failed. Please retry.");
    },
    onSuccess: (result) => {
      const nextSessionId = result.nextSessionId ?? null;
      setActiveSessionId(nextSessionId);
      setUiNotice("Session deleted.");
      setSessionDialog({ mode: "idle" });
      refetchWorkspaceCatalog();
    },
  });

  const resetSessionDialog = useCallback(() => {
    setSessionDialog({ mode: "idle" });
  }, []);

  function resetSessionLifecycle() {
    setSessionDialog({ mode: "idle" });
    createSessionMutation.reset();
    renameSessionMutation.reset();
    deleteSessionMutation.reset();
  }

  function handleCreateSession(workspaceId?: WorkspaceId | null) {
    const targetWorkspaceId = workspaceId ?? activeWorkspaceId;
    if (targetWorkspaceId !== activeWorkspaceId) {
      setActiveWorkspaceId(targetWorkspaceId ?? null);
    }
    if (!getSnapshotData()) {
      createSessionMutation.mutate({
        name: "New session",
        workspaceId: targetWorkspaceId ?? null,
      });
      return;
    }

    setSessionDialog({
      draftName: "New session",
      error: null,
      mode: "create",
    });
  }

  function handleRenameSession(session: SessionSummary) {
    setSessionDialog({
      draftName: session.name,
      error: null,
      mode: "rename",
      session,
    });
  }

  function handleDeleteSession(session: SessionSummary) {
    setSessionDialog({
      error: null,
      mode: "delete",
      session,
    });
  }

  function handleSessionDialogDraftChange(draftName: string) {
    setSessionDialog((current) => {
      if (current.mode !== "create" && current.mode !== "rename") {
        return current;
      }

      return {
        ...current,
        draftName,
        error: null,
      };
    });
  }

  function handleSessionDialogCancel() {
    if (
      createSessionMutation.isPending ||
      renameSessionMutation.isPending ||
      deleteSessionMutation.isPending
    ) {
      return;
    }

    setSessionDialog({ mode: "idle" });
  }

  function handleSessionDialogSubmit() {
    if (sessionDialog.mode === "idle") {
      return;
    }

    if (sessionDialog.mode === "delete") {
      setUiNotice(null);
      deleteSessionMutation.mutate({
        sessionId: sessionDialog.session.id,
        workspaceId: sessionDialog.session.workspaceId ?? activeWorkspaceId,
      });
      return;
    }

    const trimmed = sessionDialog.draftName.trim();
    if (!trimmed) {
      setSessionDialogError("Session name must not be empty.");
      return;
    }

    setUiNotice(null);

    if (sessionDialog.mode === "create") {
      createSessionMutation.mutate({
        name: trimmed,
        workspaceId: activeWorkspaceId,
      });
      return;
    }

    renameSessionMutation.mutate({
      name: trimmed,
      sessionId: sessionDialog.session.id,
      workspaceId: sessionDialog.session.workspaceId ?? activeWorkspaceId,
    });
  }

  return {
    isCreatingSession: createSessionMutation.isPending,
    isDeletingSession: deleteSessionMutation.isPending,
    isRenamingSession: renameSessionMutation.isPending,
    resetSessionDialog,
    resetSessionLifecycle,
    sessionDialog,
    actions: {
      cancelSessionDialog: handleSessionDialogCancel,
      changeSessionDialogDraft: handleSessionDialogDraftChange,
      createSession: handleCreateSession,
      deleteSession: handleDeleteSession,
      renameSession: handleRenameSession,
      submitSessionDialog: handleSessionDialogSubmit,
    },
  };
}
