import type { UiEvent } from "../../../shared/api/types";

export type MainPageEventAction =
  | {
      errorMessage?: string;
      kind: "refetch";
      status: "connected" | "resyncing";
    }
  | {
      kind: "ignore";
    };

export function routeMainPageEvent(event: UiEvent): MainPageEventAction {
  if (event.eventType === "command.failed") {
    return {
      kind: "refetch",
      status: "connected",
      errorMessage: userFacingFailedEventMessage(event),
    };
  }

  if (event.eventType === "session.resync_required") {
    return {
      kind: "refetch",
      status: "resyncing",
    };
  }

  return {
    kind: "refetch",
    status: "connected",
  };
}

export function resyncEventKey(event: UiEvent): string | null {
  if (event.eventType !== "session.resync_required") {
    return null;
  }

  return `${event.cursor}:${stringPayload(event.payload.reason) ?? "unknown"}`;
}

function stringPayload(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function userFacingFailedEventMessage(event: UiEvent): string {
  const candidate =
    stringPayload(event.payload.message) ?? stringPayload(event.payload.error);

  if (candidate && !containsInternalTerms(candidate)) {
    return candidate;
  }

  return "An update failed. Refreshing the session.";
}

function containsInternalTerms(value: string): boolean {
  return /\bbackend\b|\bcommand\b|\bprojection\b|\bsnapshot\b|\bsource of truth\b|\bsession facts\b/i.test(
    value,
  );
}
