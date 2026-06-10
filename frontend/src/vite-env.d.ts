/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PLATO_API_BASE_URL?: string;
  readonly VITE_PLATO_LOG_LEVEL?: "debug" | "info" | "warn" | "error" | "silent";
  readonly VITE_PLATO_API_MODE?: "mock" | "http";
  readonly VITE_PLATO_SESSION_ID?: string;
  readonly VITE_PLATO_DISABLE_EVENTS?: "0" | "1";
  readonly VITE_PLATO_RUNTIME_REDUCER_HARNESS?: "off" | "test";
  readonly VITE_PLATO_UI_LOCALE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

type PlatoElectronRuntimeConfig = {
  readonly apiBaseUrl?: string;
  readonly apiMode?: "mock" | "http";
  readonly appVersion?: string;
  readonly disableEvents?: boolean;
  readonly sessionId?: string | null;
  readonly startupId?: string;
  readonly uiLocale?: string | null;
  readonly workspace?: PlatoWorkspaceEntrySummary | null;
  readonly workspaceEntryRequired?: boolean;
};

type PlatoWorkspaceEntrySummary = {
  readonly id: string;
  readonly isCurrent: boolean;
  readonly label: string;
  readonly name: string;
  readonly pathLabel: string;
};

type PlatoWorkspaceEntryState = {
  readonly currentWorkspace: PlatoWorkspaceEntrySummary | null;
  readonly error: string | null;
  readonly recentWorkspaces: readonly PlatoWorkspaceEntrySummary[];
  readonly status: "needs_selection" | "ready" | "starting" | "failed";
};

type PlatoWorkspaceSelectionResult =
  | {
      readonly state: PlatoWorkspaceEntryState;
      readonly status: "cancelled";
    }
  | {
      readonly state: PlatoWorkspaceEntryState;
      readonly status: "ready";
    };

type PlatoWorkspaceGitStatus = {
  readonly status: "available" | "missing" | "failed";
  readonly version?: string;
};

type PlatoWorkspaceSelectionOptions = {
  readonly initializeGitOnOpen?: boolean;
};

type PlatoElectronWorkspaceBridge = {
  readonly chooseWorkspace: (
    options?: PlatoWorkspaceSelectionOptions,
  ) => Promise<PlatoWorkspaceSelectionResult>;
  readonly getGitStatus: () => Promise<PlatoWorkspaceGitStatus>;
  readonly getState: () => Promise<PlatoWorkspaceEntryState>;
  readonly useWorkspace: (
    id: string,
    options?: PlatoWorkspaceSelectionOptions,
  ) => Promise<PlatoWorkspaceSelectionResult>;
};

interface Window {
  readonly platoElectronWorkspace?: PlatoElectronWorkspaceBridge;
  readonly platoRuntimeConfig?: PlatoElectronRuntimeConfig;
}
