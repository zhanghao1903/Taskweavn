/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PLATO_API_BASE_URL?: string;
  readonly VITE_PLATO_LOG_LEVEL?: "debug" | "info" | "warn" | "error" | "silent";
  readonly VITE_PLATO_API_MODE?: "mock" | "http";
  readonly VITE_PLATO_SESSION_ID?: string;
  readonly VITE_PLATO_DISABLE_EVENTS?: "0" | "1";
  readonly VITE_PLATO_RUNTIME_REDUCER_HARNESS?: "off" | "test";
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
};

interface Window {
  readonly platoRuntimeConfig?: PlatoElectronRuntimeConfig;
}
