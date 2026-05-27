import { mapApiErrorToUiBoundary } from "../api/apiUiMapping";
import type {
  ApiError,
  AuditPageSnapshot,
  CommandId,
  CommandResult,
  ConfirmationId,
  EventCursor,
  MainPageSnapshot,
  UiEvent,
} from "../api/types";

export type RuntimePageKind = "main" | "audit";

export type RuntimeSnapshot = MainPageSnapshot | AuditPageSnapshot;

export type RuntimeSyncState =
  | { kind: "idle" }
  | { kind: "resyncing"; reason: string }
  | { kind: "stale"; reason: string; error?: ApiError | Error };

export type RuntimeCommandTarget =
  | { kind: "confirmation"; confirmationId: ConfirmationId }
  | { kind: "generic" };

export type RuntimePendingCommand = {
  commandId: CommandId;
  result: CommandResult | null;
  status: "accepted" | "failed";
  target: RuntimeCommandTarget;
  error?: ApiError | Error;
};

export type RuntimeState<TSnapshot extends RuntimeSnapshot = RuntimeSnapshot> = {
  page: RuntimePageKind;
  snapshot: TSnapshot | null;
  pendingCommands: Record<CommandId, RuntimePendingCommand>;
  lastAppliedCursor: EventCursor | null;
  sync: RuntimeSyncState;
};

export type RuntimeAction =
  | { kind: "snapshot.loaded"; page: RuntimePageKind; snapshot: RuntimeSnapshot }
  | { kind: "event.received"; event: UiEvent }
  | {
      kind: "command.accepted";
      result: CommandResult;
      target?: RuntimeCommandTarget;
    }
  | { kind: "command.failed"; commandId: CommandId; error: ApiError | Error }
  | { kind: "resync.started"; reason: string }
  | { kind: "resync.finished"; snapshot: RuntimeSnapshot }
  | { kind: "resync.failed"; error: ApiError | Error };

export type RuntimeEffect =
  | { kind: "query_snapshot"; page: RuntimePageKind; reason: string }
  | { kind: "query_audit_snapshot"; reason: string }
  | { kind: "resync"; page: RuntimePageKind; reason: string }
  | { kind: "restart_events"; cursor: EventCursor | null };

export type RuntimeWarning = {
  code:
    | "cursor_duplicate"
    | "cursor_gap"
    | "event_malformed"
    | "event_unsupported";
  eventId?: string;
  eventType?: string;
  message: string;
};

export type CursorOrder = "newer" | "duplicate_or_old" | "gap";

export type RuntimeReducerOptions = {
  compareCursor?: (
    previous: EventCursor | null,
    next: EventCursor,
  ) => CursorOrder;
};

export type RuntimeReducerResult<
  TSnapshot extends RuntimeSnapshot = RuntimeSnapshot,
> = {
  state: RuntimeState<TSnapshot>;
  effects: RuntimeEffect[];
  warnings: RuntimeWarning[];
};

export function createInitialRuntimeState<
  TSnapshot extends RuntimeSnapshot = RuntimeSnapshot,
>(page: RuntimePageKind): RuntimeState<TSnapshot> {
  return {
    lastAppliedCursor: null,
    page,
    pendingCommands: {},
    snapshot: null,
    sync: { kind: "idle" },
  };
}

export function reduceRuntimeState<
  TSnapshot extends RuntimeSnapshot = RuntimeSnapshot,
>(
  state: RuntimeState<TSnapshot>,
  action: RuntimeAction,
  options: RuntimeReducerOptions = {},
): RuntimeReducerResult<TSnapshot> {
  switch (action.kind) {
    case "snapshot.loaded":
      return result({
        ...state,
        lastAppliedCursor: action.snapshot.cursor,
        page: action.page,
        snapshot: action.snapshot as TSnapshot,
        sync: { kind: "idle" },
      });

    case "command.accepted":
      return acceptCommand(state, action.result, action.target);

    case "command.failed":
      return failCommand(state, action.commandId, action.error);

    case "event.received":
      return applyEvent(state, action.event, options);

    case "resync.started":
      return result(
        {
          ...state,
          sync: { kind: "resyncing", reason: action.reason },
        },
        [{ kind: "resync", page: state.page, reason: action.reason }],
      );

    case "resync.finished":
      return result(
        {
          ...state,
          lastAppliedCursor: action.snapshot.cursor,
          snapshot: action.snapshot as TSnapshot,
          sync: { kind: "idle" },
        },
        [{ kind: "restart_events", cursor: action.snapshot.cursor }],
      );

    case "resync.failed":
      return result({
        ...state,
        sync: {
          error: action.error,
          kind: "stale",
          reason: errorMessage(action.error),
        },
      });
  }
}

function acceptCommand<TSnapshot extends RuntimeSnapshot>(
  state: RuntimeState<TSnapshot>,
  resultValue: CommandResult,
  target: RuntimeCommandTarget = { kind: "generic" },
): RuntimeReducerResult<TSnapshot> {
  const pendingCommand: RuntimePendingCommand = {
    commandId: resultValue.commandId,
    result: resultValue,
    status: "accepted",
    target,
  };

  return result({
    ...state,
    pendingCommands: {
      ...state.pendingCommands,
      [resultValue.commandId]: pendingCommand,
    },
    snapshot:
      target.kind === "confirmation"
        ? setConfirmationLocalStatus(
            state.snapshot,
            target.confirmationId,
            "resolving",
          )
        : state.snapshot,
  });
}

function failCommand<TSnapshot extends RuntimeSnapshot>(
  state: RuntimeState<TSnapshot>,
  commandId: CommandId,
  error: ApiError | Error,
): RuntimeReducerResult<TSnapshot> {
  const previousCommand = state.pendingCommands[commandId];
  const pendingCommands = {
    ...state.pendingCommands,
    [commandId]: {
      commandId,
      error,
      result: previousCommand?.result ?? null,
      status: "failed" as const,
      target: previousCommand?.target ?? { kind: "generic" as const },
    },
  };
  const boundary = isApiError(error) ? mapApiErrorToUiBoundary(error) : null;
  const shouldResync = boundary?.shouldResync === true;
  const nextState: RuntimeState<TSnapshot> = {
    ...state,
    pendingCommands,
    snapshot:
      previousCommand?.target.kind === "confirmation"
        ? setConfirmationLocalStatus(
            state.snapshot,
            previousCommand.target.confirmationId,
            "resolve_failed",
          )
        : state.snapshot,
    sync: shouldResync
      ? { kind: "resyncing", reason: boundary.message }
      : state.sync,
  };

  return result(
    nextState,
    shouldResync
      ? [{ kind: "resync", page: state.page, reason: boundary.message }]
      : [],
  );
}

function applyEvent<TSnapshot extends RuntimeSnapshot>(
  state: RuntimeState<TSnapshot>,
  event: UiEvent,
  options: RuntimeReducerOptions,
): RuntimeReducerResult<TSnapshot> {
  const cursorOrder = options.compareCursor?.(
    state.lastAppliedCursor,
    event.cursor,
  );

  if (cursorOrder === "duplicate_or_old") {
    return result(state, [], [
      {
        code: "cursor_duplicate",
        eventId: event.eventId,
        eventType: event.eventType,
        message: "Ignored duplicate or stale event cursor.",
      },
    ]);
  }

  if (cursorOrder === "gap") {
    return requestResync(state, `Event cursor gap before ${event.cursor}.`, [
      {
        code: "cursor_gap",
        eventId: event.eventId,
        eventType: event.eventType,
        message: "Event cursor gap detected.",
      },
    ]);
  }

  const withCursor: RuntimeState<TSnapshot> = {
    ...state,
    lastAppliedCursor: event.cursor,
  };

  if (!isKnownEventType(event.eventType)) {
    if (eventMayAffectVisibleState(event)) {
      return requestResync(
        withCursor,
        `Unsupported visible event ${event.eventType}.`,
        [
          {
            code: "event_unsupported",
            eventId: event.eventId,
            eventType: event.eventType,
            message:
              "Unsupported event may affect visible state; requested snapshot resync.",
          },
        ],
      );
    }

    return result(withCursor, [], [
      {
        code: "event_unsupported",
        eventId: event.eventId,
        eventType: event.eventType,
        message: "Ignored unsupported event with no visible affected objects.",
      },
    ]);
  }

  switch (event.eventType) {
    case "session.resync_required":
      return requestResync(
        withCursor,
        stringPayload(event.payload.reason) ?? "Session snapshot resync required.",
      );

    case "audit.snapshot_stale":
      return result(
        {
          ...withCursor,
          sync: {
            kind: "resyncing",
            reason:
              stringPayload(event.payload.reason) ??
              "Audit snapshot is stale.",
          },
        },
        [
          {
            kind: "query_audit_snapshot",
            reason:
              stringPayload(event.payload.reason) ??
              "Audit snapshot is stale.",
          },
        ],
      );

    case "confirmation.resolved":
      return applyConfirmationResolved(withCursor, event);

    case "command.failed":
      return event.commandId
        ? failCommand(
            withCursor,
            event.commandId,
            apiErrorFromEvent(event) ?? new Error(eventFailureMessage(event)),
          )
        : requestResync(withCursor, "Command failed event missing commandId.", [
            {
              code: "event_malformed",
              eventId: event.eventId,
              eventType: event.eventType,
              message: "Command failed event missing commandId.",
            },
          ]);

    case "audit.records_changed":
    case "audit.record_updated":
    case "audit.evidence_hidden":
      return result(withCursor, [
        {
          kind: "query_audit_snapshot",
          reason: `${event.eventType} invalidated audit snapshot.`,
        },
      ]);

    case "command.completed":
    case "file_changes.updated":
    case "message.appended":
    case "result.updated":
    case "session.status_changed":
    case "task.node.changed":
    case "task.tree.changed":
    case "audit.summary_updated":
    case "confirmation.created":
      return result(withCursor, [
        {
          kind: "query_snapshot",
          page: withCursor.page,
          reason: `${event.eventType} invalidated page snapshot.`,
        },
      ]);
  }
}

function applyConfirmationResolved<TSnapshot extends RuntimeSnapshot>(
  state: RuntimeState<TSnapshot>,
  event: UiEvent,
): RuntimeReducerResult<TSnapshot> {
  const confirmationId =
    stringPayload(event.payload.confirmationId) ??
    objectIdPayload(event.payload.confirmation);

  if (confirmationId === null) {
    return requestResync(state, "Confirmation resolved event missing id.", [
      {
        code: "event_malformed",
        eventId: event.eventId,
        eventType: event.eventType,
        message: "Confirmation resolved event missing confirmation id.",
      },
    ]);
  }

  const nextSnapshot = setConfirmationResolved(
    state.snapshot,
    confirmationId,
    stringPayload(event.payload.resolvedAt) ?? event.createdAt,
  );

  if (nextSnapshot === state.snapshot) {
    return requestResync(
      state,
      `Confirmation ${confirmationId} is not present in current snapshot.`,
      [
        {
          code: "event_malformed",
          eventId: event.eventId,
          eventType: event.eventType,
          message: "Confirmation event referenced an unknown visible object.",
        },
      ],
    );
  }

  const pendingCommands = removeConfirmationPendingCommands(
    state.pendingCommands,
    confirmationId,
  );

  return result({
    ...state,
    pendingCommands,
    snapshot: nextSnapshot,
  });
}

function requestResync<TSnapshot extends RuntimeSnapshot>(
  state: RuntimeState<TSnapshot>,
  reason: string,
  warnings: RuntimeWarning[] = [],
): RuntimeReducerResult<TSnapshot> {
  return result(
    {
      ...state,
      sync: { kind: "resyncing", reason },
    },
    [{ kind: "resync", page: state.page, reason }],
    warnings,
  );
}

function result<TSnapshot extends RuntimeSnapshot>(
  state: RuntimeState<TSnapshot>,
  effects: RuntimeEffect[] = [],
  warnings: RuntimeWarning[] = [],
): RuntimeReducerResult<TSnapshot> {
  return { effects, state, warnings };
}

function setConfirmationLocalStatus<TSnapshot extends RuntimeSnapshot>(
  snapshot: TSnapshot | null,
  confirmationId: ConfirmationId,
  localStatus: "resolving" | "resolve_failed",
): TSnapshot | null {
  if (!isMainPageSnapshot(snapshot)) {
    return snapshot;
  }

  return {
    ...snapshot,
    pendingConfirmations: snapshot.pendingConfirmations.map((confirmation) =>
      confirmation.id === confirmationId
        ? { ...confirmation, localStatus }
        : confirmation,
    ),
  } as TSnapshot;
}

function setConfirmationResolved<TSnapshot extends RuntimeSnapshot>(
  snapshot: TSnapshot | null,
  confirmationId: ConfirmationId,
  resolvedAt: string,
): TSnapshot | null {
  if (!isMainPageSnapshot(snapshot)) {
    return snapshot;
  }

  let found = false;
  const pendingConfirmations = snapshot.pendingConfirmations.map(
    (confirmation) => {
      if (confirmation.id !== confirmationId) {
        return confirmation;
      }

      found = true;
      return {
        ...confirmation,
        localStatus: "idle" as const,
        resolvedAt,
        status: "resolved" as const,
      };
    },
  );

  if (!found) {
    return snapshot;
  }

  return {
    ...snapshot,
    pendingConfirmations,
  } as TSnapshot;
}

function removeConfirmationPendingCommands(
  pendingCommands: Record<CommandId, RuntimePendingCommand>,
  confirmationId: ConfirmationId,
): Record<CommandId, RuntimePendingCommand> {
  return Object.fromEntries(
    Object.entries(pendingCommands).filter(([, command]) => {
      return !(
        command.target.kind === "confirmation" &&
        command.target.confirmationId === confirmationId
      );
    }),
  );
}

function isMainPageSnapshot(
  snapshot: RuntimeSnapshot | null,
): snapshot is MainPageSnapshot {
  return (
    snapshot !== null &&
    "pendingConfirmations" in snapshot &&
    Array.isArray(snapshot.pendingConfirmations)
  );
}

function eventMayAffectVisibleState(event: UiEvent): boolean {
  return (
    event.taskNodeIds.length > 0 ||
    event.messageIds.length > 0 ||
    event.payload.affectsVisibleState === true ||
    event.payload.visible === true
  );
}

function isKnownEventType(eventType: string): boolean {
  return knownEventTypes.has(eventType);
}

function apiErrorFromEvent(event: UiEvent): ApiError | null {
  const error = event.payload.error;

  if (isApiError(error)) {
    return error;
  }

  return null;
}

function isApiError(value: unknown): value is ApiError {
  return (
    typeof value === "object" &&
    value !== null &&
    "code" in value &&
    "message" in value &&
    "retryable" in value &&
    "details" in value
  );
}

function eventFailureMessage(event: UiEvent): string {
  return (
    stringPayload(event.payload.message) ??
    stringPayload(event.payload.error) ??
    "Backend command failed."
  );
}

function errorMessage(error: ApiError | Error): string {
  return isApiError(error) ? error.message : error.message;
}

function stringPayload(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function objectIdPayload(value: unknown): string | null {
  if (typeof value !== "object" || value === null || !("id" in value)) {
    return null;
  }

  const id = (value as { id: unknown }).id;
  return typeof id === "string" ? id : null;
}

const knownEventTypes = new Set<string>([
  "session.status_changed",
  "session.resync_required",
  "task.tree.changed",
  "task.node.changed",
  "message.appended",
  "confirmation.created",
  "confirmation.resolved",
  "result.updated",
  "file_changes.updated",
  "audit.summary_updated",
  "audit.records_changed",
  "audit.record_updated",
  "audit.evidence_hidden",
  "audit.snapshot_stale",
  "command.completed",
  "command.failed",
]);
