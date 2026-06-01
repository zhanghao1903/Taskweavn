import { useEffect, useRef } from "react";

import type {
  AuditRecordId,
  EventCursor,
  EvidenceId,
  SessionId,
  TaskNodeId,
  UiEvent,
  UiEventType,
} from "../../shared/api/types";
import type { PlatoApi } from "../../shared/api/platoApi";

export type AuditPageRuntimeEventContext = {
  selectedEvidenceId: EvidenceId | null;
  selectedRecordId: AuditRecordId | null;
  sessionId: SessionId;
  taskNodeId: TaskNodeId | null;
};

export type AuditPageRuntimeEventAction =
  | {
      kind: "ignore";
    }
  | {
      kind: "refetch";
      refetchDetail: boolean;
      refetchEvidence: boolean;
      refetchSnapshot: boolean;
      resync: boolean;
    };

export type AuditPageRuntimeEventApi = Pick<PlatoApi, "subscribeSessionEvents">;

export type AuditPageRuntimeEventOptions = AuditPageRuntimeEventContext & {
  api: AuditPageRuntimeEventApi;
  cursor: EventCursor | null;
  enabled: boolean;
  refetchDetail: () => Promise<unknown> | unknown;
  refetchEvidence: () => Promise<unknown> | unknown;
  refetchSnapshot: () => Promise<unknown> | unknown;
};

const SNAPSHOT_EVENTS = new Set<UiEventType>([
  "audit.summary_updated",
  "audit.records_changed",
]);

const COARSE_AUDIT_INVALIDATION_EVENTS = new Set<UiEventType>([
  "message.appended",
  "confirmation.created",
  "confirmation.resolved",
  "file_changes.updated",
  "result.updated",
]);

export function useAuditPageRuntimeEvents({
  api,
  cursor,
  enabled,
  refetchDetail,
  refetchEvidence,
  refetchSnapshot,
  selectedEvidenceId,
  selectedRecordId,
  sessionId,
  taskNodeId,
}: AuditPageRuntimeEventOptions): void {
  const lastEventCursorRef = useRef<EventCursor | null>(null);

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    let unsubscribe: (() => void) | null = null;
    try {
      unsubscribe = api.subscribeSessionEvents(sessionId, cursor, (event) => {
        if (event.cursor === lastEventCursorRef.current) {
          return;
        }

        const action = routeAuditPageRuntimeEvent(event, {
          selectedEvidenceId,
          selectedRecordId,
          sessionId,
          taskNodeId,
        });

        if (action.kind === "ignore") {
          return;
        }

        lastEventCursorRef.current = event.cursor;

        if (action.refetchSnapshot) {
          void refetchSnapshot();
        }
        if (action.refetchDetail) {
          void refetchDetail();
        }
        if (action.refetchEvidence) {
          void refetchEvidence();
        }
      });
    } catch {
      // AP-013B intentionally keeps live-refresh failures non-blocking. AP-013C
      // will add visible live-state feedback for disconnected/stale states.
      return undefined;
    }

    return () => {
      unsubscribe?.();
    };
  }, [
    api,
    cursor,
    enabled,
    refetchDetail,
    refetchEvidence,
    refetchSnapshot,
    selectedEvidenceId,
    selectedRecordId,
    sessionId,
    taskNodeId,
  ]);
}

export function routeAuditPageRuntimeEvent(
  event: UiEvent,
  context: AuditPageRuntimeEventContext,
): AuditPageRuntimeEventAction {
  if (event.sessionId !== context.sessionId) {
    return { kind: "ignore" };
  }

  if (!eventAffectsCurrentScope(event, context)) {
    return { kind: "ignore" };
  }

  if (event.eventType === "session.resync_required") {
    return refetchAction({ resync: true, snapshot: true });
  }

  if (event.eventType === "audit.snapshot_stale") {
    return refetchAction({ resync: true, snapshot: true });
  }

  if (SNAPSHOT_EVENTS.has(event.eventType)) {
    return refetchAction({ snapshot: true });
  }

  if (event.eventType === "audit.record_updated") {
    const recordId = stringPayload(event.payload, "record_id", "recordId");
    const selected = recordId !== null && recordId === context.selectedRecordId;
    return refetchAction({
      detail: selected,
      snapshot: true,
    });
  }

  if (event.eventType === "audit.evidence_hidden") {
    const recordId = stringPayload(event.payload, "record_id", "recordId");
    const evidenceIds = stringArrayPayload(
      event.payload,
      "evidence_ids",
      "evidenceIds",
    );
    const selectedRecord =
      recordId !== null && recordId === context.selectedRecordId;
    const selectedEvidence =
      context.selectedEvidenceId !== null &&
      evidenceIds.includes(context.selectedEvidenceId);

    return refetchAction({
      detail: selectedRecord || selectedEvidence,
      evidence: selectedEvidence,
      snapshot: true,
    });
  }

  if (COARSE_AUDIT_INVALIDATION_EVENTS.has(event.eventType)) {
    return refetchAction({ snapshot: true });
  }

  return { kind: "ignore" };
}

function refetchAction({
  detail = false,
  evidence = false,
  resync = false,
  snapshot = false,
}: {
  detail?: boolean;
  evidence?: boolean;
  resync?: boolean;
  snapshot?: boolean;
}): AuditPageRuntimeEventAction {
  return {
    kind: "refetch",
    refetchDetail: detail,
    refetchEvidence: evidence,
    refetchSnapshot: snapshot,
    resync,
  };
}

function eventAffectsCurrentScope(
  event: UiEvent,
  context: AuditPageRuntimeEventContext,
): boolean {
  if (context.taskNodeId === null) {
    return true;
  }

  if (event.taskNodeIds.includes(context.taskNodeId)) {
    return true;
  }

  const scope = objectPayload(event.payload.scope);
  const scopeSessionId = stringPayload(scope, "sessionId", "session_id");
  if (scopeSessionId !== null && scopeSessionId !== context.sessionId) {
    return false;
  }

  const scopeTaskNodeId = stringPayload(scope, "taskNodeId", "task_node_id");
  if (scopeTaskNodeId !== null) {
    return scopeTaskNodeId === context.taskNodeId;
  }

  if (event.taskNodeIds.length > 0) {
    return false;
  }

  return true;
}

function objectPayload(value: unknown): Record<string, unknown> {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }

  return {};
}

function stringPayload(
  payload: Record<string, unknown>,
  ...keys: string[]
): string | null {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "string") {
      return value;
    }
  }

  return null;
}

function stringArrayPayload(
  payload: Record<string, unknown>,
  ...keys: string[]
): string[] {
  for (const key of keys) {
    const value = payload[key];
    if (Array.isArray(value)) {
      return value.filter((item): item is string => typeof item === "string");
    }
  }

  return [];
}
