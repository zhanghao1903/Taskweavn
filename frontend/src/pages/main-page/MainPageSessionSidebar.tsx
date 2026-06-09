import type { MouseEvent } from "react";
import { useEffect, useState } from "react";
import { Folder, FolderOpen } from "lucide-react";

import type { WorkspaceCatalogResult } from "../../shared/api/platoApi";
import type { SessionSummary, WorkspaceId } from "../../shared/api/types";
import { Button, Panel, Text } from "../../shared/components";
import { SessionLifecyclePanel } from "./SessionLifecyclePanel";
import {
  MainPageWorkspaceSwitcher,
  type MainPageWorkspaceRuntime,
} from "./MainPageWorkspaceSwitcher";
import type { MainPageController } from "./useMainPageController";
import styles from "./MainPage.module.css";

export type MainPageSessionSidebarProps = {
  activeSession: SessionSummary | null;
  activeWorkspaceId?: WorkspaceId | null;
  isCreatingSession: boolean;
  isDeletingSession: boolean;
  isRenamingSession: boolean;
  onCancelSessionDialog: () => void;
  onChangeSessionDialogDraft: (draftName: string) => void;
  onCreateSession: (workspaceId?: WorkspaceId | null) => void;
  onDeleteSession: (session: SessionSummary) => void;
  onRenameSession: (session: SessionSummary) => void;
  onSelectSession: (session: SessionSummary, currentSessionId: string) => void;
  onSubmitSessionDialog: () => void;
  sessionDialog: MainPageController["sessionDialog"];
  sessions: SessionSummary[];
  workspaceCatalog?: WorkspaceCatalogResult | null;
  workspaceRuntime?: MainPageWorkspaceRuntime | null;
};

type SessionContextMenuState = {
  session: SessionSummary;
  x: number;
  y: number;
};

export function MainPageSessionSidebar({
  activeSession,
  activeWorkspaceId = null,
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
  workspaceCatalog = null,
  workspaceRuntime = null,
}: MainPageSessionSidebarProps) {
  const [contextMenu, setContextMenu] =
    useState<SessionContextMenuState | null>(null);
  const workspaceBridge =
    workspaceRuntime?.bridge ?? globalThis.window?.platoElectronWorkspace ?? null;

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
    onSelectSession(session, activeSession?.id ?? session.id);
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

  function isActiveSession(session: SessionSummary): boolean {
    if (activeSession === null || session.id !== activeSession.id) {
      return false;
    }
    return (
      session.workspaceId === undefined ||
      activeWorkspaceId === null ||
      session.workspaceId === activeWorkspaceId
    );
  }

  const catalogTree =
    workspaceCatalog === null ? null : (
      <div className={styles.workspaceExplorer} aria-label="Workspaces">
        {workspaceCatalog.workspaces.map((workspace) => {
          const isActiveWorkspace =
            activeWorkspaceId === workspace.workspaceId ||
            (activeWorkspaceId === null && workspace.isCurrent);
          const workspaceClassName = isActiveWorkspace
            ? styles.workspaceTreeCurrent
            : styles.workspaceTreeRow;
          const canCreateSession = workspace.status === "available";

          return (
            <div className={styles.workspaceTreeGroup} key={workspace.workspaceId}>
              <div className={workspaceClassName} aria-current={isActiveWorkspace}>
                <Folder
                  className={styles.workspaceSwitcherIcon}
                  size={18}
                  aria-hidden="true"
                />
                <div className={styles.workspaceTreeCurrentLabel}>
                  <span>
                    <Text as="span" className={styles.workspaceSwitcherEyebrow}>
                      Workspace
                    </Text>
                    <strong>{workspace.label}</strong>
                  </span>
                  {workspace.status !== "available" ? (
                    <Text as="span" variant="muted">
                      {workspace.status}
                    </Text>
                  ) : null}
                </div>
                <div className={styles.workspaceTreeCurrentActions}>
                  <Button
                    disabled={isCreatingSession || !canCreateSession}
                    onClick={() => onCreateSession(workspace.workspaceId)}
                    size="sm"
                  >
                    {isCreatingSession && isActiveWorkspace ? "Creating" : "New"}
                  </Button>
                </div>
              </div>

              {workspace.recentSessions.length > 0 ? (
                <div className={styles.sessionTreeList}>
                  {workspace.recentSessions.map((session) => (
                    <button
                      className={
                        isActiveSession(session)
                          ? styles.activeNavItem
                          : styles.navItem
                      }
                      key={`${workspace.workspaceId}:${session.id}`}
                      onContextMenu={(event) => openContextMenu(event, session)}
                      onDoubleClick={() => renameFromContextMenu(session)}
                      onClick={() =>
                        onSelectSession(session, activeSession?.id ?? session.id)
                      }
                      type="button"
                    >
                      {session.name}
                    </button>
                  ))}
                </div>
              ) : (
                <Text className={styles.workspaceSwitcherNotice} variant="muted">
                  No sessions
                </Text>
              )}
            </div>
          );
        })}
        {workspaceBridge ? (
          <button
            className={styles.workspaceTreeRow}
            onClick={() => {
              void workspaceBridge.chooseWorkspace();
            }}
            type="button"
          >
            <FolderOpen
              className={styles.workspaceSwitcherIcon}
              size={18}
              aria-hidden="true"
            />
            <span>Open or add workspace</span>
          </button>
        ) : null}
      </div>
    );

  return (
    <Panel
      as="aside"
      className={styles.sidebar}
      aria-label="Workspace sessions"
    >
      <div className={styles.workspaceSessionTree}>
        {catalogTree ?? (
          <MainPageWorkspaceSwitcher
            actions={
              <Button
                disabled={isCreatingSession}
                onClick={() => onCreateSession()}
                size="sm"
              >
                {isCreatingSession ? "Creating" : "New"}
              </Button>
            }
            runtime={workspaceRuntime}
          >
            <div className={styles.sessionTreeList}>
              {sessions.map((session) => (
                <button
                  className={
                    activeSession !== null && session.id === activeSession.id
                      ? styles.activeNavItem
                      : styles.navItem
                  }
                  key={session.id}
                  onContextMenu={(event) => openContextMenu(event, session)}
                  onDoubleClick={() => renameFromContextMenu(session)}
                  onClick={() =>
                    onSelectSession(session, activeSession?.id ?? session.id)
                  }
                  type="button"
                >
                  {session.name}
                </button>
              ))}
            </div>
          </MainPageWorkspaceSwitcher>
        )}
      </div>
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
            disabled={
              activeSession !== null && contextMenu.session.id === activeSession.id
            }
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
