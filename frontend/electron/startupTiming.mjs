import { performance } from "node:perf_hooks";

export const STARTUP_TIMING_PREFIX = "[plato-startup-timing]";

const processStartedAt = performance.now();

export function markStartupTiming(event, details = {}) {
  const {
    source = "electron-main",
    startupId = process.env.PLATO_STARTUP_ID ?? null,
    ...attributes
  } = details && typeof details === "object" ? details : {};
  const payload = {
    schemaVersion: "plato.startup_timing.v1",
    event: sanitizeEventName(event),
    source: sanitizeString(source, "electron-main"),
    startupId: typeof startupId === "string" && startupId.length > 0 ? startupId : null,
    pid: process.pid,
    timestamp: new Date().toISOString(),
    elapsedMs: Math.round((performance.now() - processStartedAt) * 100) / 100,
    ...sanitizeAttributes(attributes),
  };
  console.log(`${STARTUP_TIMING_PREFIX} ${JSON.stringify(payload)}`);
  return payload;
}

function sanitizeEventName(value) {
  if (typeof value !== "string") {
    return "unknown";
  }
  const trimmed = value.trim();
  if (/^[a-z0-9_.:-]{1,96}$/i.test(trimmed)) {
    return trimmed;
  }
  return "unknown";
}

function sanitizeString(value, fallback) {
  if (typeof value !== "string" || value.length === 0) {
    return fallback;
  }
  return value.length > 160 ? `${value.slice(0, 157)}...` : value;
}

function sanitizeAttributes(attributes) {
  const sanitized = {};
  for (const [key, value] of Object.entries(attributes)) {
    if (!/^[A-Za-z0-9_.:-]{1,64}$/.test(key)) {
      continue;
    }
    if (typeof value === "string") {
      sanitized[key] = sanitizeString(value, "");
      continue;
    }
    if (typeof value === "number" && Number.isFinite(value)) {
      sanitized[key] = Math.round(value * 100) / 100;
      continue;
    }
    if (typeof value === "boolean" || value === null) {
      sanitized[key] = value;
    }
  }
  return sanitized;
}
