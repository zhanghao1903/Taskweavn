import { Clock, Folder, FolderOpen } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { Text } from "../../shared/components";
import { useUiText, type UiTextCatalog } from "../../shared/ui-text";
import styles from "./MainPage.module.css";

export type MainPageWorkspaceRuntime = {
  bridge: PlatoElectronWorkspaceBridge | null;
  currentWorkspace: PlatoWorkspaceEntrySummary | null;
  isRequired: boolean;
};

export type MainPageWorkspaceSwitcherProps = {
  actions?: ReactNode;
  children?: ReactNode;
  runtime?: MainPageWorkspaceRuntime | null;
};

export function MainPageWorkspaceSwitcher({
  actions = null,
  children = null,
  runtime = null,
}: MainPageWorkspaceSwitcherProps) {
  const uiText = useUiText();
  const bridge = runtime?.bridge ?? globalThis.window?.platoElectronWorkspace ?? null;
  const runtimeWorkspace =
    runtime?.currentWorkspace ?? globalThis.window?.platoRuntimeConfig?.workspace ?? null;
  const [state, setState] = useState<PlatoWorkspaceEntryState | null>(null);
  const [isPending, setIsPending] = useState(false);

  const currentWorkspace = state?.currentWorkspace ?? runtimeWorkspace;
  const recentWorkspaces = state?.recentWorkspaces ?? [];
  const canSwitch = bridge !== null;
  const isBusy = isPending || state?.status === "starting";

  useEffect(() => {
    if (bridge === null) {
      return undefined;
    }

    let isMounted = true;
    void bridge
      .getState()
      .then((nextState) => {
        if (isMounted) {
          setState(nextState);
        }
      })
      .catch(() => {
        if (isMounted) {
          setState(unavailableState(uiText));
        }
      });

    return () => {
      isMounted = false;
    };
  }, [bridge, uiText]);

  async function chooseWorkspace() {
    await runWorkspaceAction(() => bridge?.chooseWorkspace());
  }

  async function switchWorkspace(id: string) {
    await runWorkspaceAction(() => bridge?.useWorkspace(id));
  }

  async function runWorkspaceAction(
    action: () => Promise<PlatoWorkspaceSelectionResult> | undefined,
  ) {
    const resultPromise = action();
    if (!resultPromise) {
      setState(unavailableState(uiText));
      return;
    }

    setIsPending(true);
    setState((current) =>
      current === null ? current : { ...current, error: null, status: "starting" },
    );
    try {
      const result = await resultPromise;
      setState(result.state);
      if (result.status === "cancelled" || result.state.status !== "starting") {
        setIsPending(false);
      }
    } catch {
      setState({
        currentWorkspace,
        error: uiText.main.states.workspaceSwitchFailed,
        recentWorkspaces,
        status: "failed",
      });
      setIsPending(false);
    }
  }

  return (
    <div
      className={styles.workspaceExplorer}
      aria-label={uiText.workspace.labels.workspaces}
    >
      <div className={styles.workspaceTreeGroup}>
        <div className={styles.workspaceTreeCurrent} aria-current="true">
          <Folder className={styles.workspaceSwitcherIcon} size={18} aria-hidden="true" />
          <div className={styles.workspaceTreeCurrentLabel}>
            <span>
              <Text as="span" className={styles.workspaceSwitcherEyebrow}>
                {uiText.workspace.labels.workspace}
              </Text>
              <strong>
                {currentWorkspace?.name ?? uiText.workspace.labels.workspace}
              </strong>
            </span>
          </div>
          {actions ? (
            <div className={styles.workspaceTreeCurrentActions}>{actions}</div>
          ) : null}
        </div>
        {children}
      </div>

      {isBusy ? (
        <Text as="div" className={styles.workspaceSwitcherNotice} variant="muted">
          {uiText.main.states.workspaceSwitching}
        </Text>
      ) : null}

      {state?.error ? (
        <div className={styles.workspaceSwitcherError} role="alert">
          {state.error}
        </div>
      ) : null}

      {recentWorkspaces.map((workspace) => (
        <button
          className={styles.workspaceTreeRow}
          disabled={!canSwitch || isBusy}
          key={workspace.id}
          onClick={() => void switchWorkspace(workspace.id)}
          type="button"
        >
          <Clock className={styles.workspaceSwitcherIcon} size={18} aria-hidden="true" />
          <span>{workspace.name}</span>
        </button>
      ))}

      <button
        className={styles.workspaceTreeRow}
        disabled={!canSwitch || isBusy}
        onClick={() => void chooseWorkspace()}
        type="button"
      >
        <FolderOpen className={styles.workspaceSwitcherIcon} size={18} aria-hidden="true" />
        <span>{uiText.workspace.actions.openOrAddWorkspace}</span>
      </button>
    </div>
  );
}

function unavailableState(uiText: UiTextCatalog): PlatoWorkspaceEntryState {
  return {
    currentWorkspace: null,
    error: uiText.main.states.workspaceSwitchUnavailable,
    recentWorkspaces: [],
    status: "failed",
  };
}
