import { useEffect, useMemo, useState, type ReactNode } from "react";

import { Button, Text } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import styles from "./SettingsDataManagementTab.module.css";

type LifecycleState =
  | { kind: "idle" | "loading" }
  | { kind: "confirm_delete"; workspace: PlatoWorkspaceEntrySummary }
  | { kind: "error"; message: string };

export function SettingsDataManagementTab({
  workspaceBridge,
}: {
  workspaceBridge?: PlatoElectronWorkspaceBridge | null;
}) {
  const uiText = useUiText();
  const bridge = workspaceBridge ?? globalThis.window?.platoElectronWorkspace ?? null;
  const [workspaceState, setWorkspaceState] =
    useState<PlatoWorkspaceEntryState | null>(null);
  const [lifecycleState, setLifecycleState] =
    useState<LifecycleState>({ kind: "loading" });

  useEffect(() => {
    if (bridge === null) {
      setLifecycleState({ kind: "idle" });
      return undefined;
    }
    let isMounted = true;
    setLifecycleState({ kind: "loading" });
    void bridge
      .getState()
      .then((state) => {
        if (isMounted) {
          setWorkspaceState(state);
          setLifecycleState({ kind: "idle" });
        }
      })
      .catch(() => {
        if (isMounted) {
          setLifecycleState({
            kind: "error",
            message: uiText.workspace.messages.lifecycleActionFailed,
          });
        }
      });
    return () => {
      isMounted = false;
    };
  }, [bridge, uiText.workspace.messages.lifecycleActionFailed]);

  const activeWorkspaces = useMemo(
    () => activeWorkspaceSummaries(workspaceState),
    [workspaceState],
  );
  const archivedWorkspaces = workspaceState?.archivedWorkspaces ?? [];
  const isPending = lifecycleState.kind === "loading";

  async function runLifecycleAction(
    action:
      | (() => Promise<PlatoWorkspaceLifecycleResult> | undefined)
      | undefined,
  ) {
    if (!action) {
      setLifecycleState({
        kind: "error",
        message: uiText.workspace.messages.lifecycleActionFailed,
      });
      return;
    }
    setLifecycleState({ kind: "loading" });
    try {
      const result = await action();
      if (result === undefined) {
        setLifecycleState({
          kind: "error",
          message: uiText.workspace.messages.lifecycleActionFailed,
        });
        return;
      }
      setWorkspaceState(result.state);
      setLifecycleState(
        result.status === "ok"
          ? { kind: "idle" }
          : {
              kind: "error",
              message:
                result.error ?? uiText.workspace.messages.lifecycleActionFailed,
            },
      );
    } catch {
      setLifecycleState({
        kind: "error",
        message: uiText.workspace.messages.lifecycleActionFailed,
      });
    }
  }

  if (bridge === null) {
    return (
      <section className={styles.sectionStack} aria-label={uiText.workspace.labels.dataManagement}>
        <Text variant="muted">{uiText.workspace.messages.bridgeUnavailable}</Text>
      </section>
    );
  }

  return (
    <section className={styles.sectionStack} aria-label={uiText.workspace.labels.dataManagement}>
      {lifecycleState.kind === "error" ? (
        <p className={styles.error} role="alert">
          {lifecycleState.message}
        </p>
      ) : null}
      <WorkspaceSection
        actions={(workspace) => (
          <>
            <Button
              disabled={isPending || bridge.archiveWorkspace === undefined}
              onClick={() =>
                void runLifecycleAction(() => bridge.archiveWorkspace?.(workspace.id))
              }
              size="sm"
            >
              {uiText.workspace.actions.archiveWorkspace}
            </Button>
            <Button
              disabled={isPending || bridge.deleteWorkspaceData === undefined}
              onClick={() =>
                setLifecycleState({ kind: "confirm_delete", workspace })
              }
              size="sm"
              variant="secondary"
            >
              {uiText.workspace.actions.deletePlatoData}
            </Button>
          </>
        )}
        emptyText={uiText.workspace.messages.noWorkspaceData}
        helpText={uiText.workspace.messages.archiveHelp}
        title={uiText.workspace.labels.activeWorkspaces}
        workspaces={activeWorkspaces}
      />
      <WorkspaceSection
        actions={(workspace) => (
          <>
            <Button
              disabled={isPending || bridge.restoreWorkspace === undefined}
              onClick={() =>
                void runLifecycleAction(() => bridge.restoreWorkspace?.(workspace.id))
              }
              size="sm"
            >
              {uiText.workspace.actions.restoreWorkspace}
            </Button>
            <Button
              disabled={isPending || bridge.deleteWorkspaceData === undefined}
              onClick={() =>
                setLifecycleState({ kind: "confirm_delete", workspace })
              }
              size="sm"
              variant="secondary"
            >
              {uiText.workspace.actions.deletePlatoData}
            </Button>
          </>
        )}
        emptyText={uiText.workspace.messages.noArchivedWorkspaces}
        helpText={uiText.workspace.messages.restoreHelp}
        title={uiText.workspace.labels.archivedWorkspaces}
        workspaces={archivedWorkspaces}
      />
      {lifecycleState.kind === "confirm_delete" ? (
        <div className={styles.confirmPanel} role="alertdialog">
          <Text variant="muted">
            {uiText.workspace.messages.deletePlatoDataConfirmation({
              name: lifecycleState.workspace.name,
            })}
          </Text>
          <Text variant="muted">
            {uiText.workspace.messages.deletePlatoDataHelp}
          </Text>
          <div className={styles.confirmActions}>
            <Button onClick={() => setLifecycleState({ kind: "idle" })}>
              {uiText.workspace.actions.cancelDelete}
            </Button>
            <Button
              onClick={() =>
                void runLifecycleAction(() =>
                  bridge.deleteWorkspaceData?.(lifecycleState.workspace.id),
                )
              }
              variant="primary"
            >
              {uiText.workspace.actions.confirmDeletePlatoData}
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function WorkspaceSection({
  actions,
  emptyText,
  helpText,
  title,
  workspaces,
}: {
  actions: (workspace: PlatoWorkspaceEntrySummary) => ReactNode;
  emptyText: string;
  helpText: string;
  title: string;
  workspaces: readonly PlatoWorkspaceEntrySummary[];
}) {
  return (
    <section className={styles.section}>
      <div className={styles.sectionHeader}>
        <div>
          <h2>{title}</h2>
          <p>{helpText}</p>
        </div>
      </div>
      {workspaces.length === 0 ? (
        <p className={styles.empty}>{emptyText}</p>
      ) : (
        <div className={styles.workspaceList}>
          {workspaces.map((workspace) => (
            <article className={styles.workspaceRow} key={workspace.id}>
              <div>
                <span className={styles.workspaceName}>{workspace.name}</span>
                <span className={styles.meta}>{workspace.pathLabel}</span>
              </div>
              <div className={styles.rowActions}>{actions(workspace)}</div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function activeWorkspaceSummaries(
  state: PlatoWorkspaceEntryState | null,
): PlatoWorkspaceEntrySummary[] {
  if (state === null) {
    return [];
  }
  const summaries = [
    ...(state.currentWorkspace === null ? [] : [state.currentWorkspace]),
    ...state.recentWorkspaces,
  ];
  const seen = new Set<string>();
  return summaries.filter((summary) => {
    if (seen.has(summary.id)) {
      return false;
    }
    seen.add(summary.id);
    return true;
  });
}
