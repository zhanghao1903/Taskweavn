import type { MouseEvent } from "react";
import { useEffect, useState } from "react";

import type { SessionSummary } from "../../shared/api/types";
import { Button, Panel, Text } from "../../shared/components";
import { SessionLifecyclePanel } from "./SessionLifecyclePanel";
import type { MainPageController } from "./useMainPageController";
import styles from "./MainPage.module.css";

export type MainPageSessionSidebarProps = {
  activeSession: SessionSummary;
  isCreatingSession: boolean;
  isDeletingSession: boolean;
  isRenamingSession: boolean;
  onCancelSessionDialog: () => void;
  onChangeSessionDialogDraft: (draftName: string) => void;
  onCreateSession: () => void;
  onDeleteSession: (session: SessionSummary) => void;
  onRenameSession: (session: SessionSummary) => void;
  onSelectSession: (session: SessionSummary, currentSessionId: string) => void;
  onSubmitSessionDialog: () => void;
  sessionDialog: MainPageController["sessionDialog"];
  sessions: SessionSummary[];
};

type SessionContextMenuState = {
  session: SessionSummary;
  x: number;
  y: number;
};

export function MainPageSessionSidebar({
  activeSession,
  isCreatingSession,
  isDeletingSession,
  isRenamingSession,
  onCancelSessionDialog,
  onChangeSessionDialogDraft,
  onCreateSession,
  onDeleteSession,
  onRenameSession,
  onSelectSession,
  onSubmitSessionDialog,
  sessionDialog,
  sessions,
}: MainPageSessionSidebarProps) {
  const [contextMenu, setContextMenu] =
    useState<SessionContextMenuState | null>(null);

  useEffect(() => {
    if (contextMenu === null) {
      return undefined;
    }

    function closeContextMenu() {
      setContextMenu(null);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeContextMenu();
      }
    }

    window.addEventListener("click", closeContextMenu);
    window.addEventListener("contextmenu", closeContextMenu);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("click", closeContextMenu);
      window.removeEventListener("contextmenu", closeContextMenu);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [contextMenu]);

  function openContextMenu(
    event: MouseEvent<HTMLButtonElement>,
    session: SessionSummary,
  ) {
    event.preventDefault();
    event.stopPropagation();
    setContextMenu({
      session,
      x: event.clientX,
      y: event.clientY,
    });
  }

  function selectFromContextMenu(session: SessionSummary) {
    setContextMenu(null);
    onSelectSession(session, activeSession.id);
  }

  function renameFromContextMenu(session: SessionSummary) {
    setContextMenu(null);
    onRenameSession(session);
  }

  function deleteFromContextMenu(session: SessionSummary) {
    setContextMenu(null);
    onDeleteSession(session);
  }

  function copySessionId(session: SessionSummary) {
    setContextMenu(null);
    void navigator.clipboard?.writeText(session.id);
  }

  return (
    <Panel
      as="aside"
      className={styles.sidebar}
      aria-label="Workflow sessions"
    >
      <div className={styles.sidebarHeader}>
        <Text as="span" className={styles.sidebarTitle} variant="label">
          Workflow
        </Text>
        <Button
          disabled={isCreatingSession}
          onClick={onCreateSession}
          size="sm"
        >
          {isCreatingSession ? "Creating" : "New"}
        </Button>
      </div>
      <Text as="div" variant="eyebrow">
        Sessions
      </Text>
      {sessions.map((session) => (
        <button
          className={
            session.id === activeSession.id
              ? styles.activeNavItem
              : styles.navItem
          }
          key={session.id}
          onContextMenu={(event) => openContextMenu(event, session)}
          onDoubleClick={() => renameFromContextMenu(session)}
          onClick={() => onSelectSession(session, activeSession.id)}
          type="button"
        >
          {session.name}
        </button>
      ))}
      {contextMenu ? (
        <div
          aria-label="Session actions"
          className={styles.sessionContextMenu}
          onClick={(event) => event.stopPropagation()}
          onContextMenu={(event) => event.preventDefault()}
          role="menu"
          style={{
            left: contextMenu.x,
            top: contextMenu.y,
          }}
        >
          <button
            disabled={contextMenu.session.id === activeSession.id}
            onClick={() => selectFromContextMenu(contextMenu.session)}
            role="menuitem"
            type="button"
          >
            Open session
          </button>
          <button
            disabled={isRenamingSession}
            onClick={() => renameFromContextMenu(contextMenu.session)}
            role="menuitem"
            type="button"
          >
            Rename session
          </button>
          <button
            onClick={() => copySessionId(contextMenu.session)}
            role="menuitem"
            type="button"
          >
            Copy session ID
          </button>
          <div className={styles.sessionContextMenuDivider} />
          <button
            className={styles.dangerMenuItem}
            disabled={isDeletingSession}
            onClick={() => deleteFromContextMenu(contextMenu.session)}
            role="menuitem"
            type="button"
          >
            Delete session
          </button>
        </div>
      ) : null}
      <SessionLifecyclePanel
        dialog={sessionDialog}
        isCreatingSession={isCreatingSession}
        isDeletingSession={isDeletingSession}
        isRenamingSession={isRenamingSession}
        onCancel={onCancelSessionDialog}
        onChangeDraft={onChangeSessionDialogDraft}
        onSubmit={onSubmitSessionDialog}
      />
    </Panel>
  );
}
