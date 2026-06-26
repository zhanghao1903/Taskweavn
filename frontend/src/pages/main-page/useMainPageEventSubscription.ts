import { useCallback, useEffect, useRef, useState } from "react";

import {
  summarizeMainPageSnapshot,
  summarizeUiEvent,
} from "../../shared/api/traceSummary";
import {
  createFrontendLogger,
  toLoggableError,
} from "../../shared/logging/frontendLogger";
import type { EventConnectionStatus } from "./mainPageUiTypes";
import type {
  MainPageAdapter,
  MainPageRuntimeSnapshot,
} from "./runtime/adapter";
import { resyncEventKey, routeMainPageEvent } from "./runtime/eventRouter";

const mainPageEventLogger = createFrontendLogger("main-page");

type SnapshotRefetchResult = {
  data?: MainPageRuntimeSnapshot;
  status: string;
};

export type UseMainPageEventSubscriptionOptions = {
  activeWorkspaceId: string | null;
  adapter: MainPageAdapter;
  refetchSnapshot: () => Promise<SnapshotRefetchResult>;
  resetKey: string | null;
  snapshotData: MainPageRuntimeSnapshot | undefined;
};

export type MainPageEventSubscriptionState = {
  clearEventError: () => void;
  eventConnectionStatus: EventConnectionStatus;
  eventError: string | null;
};

export function useMainPageEventSubscription({
  activeWorkspaceId,
  adapter,
  refetchSnapshot,
  resetKey,
  snapshotData,
}: UseMainPageEventSubscriptionOptions): MainPageEventSubscriptionState {
  const [eventError, setEventError] = useState<string | null>(null);
  const [eventConnectionStatus, setEventConnectionStatus] =
    useState<EventConnectionStatus>("disconnected");
  const lastEventCursorRef = useRef<string | null>(null);
  const lastResyncEventKeyRef = useRef<string | null>(null);
  const clearEventError = useCallback(() => setEventError(null), []);

  useEffect(() => {
    if (resetKey === null) {
      return;
    }

    lastEventCursorRef.current = null;
    lastResyncEventKeyRef.current = null;
  }, [resetKey]);

  useEffect(() => {
    if (!snapshotData) {
      return undefined;
    }

    mainPageEventLogger.info("events.subscribe.start", {
      runtimeKind: adapter.runtimeKind,
      sessionId: snapshotData.snapshot.session.id,
    });

    let active = true;
    setEventConnectionStatus("connected");

    let unsubscribe: (() => void) | null = null;
    try {
      unsubscribe = adapter.subscribeSessionEvents(
        snapshotData.snapshot.session.id,
        snapshotData.snapshot.cursor,
        (event) => {
          mainPageEventLogger.debug("events.received", {
            ...summarizeUiEvent(event),
          });

          if (event.cursor === lastEventCursorRef.current) {
            mainPageEventLogger.info("events.cursor.duplicate_ignored", {
              event: summarizeUiEvent(event),
            });
            return;
          }
          lastEventCursorRef.current = event.cursor;

          const nextResyncEventKey = resyncEventKey(event);
          if (nextResyncEventKey !== null) {
            if (nextResyncEventKey === lastResyncEventKeyRef.current) {
              mainPageEventLogger.info("events.resync.duplicate_ignored", {
                event: summarizeUiEvent(event),
              });
              return;
            }
            lastResyncEventKeyRef.current = nextResyncEventKey;
          }

          const action = routeMainPageEvent(event);
          mainPageEventLogger.info("events.route", {
            action,
            event: summarizeUiEvent(event),
          });
          if (action.kind === "ignore") {
            return;
          }

          if (action.errorMessage) {
            setEventError(action.errorMessage);
          }
          setEventConnectionStatus(action.status);
          mainPageEventLogger.info("snapshot.refetch.request", {
            event: summarizeUiEvent(event),
            reason: "event",
          });
          void refetchSnapshot()
            .then((queryResult) => {
              mainPageEventLogger.info("snapshot.refetch.result", {
                event: summarizeUiEvent(event),
                hasData: queryResult.data !== undefined,
                reason: "event",
                snapshot:
                  queryResult.data === undefined
                    ? null
                    : summarizeMainPageSnapshot(queryResult.data.snapshot),
                status: queryResult.status,
              });
            })
            .catch((error) => {
              mainPageEventLogger.error("snapshot.refetch.failed", {
                error: toLoggableError(error),
                event: summarizeUiEvent(event),
                reason: "event",
              });
            })
            .finally(() => {
              if (active) {
                setEventConnectionStatus("connected");
              }
            });
        },
        activeWorkspaceId,
      );
    } catch (error) {
      mainPageEventLogger.error("events.subscribe.failed", {
        error: toLoggableError(error),
        runtimeKind: adapter.runtimeKind,
        sessionId: snapshotData.snapshot.session.id,
      });
      setEventConnectionStatus("disconnected");
      setEventError(
        error instanceof Error
          ? `Event stream unavailable: ${error.message}`
          : "Event stream unavailable.",
      );
    }

    return () => {
      active = false;
      mainPageEventLogger.info("events.subscribe.stop", {
        runtimeKind: adapter.runtimeKind,
        sessionId: snapshotData.snapshot.session.id,
      });
      unsubscribe?.();
    };
  }, [activeWorkspaceId, adapter, refetchSnapshot, snapshotData]);

  return {
    clearEventError,
    eventConnectionStatus,
    eventError,
  };
}
