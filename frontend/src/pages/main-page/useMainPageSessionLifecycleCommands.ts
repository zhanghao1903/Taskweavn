import { useMutation } from "@tanstack/react-query";

import type { WorkspaceId } from "../../shared/api/types";
import type { MainPageAdapter } from "./runtime/adapter";

type SnapshotRefetch = () => Promise<unknown>;

export type CreateSessionContext = {
  name: string;
  workspaceId: WorkspaceId | null;
};

export type RenameSessionContext = {
  name: string;
  sessionId: string;
  workspaceId: WorkspaceId | null;
};

export type DeleteSessionContext = {
  sessionId: string;
  workspaceId: WorkspaceId | null;
};

export type UseMainPageSessionLifecycleCommandsOptions = {
  adapter: MainPageAdapter;
  closeSessionDialog: () => void;
  refetchSnapshot: SnapshotRefetch;
  refetchWorkspaceCatalog: () => void;
  setActiveSessionId: (sessionId: string | null) => void;
  setActiveWorkspaceId: (workspaceId: WorkspaceId | null) => void;
  setSessionDialogError: (message: string) => void;
  setUiNotice: (notice: string | null) => void;
};

export function useMainPageSessionLifecycleCommands({
  adapter,
  closeSessionDialog,
  refetchSnapshot,
  refetchWorkspaceCatalog,
  setActiveSessionId,
  setActiveWorkspaceId,
  setSessionDialogError,
  setUiNotice,
}: UseMainPageSessionLifecycleCommandsOptions) {
  const createSessionMutation = useMutation({
    mutationFn: async ({ name, workspaceId }: CreateSessionContext) =>
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
      closeSessionDialog();
      refetchWorkspaceCatalog();
    },
  });

  const renameSessionMutation = useMutation({
    mutationFn: async ({
      name,
      sessionId,
      workspaceId,
    }: RenameSessionContext) =>
      adapter.renameSession({
        name,
        sessionId,
      }, workspaceId),
    onError: () => {
      setSessionDialogError("Rename session failed. Please retry.");
    },
    onSuccess: (result) => {
      setUiNotice(`Renamed session to ${result.session?.name ?? "new name"}.`);
      closeSessionDialog();
      refetchWorkspaceCatalog();
      void refetchSnapshot();
    },
  });

  const deleteSessionMutation = useMutation({
    mutationFn: async ({ sessionId, workspaceId }: DeleteSessionContext) =>
      adapter.deleteSession(sessionId, workspaceId),
    onError: () => {
      setSessionDialogError("Delete session failed. Please retry.");
    },
    onSuccess: (result) => {
      const nextSessionId = result.nextSessionId ?? null;
      setActiveSessionId(nextSessionId);
      setUiNotice("Session deleted.");
      closeSessionDialog();
      refetchWorkspaceCatalog();
    },
  });

  return {
    createSessionMutation,
    deleteSessionMutation,
    renameSessionMutation,
  };
}
