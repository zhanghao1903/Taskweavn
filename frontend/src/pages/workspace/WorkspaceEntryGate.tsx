import { Clock, FolderOpen } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button, Panel, Text } from "../../shared/components";
import { workspaceGitSelectionOptionsFromPreference } from "../../shared/workspace/workspaceGitPreference";
import styles from "./WorkspaceEntryGate.module.css";

type WorkspaceEntryBridge = PlatoElectronWorkspaceBridge;
type WorkspaceEntryState = PlatoWorkspaceEntryState;
type WorkspaceSelectionResult = PlatoWorkspaceSelectionResult;

export type WorkspaceEntryGateProps = {
  bridge?: WorkspaceEntryBridge | null;
};

const unavailableState: WorkspaceEntryState = {
  currentWorkspace: null,
  error: "Workspace selection is only available in the Plato desktop app.",
  recentWorkspaces: [],
  status: "failed",
};

export function WorkspaceEntryGate({ bridge }: WorkspaceEntryGateProps) {
  const workspaceBridge = useMemo(
    () => bridge ?? globalThis.window?.platoElectronWorkspace ?? null,
    [bridge],
  );
  const [state, setState] = useState<WorkspaceEntryState | null>(null);
  const [isChoosing, setIsChoosing] = useState(false);

  useEffect(() => {
    let isMounted = true;
    if (workspaceBridge === null) {
      setState(unavailableState);
      return;
    }

    void workspaceBridge
      .getState()
      .then((nextState) => {
        if (isMounted) {
          setState(nextState);
        }
      })
      .catch(() => {
        if (isMounted) {
          setState({
            ...unavailableState,
            error: "Workspace selection is unavailable.",
          });
        }
      });

    return () => {
      isMounted = false;
    };
  }, [workspaceBridge]);

  const isBusy = isChoosing || state?.status === "starting";

  async function chooseWorkspace() {
    if (workspaceBridge === null) {
      setState(unavailableState);
      return;
    }
    await runSelection(() =>
      workspaceBridge.chooseWorkspace(workspaceGitSelectionOptionsFromPreference()),
    );
  }

  async function openRecentWorkspace(id: string) {
    if (workspaceBridge === null) {
      setState(unavailableState);
      return;
    }
    await runSelection(() =>
      workspaceBridge.useWorkspace(id, workspaceGitSelectionOptionsFromPreference()),
    );
  }

  async function runSelection(
    action: () => Promise<WorkspaceSelectionResult>,
  ) {
    setIsChoosing(true);
    setState((current) =>
      current === null ? current : { ...current, error: null, status: "starting" },
    );
    try {
      const result = await action();
      setState(result.state);
    } catch {
      setState({
        ...(state ?? unavailableState),
        error: "Could not open that workspace.",
        status: "failed",
      });
    } finally {
      setIsChoosing(false);
    }
  }

  return (
    <main className={styles.page}>
      <Panel aria-label="Workspace selection" className={styles.panel}>
        <header className={styles.header}>
          <span className={styles.eyebrow}>Workspace</span>
          <h1>Open a workspace</h1>
          <p>
            Choose the local folder Plato should use for this project. Settings,
            sessions, audit records, and diagnostics stay tied to that workspace.
          </p>
        </header>

        {state?.error ? (
          <div className={styles.error} role="alert">
            {state.error}
          </div>
        ) : null}

        <div className={styles.actions}>
          <Button disabled={isBusy} onClick={chooseWorkspace} variant="primary">
            <FolderOpen size={18} aria-hidden="true" />
            Open workspace
          </Button>
        </div>

        {state === null ? (
          <Text variant="muted">Loading workspace state.</Text>
        ) : state.recentWorkspaces.length > 0 ? (
          <section className={styles.recentSection} aria-label="Recent workspaces">
            <Text as="strong" variant="label">
              Recent
            </Text>
            <div className={styles.recentList}>
              {state.recentWorkspaces.map((workspace) => (
                <button
                  className={styles.recentButton}
                  disabled={isBusy}
                  key={workspace.id}
                  onClick={() => void openRecentWorkspace(workspace.id)}
                  type="button"
                >
                  <Clock size={18} aria-hidden="true" />
                  <span className={styles.recentCopy}>
                    <strong>{workspace.name}</strong>
                    <Text as="span" variant="muted">
                      {workspace.pathLabel}
                    </Text>
                  </span>
                </button>
              ))}
            </div>
          </section>
        ) : null}
      </Panel>
    </main>
  );
}
