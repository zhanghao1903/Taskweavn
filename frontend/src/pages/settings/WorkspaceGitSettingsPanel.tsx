import { useCallback, useEffect, useMemo, useState } from "react";

import { useUiText, type UiTextCatalog } from "../../shared/ui-text";
import {
  readWorkspaceGitInitializeOnOpenPreference,
  readStoredWorkspaceGitInitializeOnOpenPreference,
  writeWorkspaceGitInitializeOnOpenPreference,
} from "../../shared/workspace/workspaceGitPreference";
import styles from "./SettingsRoute.module.css";

type WorkspaceGitStatusState =
  | { status: "checking" | "desktop_unavailable" }
  | PlatoWorkspaceGitStatus;

type WorkspaceGitPreferenceState = {
  loaded: boolean;
  value: boolean | null;
};

export type WorkspaceGitSettingsPanelProps = {
  bridge?: PlatoElectronWorkspaceBridge | null;
};

export function WorkspaceGitSettingsPanel({
  bridge,
}: WorkspaceGitSettingsPanelProps) {
  const uiText = useUiText();
  const workspaceBridge = useMemo(
    () => bridge ?? globalThis.window?.platoElectronWorkspace ?? null,
    [bridge],
  );
  const [status, setStatus] = useState<WorkspaceGitStatusState>({
    status: workspaceBridge === null ? "desktop_unavailable" : "checking",
  });
  const [preference, setPreference] = useState<WorkspaceGitPreferenceState>(() => ({
    loaded: workspaceBridge?.getGitPreference === undefined,
    value: readStoredWorkspaceGitInitializeOnOpenPreference(),
  }));
  const [initializeOnOpen, setInitializeOnOpen] = useState(() =>
    readWorkspaceGitInitializeOnOpenPreference(),
  );
  const persistInitializeOnOpen = useCallback(
    (enabled: boolean) => {
      setInitializeOnOpen(enabled);
      setPreference({ loaded: true, value: enabled });
      writeWorkspaceGitInitializeOnOpenPreference(enabled);
      void workspaceBridge?.setGitPreference?.({
        initializeGitOnOpen: enabled,
      });
    },
    [workspaceBridge],
  );

  useEffect(() => {
    let isMounted = true;
    if (workspaceBridge === null) {
      setStatus({ status: "desktop_unavailable" });
      return () => {
        isMounted = false;
      };
    }

    setStatus({ status: "checking" });
    void workspaceBridge
      .getGitStatus()
      .then((nextStatus) => {
        if (isMounted) {
          setStatus(nextStatus);
        }
      })
      .catch(() => {
        if (isMounted) {
          setStatus({ status: "failed" });
        }
      });

    return () => {
      isMounted = false;
    };
  }, [workspaceBridge]);

  useEffect(() => {
    let isMounted = true;
    const readPreference = workspaceBridge?.getGitPreference;
    if (readPreference === undefined) {
      setPreference((current) => ({ ...current, loaded: true }));
      return () => {
        isMounted = false;
      };
    }

    setPreference((current) => ({ ...current, loaded: false }));
    void readPreference()
      .then((nextPreference) => {
        if (!isMounted) {
          return;
        }
        const nextValue =
          typeof nextPreference.initializeGitOnOpen === "boolean"
            ? nextPreference.initializeGitOnOpen
            : null;
        setPreference({ loaded: true, value: nextValue });
        if (nextValue !== null) {
          setInitializeOnOpen(nextValue);
          writeWorkspaceGitInitializeOnOpenPreference(nextValue);
        }
      })
      .catch(() => {
        if (isMounted) {
          setPreference((current) => ({ ...current, loaded: true }));
        }
      });

    return () => {
      isMounted = false;
    };
  }, [workspaceBridge]);

  useEffect(() => {
    if (
      status.status === "available" &&
      preference.loaded &&
      preference.value === null
    ) {
      persistInitializeOnOpen(true);
    }
  }, [
    persistInitializeOnOpen,
    preference.loaded,
    preference.value,
    status.status,
  ]);

  const isUnavailable =
    status.status === "missing" ||
    status.status === "failed" ||
    status.status === "desktop_unavailable";

  return (
    <section
      aria-label={uiText.settings.labels.workspaceGit}
      className={styles.settingsSubsection}
    >
      <div>
        <h2>{uiText.settings.labels.workspaceGit}</h2>
        <dl className={styles.inlineStatusList}>
          <div>
            <dt>{uiText.settings.fields.gitAvailability}</dt>
            <dd>{gitStatusLabel(status, uiText)}</dd>
          </div>
        </dl>
        {gitStatusHelp(status, uiText) ? (
          <p className={styles.helperText}>{gitStatusHelp(status, uiText)}</p>
        ) : null}
      </div>
      <label className={styles.checkboxField}>
        <input
          checked={initializeOnOpen}
          disabled={isUnavailable || status.status === "checking" || !preference.loaded}
          onChange={(event) => {
            persistInitializeOnOpen(event.target.checked);
          }}
          type="checkbox"
        />
        <span>{uiText.settings.fields.initializeGitForOpenedWorkspaces}</span>
      </label>
      <p className={styles.helperText}>
        {uiText.settings.messages.initializeGitForOpenedWorkspacesHelp}
      </p>
    </section>
  );
}

function gitStatusLabel(
  status: WorkspaceGitStatusState,
  uiText: UiTextCatalog,
): string {
  if (status.status === "checking") {
    return uiText.settings.messages.checkingGitAvailability;
  }
  if (status.status === "available") {
    return uiText.settings.messages.gitAvailable({
      version: status.version ?? uiText.settings.labels.gitAvailable,
    });
  }
  if (status.status === "missing") {
    return uiText.settings.labels.gitMissing;
  }
  if (status.status === "failed") {
    return uiText.settings.labels.gitFailed;
  }
  return uiText.settings.labels.sidecarRequired;
}

function gitStatusHelp(
  status: WorkspaceGitStatusState,
  uiText: UiTextCatalog,
): string | null {
  if (status.status === "missing") {
    return uiText.settings.messages.gitMissingHelp;
  }
  if (status.status === "failed") {
    return uiText.settings.messages.gitFailedHelp;
  }
  if (status.status === "desktop_unavailable") {
    return uiText.settings.messages.workspaceGitDesktopUnavailable;
  }
  return null;
}
