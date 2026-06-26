import { useCallback, useState } from "react";

import type { SessionSummary } from "../../shared/api/types";

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

export function useMainPageSessionDialogState() {
  const [sessionDialog, setSessionDialog] = useState<SessionLifecycleDialog>({
    mode: "idle",
  });

  function changeSessionDialogDraft(draftName: string) {
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

  const closeSessionDialog = useCallback(() => {
    setSessionDialog({ mode: "idle" });
  }, []);

  function openCreateSessionDialog() {
    setSessionDialog({
      draftName: "New session",
      error: null,
      mode: "create",
    });
  }

  function openDeleteSessionDialog(session: SessionSummary) {
    setSessionDialog({
      error: null,
      mode: "delete",
      session,
    });
  }

  function openRenameSessionDialog(session: SessionSummary) {
    setSessionDialog({
      draftName: session.name,
      error: null,
      mode: "rename",
      session,
    });
  }

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

  return {
    changeSessionDialogDraft,
    closeSessionDialog,
    openCreateSessionDialog,
    openDeleteSessionDialog,
    openRenameSessionDialog,
    sessionDialog,
    setSessionDialogError,
  };
}
