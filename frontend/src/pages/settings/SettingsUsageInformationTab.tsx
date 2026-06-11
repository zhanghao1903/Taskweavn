import { useEffect, useMemo, useState } from "react";

import type { WorkspaceUsageApi } from "../usage/WorkspaceUsageRoute";
import { WorkspaceUsageRoute } from "../usage/WorkspaceUsageRoute";
import { Text } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import styles from "./SettingsDataManagementTab.module.css";

export function SettingsUsageInformationTab({
  api,
  workspaceBridge,
}: {
  api: WorkspaceUsageApi | null;
  workspaceBridge?: PlatoElectronWorkspaceBridge | null;
}) {
  const uiText = useUiText();
  const bridge = workspaceBridge ?? globalThis.window?.platoElectronWorkspace ?? null;
  const runtimeWorkspace = globalThis.window?.platoRuntimeConfig?.workspace ?? null;
  const [workspaceState, setWorkspaceState] =
    useState<PlatoWorkspaceEntryState | null>(null);

  useEffect(() => {
    if (bridge === null) {
      return undefined;
    }
    let isMounted = true;
    void bridge.getState().then((state) => {
      if (isMounted) {
        setWorkspaceState(state);
      }
    });
    return () => {
      isMounted = false;
    };
  }, [bridge]);

  const workspace = useMemo(
    () => workspaceState?.currentWorkspace ?? runtimeWorkspace,
    [runtimeWorkspace, workspaceState?.currentWorkspace],
  );

  if (workspace === null) {
    return (
      <section className={styles.sectionStack} aria-label={uiText.settings.tabs.usageInformation}>
        <Text variant="muted">{uiText.workspace.messages.noWorkspaceData}</Text>
      </section>
    );
  }

  return (
    <WorkspaceUsageRoute
      api={api}
      location={{
        pathname: `/workspaces/${encodeURIComponent(workspace.id)}/usage`,
        search: "",
      }}
      presentation="embedded"
    />
  );
}
