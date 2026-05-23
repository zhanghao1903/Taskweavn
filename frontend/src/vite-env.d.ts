/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PLATO_API_BASE_URL?: string;
  readonly VITE_PLATO_LOG_LEVEL?: "debug" | "info" | "warn" | "error" | "silent";
  readonly VITE_PLATO_API_MODE?: "mock" | "http";
  readonly VITE_PLATO_SESSION_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
