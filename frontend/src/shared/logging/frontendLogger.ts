export type FrontendLogLevel = "debug" | "info" | "warn" | "error" | "silent";

export type FrontendLogContext = Record<string, unknown>;

export type FrontendLogEntry = {
  context?: FrontendLogContext;
  createdAt: string;
  level: Exclude<FrontendLogLevel, "silent">;
  message: string;
  namespace: string;
};

export type FrontendLogSink = (entry: FrontendLogEntry) => void;

const LEVEL_WEIGHT: Record<FrontendLogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
  silent: 50,
};

const LOG_LEVEL_STORAGE_KEY = "plato.logLevel";
const validLogLevels = new Set<FrontendLogLevel>([
  "debug",
  "info",
  "warn",
  "error",
  "silent",
]);

let frontendLogSink: FrontendLogSink | null = null;
let isNotifyingSink = false;

export type FrontendLogger = {
  debug(message: string, context?: FrontendLogContext): void;
  error(message: string, context?: FrontendLogContext): void;
  info(message: string, context?: FrontendLogContext): void;
  warn(message: string, context?: FrontendLogContext): void;
};

export function configureFrontendLogSink(sink: FrontendLogSink | null): void {
  frontendLogSink = sink;
}

export function createFrontendLogger(namespace: string): FrontendLogger {
  return {
    debug(message, context) {
      writeLog("debug", namespace, message, context);
    },
    error(message, context) {
      writeLog("error", namespace, message, context);
    },
    info(message, context) {
      writeLog("info", namespace, message, context);
    },
    warn(message, context) {
      writeLog("warn", namespace, message, context);
    },
  };
}

export function toLoggableError(error: unknown): FrontendLogContext {
  if (error instanceof Error) {
    return {
      ...ownProperties(error),
      message: error.message,
      name: error.name,
      stack: error.stack,
    };
  }

  return {
    value: error,
  };
}

export function summarizeLoggableError(error: unknown): string {
  if (error instanceof Error) {
    return `${error.name}: ${error.message}`;
  }

  if (typeof error === "string") {
    return error;
  }

  return "unknown error";
}

function writeLog(
  level: Exclude<FrontendLogLevel, "silent">,
  namespace: string,
  message: string,
  context?: FrontendLogContext,
): void {
  const configuredLevel = currentLogLevel();
  if (LEVEL_WEIGHT[level] < LEVEL_WEIGHT[configuredLevel]) {
    return;
  }

  const entry: FrontendLogEntry = {
    context,
    createdAt: new Date().toISOString(),
    level,
    message,
    namespace,
  };
  const prefix = `[plato:${namespace}] ${message}`;
  if (context === undefined) {
    console[level](prefix);
  } else {
    console[level](prefix, context);
  }

  if (level === "error") {
    notifySink(entry);
  }
}

function notifySink(entry: FrontendLogEntry): void {
  if (frontendLogSink === null || isNotifyingSink) {
    return;
  }

  try {
    isNotifyingSink = true;
    frontendLogSink(entry);
  } catch (error) {
    console.warn("[plato:logger] frontend log sink failed", error);
  } finally {
    isNotifyingSink = false;
  }
}

function currentLogLevel(): FrontendLogLevel {
  if (import.meta.env.MODE === "test") {
    return parseLogLevel(import.meta.env.VITE_PLATO_LOG_LEVEL) ?? "silent";
  }

  return (
    readLocalStorageLogLevel() ??
    parseLogLevel(import.meta.env.VITE_PLATO_LOG_LEVEL) ??
    defaultLogLevel()
  );
}

function readLocalStorageLogLevel(): FrontendLogLevel | null {
  try {
    return parseLogLevel(globalThis.localStorage?.getItem(LOG_LEVEL_STORAGE_KEY));
  } catch {
    return null;
  }
}

function parseLogLevel(value: string | null | undefined): FrontendLogLevel | null {
  if (value === null || value === undefined) {
    return null;
  }

  const normalized = value.toLowerCase();
  if (validLogLevels.has(normalized as FrontendLogLevel)) {
    return normalized as FrontendLogLevel;
  }

  return null;
}

function defaultLogLevel(): FrontendLogLevel {
  return import.meta.env.DEV ? "debug" : "warn";
}

function ownProperties(error: Error): FrontendLogContext {
  const properties: FrontendLogContext = {};
  for (const key of Object.getOwnPropertyNames(error)) {
    if (key === "message" || key === "name" || key === "stack") {
      continue;
    }

    properties[key] = (error as unknown as Record<string, unknown>)[key];
  }

  return properties;
}
