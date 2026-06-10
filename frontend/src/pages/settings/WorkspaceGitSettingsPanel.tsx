import { useEffect, useMemo, useState } from "react";

import { useUiText, type UiTextCatalog } from "../../shared/ui-text";
import {
  readWorkspaceGitInitializeOnOpenPreference,
  writeWorkspaceGitInitializeOnOpenPreference,
} from "../../shared/workspace/workspaceGitPreference";
import styles from "./SettingsRoute.module.css";

type WorkspaceGitStatusState =
  | { status: "checking" | "desktop_unavailable" }
  | PlatoWorkspaceGitStatus;

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
  const [initializeOnOpen, setInitializeOnOpen] = useState(() =>
    readWorkspaceGitInitializeOnOpenPreference(),
  );

  useEffect(() => {
    let isMounted = true;
    if (workspaceBridge === null) {
      setStatus({ status: "desktop_unavailable" });
      if (initializeOnOpen) {
        setInitializeOnOpen(false);
        writeWorkspaceGitInitializeOnOpenPreference(false);
      }
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
  }, [initializeOnOpen, workspaceBridge]);

  useEffect(() => {
    if (
      initializeOnOpen &&
      (status.status === "missing" ||
        status.status === "failed" ||
        status.status === "desktop_unavailable")
    ) {
      setInitializeOnOpen(false);
      writeWorkspaceGitInitializeOnOpenPreference(false);
    }
  }, [initializeOnOpen, status.status]);

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
          disabled={isUnavailable || status.status === "checking"}
          onChange={(event) => {
            const nextValue = event.target.checked;
            setInitializeOnOpen(nextValue);
            writeWorkspaceGitInitializeOnOpenPreference(nextValue);
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
