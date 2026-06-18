import type { MouseEvent, ReactNode } from "react";
import { useEffect, useState } from "react";
import { Folder, FolderOpen } from "lucide-react";

import { navigateApp } from "../../app/navigation";
import type { WorkspaceCatalogResult } from "../../shared/api/platoApi";
import type { SessionSummary, WorkspaceId } from "../../shared/api/types";
import { Button, Panel, Text } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import { workspaceGitSelectionOptionsFromPreference } from "../../shared/workspace/workspaceGitPreference";
import { buildSettingsRoute } from "../settings/settingsRouteModel";
import { SessionLifecyclePanel } from "./SessionLifecyclePanel";
import {
  MainPageWorkspaceSwitcher,
  type MainPageWorkspaceRuntime,
} from "./MainPageWorkspaceSwitcher";
import { PlatoProductMark } from "./PlatoProductMark";
import type { MainPageController } from "./useMainPageController";
import styles from "./MainPage.module.css";

export type MainPageSessionSidebarProps = {
  activeSession: SessionSummary | null;
  activeWorkspaceId?: WorkspaceId | null;
  brandLabel?: string;
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
  utilitySlot?: ReactNode;
  workspaceCatalog?: WorkspaceCatalogResult | null;
  workspaceRuntime?: MainPageWorkspaceRuntime | null;
};

type SessionContextMenuState = {
  session: SessionSummary;
  x: number;
  y: number;
};

type WorkspaceCatalogEntry = WorkspaceCatalogResult["workspaces"][number];

type WorkspaceContextMenuState = {
  workspace: WorkspaceCatalogEntry;
  x: number;
  y: number;
};

const CONTEXT_MENU_VIEWPORT_GAP = 8;
const SESSION_CONTEXT_MENU_WIDTH = 220;
const SESSION_CONTEXT_MENU_HEIGHT = 188;

export function MainPageSessionSidebar({
  activeSession,
  activeWorkspaceId = null,
  brandLabel = "Plato",
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
  utilitySlot = null,
  workspaceCatalog = null,
  workspaceRuntime = null,
}: MainPageSessionSidebarProps) {
  const uiText = useUiText();
  const [contextMenu, setContextMenu] =
    useState<SessionContextMenuState | null>(null);
  const [workspaceContextMenu, setWorkspaceContextMenu] =
    useState<WorkspaceContextMenuState | null>(null);
  const [hiddenWorkspaceIds, setHiddenWorkspaceIds] = useState<Set<string>>(
    () => new Set(),
  );
  const workspaceBridge =
    workspaceRuntime?.bridge ?? globalThis.window?.platoElectronWorkspace ?? null;

  useEffect(() => {
    if (contextMenu === null && workspaceContextMenu === null) {
      return undefined;
    }

    function closeContextMenu() {
      setContextMenu(null);
      setWorkspaceContextMenu(null);
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
  }, [contextMenu, workspaceContextMenu]);

  function openContextMenu(
    event: MouseEvent<HTMLElement>,
    session: SessionSummary,
  ) {
    event.preventDefault();
    event.stopPropagation();
    const position = fitContextMenuToViewport(event.clientX, event.clientY);
    setWorkspaceContextMenu(null);
    setContextMenu({
      session,
      x: position.x,
      y: position.y,
    });
  }

  function openWorkspaceContextMenu(
    event: MouseEvent<HTMLElement>,
    workspace: WorkspaceCatalogEntry,
  ) {
    event.preventDefault();
    event.stopPropagation();
    const position = fitContextMenuToViewport(event.clientX, event.clientY);
    setContextMenu(null);
    setWorkspaceContextMenu({
      workspace,
      x: position.x,
      y: position.y,
    });
  }

  function openWorkspaceManagement() {
    const returnTo = `${globalThis.location.pathname}${globalThis.location.search}`;
    navigateApp(buildSettingsRoute({ returnTo, tab: "data" }));
  }

  async function archiveWorkspace(workspace: WorkspaceCatalogEntry) {
    setWorkspaceContextMenu(null);
    const result = await workspaceBridge?.archiveWorkspace?.(workspace.workspaceId);
    if (result?.status === "ok") {
      setHiddenWorkspaceIds((current) => {
        const next = new Set(current);
        next.add(workspace.workspaceId);
        return next;
      });
    }
  }

  async function deleteWorkspaceData(workspace: WorkspaceCatalogEntry) {
    setWorkspaceContextMenu(null);
    const confirmed = globalThis.confirm?.(
      uiText.workspace.messages.deletePlatoDataConfirmation({
        name: workspace.label,
      }),
    );
    if (confirmed === false) {
      return;
    }
    await workspaceBridge?.deleteWorkspaceData?.(workspace.workspaceId);
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
    workspaceCatalog === null || !Array.isArray(workspaceCatalog.workspaces) ? null : (
      <div
        className={styles.workspaceExplorer}
        aria-label={uiText.workspace.labels.workspaces}
      >
        {workspaceCatalog.workspaces
          .filter((workspace) => !hiddenWorkspaceIds.has(workspace.workspaceId))
          .map((workspace) => {
            const isActiveWorkspace =
              activeWorkspaceId === workspace.workspaceId ||
              (activeWorkspaceId === null && workspace.isCurrent);
            const workspaceClassName = isActiveWorkspace
              ? styles.workspaceTreeCurrent
              : styles.workspaceTreeRow;
            const canCreateSession = workspace.status === "available";

            return (
              <div className={styles.workspaceTreeGroup} key={workspace.workspaceId}>
                <div
                  className={workspaceClassName}
                  aria-current={isActiveWorkspace}
                  onContextMenu={(event) =>
                    openWorkspaceContextMenu(event, workspace)
                  }
                >
                  <Folder
                    className={styles.workspaceSwitcherIcon}
                    size={18}
                    aria-hidden="true"
                  />
                  <div className={styles.workspaceTreeCurrentLabel}>
                    <span>
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
                      {isCreatingSession && isActiveWorkspace
                        ? uiText.main.states.creatingSession
                        : uiText.main.actions.newSession}
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
                    {uiText.main.labels.noSessions}
                  </Text>
                )}
              </div>
            );
          })}
        {workspaceBridge ? (
          <button
            className={styles.workspaceTreeRow}
            onClick={() => {
              void workspaceBridge.chooseWorkspace(
                workspaceGitSelectionOptionsFromPreference(),
              );
            }}
            type="button"
          >
            <FolderOpen
              className={styles.workspaceSwitcherIcon}
              size={18}
              aria-hidden="true"
            />
            <span>{uiText.workspace.actions.openOrAddWorkspace}</span>
          </button>
        ) : null}
        <button
          className={styles.workspaceTreeRow}
          onClick={openWorkspaceManagement}
          type="button"
        >
          <FolderOpen
            className={styles.workspaceSwitcherIcon}
            size={18}
            aria-hidden="true"
          />
          <span>{uiText.workspace.actions.workspaceManagement}</span>
        </button>
      </div>
    );

  return (
    <Panel
      as="aside"
      className={styles.sidebar}
      aria-label={uiText.main.labels.workspaceSessions}
    >
      <div className={styles.railBrandBlock} aria-label={brandLabel}>
        <PlatoProductMark className={styles.railBrandMark} />
        <div className={styles.railBrandCopy}>
          <div className={styles.railBrandName}>Plato</div>
        </div>
      </div>
      <div className={styles.workspaceSessionTree}>
        {catalogTree ?? (
          <MainPageWorkspaceSwitcher
            actions={
              <Button
                disabled={isCreatingSession}
                onClick={() => onCreateSession()}
                size="sm"
              >
                {isCreatingSession
                  ? uiText.main.states.creatingSession
                  : uiText.main.actions.newSession}
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
          aria-label={uiText.main.labels.sessionActions}
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
            {uiText.main.actions.openSession}
          </button>
          <button
            disabled={isRenamingSession}
            onClick={() => renameFromContextMenu(contextMenu.session)}
            role="menuitem"
            type="button"
          >
            {uiText.main.actions.renameSession}
          </button>
          <button
            onClick={() => copySessionId(contextMenu.session)}
            role="menuitem"
            type="button"
          >
            {uiText.main.actions.copySessionId}
          </button>
          <div className={styles.sessionContextMenuDivider} />
          <button
            className={styles.dangerMenuItem}
            disabled={isDeletingSession}
            onClick={() => deleteFromContextMenu(contextMenu.session)}
            role="menuitem"
            type="button"
          >
            {uiText.main.actions.deleteSession}
          </button>
        </div>
      ) : null}
      {workspaceContextMenu ? (
        <div
          aria-label={uiText.workspace.actions.openWorkspaceMenu}
          className={styles.sessionContextMenu}
          onClick={(event) => event.stopPropagation()}
          onContextMenu={(event) => event.preventDefault()}
          role="menu"
          style={{
            left: workspaceContextMenu.x,
            top: workspaceContextMenu.y,
          }}
        >
          <button
            disabled={workspaceBridge?.archiveWorkspace === undefined}
            onClick={() => void archiveWorkspace(workspaceContextMenu.workspace)}
            role="menuitem"
            type="button"
          >
            {uiText.workspace.actions.archiveWorkspace}
          </button>
          <div className={styles.sessionContextMenuDivider} />
          <button
            className={styles.dangerMenuItem}
            disabled={workspaceBridge?.deleteWorkspaceData === undefined}
            onClick={() =>
              void deleteWorkspaceData(workspaceContextMenu.workspace)
            }
            role="menuitem"
            type="button"
          >
            {uiText.workspace.actions.deletePlatoData}
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
      {utilitySlot ? (
        <div className={styles.railUtilitySlot}>{utilitySlot}</div>
      ) : null}
    </Panel>
  );
}

function fitContextMenuToViewport(clientX: number, clientY: number) {
  const viewportWidth = globalThis.window?.innerWidth ?? 0;
  const viewportHeight = globalThis.window?.innerHeight ?? 0;
  const maxX = Math.max(
    CONTEXT_MENU_VIEWPORT_GAP,
    viewportWidth - SESSION_CONTEXT_MENU_WIDTH - CONTEXT_MENU_VIEWPORT_GAP,
  );
  const maxY = Math.max(
    CONTEXT_MENU_VIEWPORT_GAP,
    viewportHeight - SESSION_CONTEXT_MENU_HEIGHT - CONTEXT_MENU_VIEWPORT_GAP,
  );

  return {
    x: Math.max(CONTEXT_MENU_VIEWPORT_GAP, Math.min(clientX, maxX)),
    y: Math.max(CONTEXT_MENU_VIEWPORT_GAP, Math.min(clientY, maxY)),
  };
}
