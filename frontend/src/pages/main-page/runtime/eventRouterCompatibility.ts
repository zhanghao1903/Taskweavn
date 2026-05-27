import type { UiEvent } from "../../../shared/api/types";
import type { RuntimeEffect } from "../../../shared/runtime/runtimeReducer";
import {
  routeMainPageEvent,
  type MainPageEventAction,
} from "./eventRouter";
import type {
  MainPageMockRuntimeDispatchResult,
  MainPageMockRuntimeFacade,
} from "./mockRuntimeFacade";

export type MainPageEventCompatibilityResult =
  MainPageMockRuntimeDispatchResult & {
    compatible: boolean;
    legacyAction: MainPageEventAction;
    reducerIntent: MainPageReducerEventIntent;
  };

export type MainPageReducerEventIntent = {
  errorMessage: string | null;
  refetch: boolean;
  resync: boolean;
};

export function routeMainPageEventWithReducerCompatibility(
  facade: Pick<MainPageMockRuntimeFacade, "receiveEvent">,
  event: UiEvent,
): MainPageEventCompatibilityResult {
  const legacyAction = routeMainPageEvent(event);
  const reducerResult = facade.receiveEvent(event);
  const reducerIntent = reducerEventIntent(
    reducerResult.effects,
    reducerResult.state.sync.kind === "resyncing",
  );

  return {
    ...reducerResult,
    compatible: isCompatibleLegacyIntent(legacyAction, reducerIntent),
    legacyAction,
    reducerIntent,
  };
}

function reducerEventIntent(
  effects: readonly RuntimeEffect[],
  syncResyncing: boolean,
): MainPageReducerEventIntent {
  const refetch = effects.some(
    (effect) =>
      effect.kind === "query_snapshot" && effect.page === "main",
  );
  const resync =
    syncResyncing ||
    effects.some(
      (effect) => effect.kind === "resync" && effect.page === "main",
    );

  return {
    errorMessage: null,
    refetch,
    resync,
  };
}

function isCompatibleLegacyIntent(
  legacyAction: MainPageEventAction,
  reducerIntent: MainPageReducerEventIntent,
): boolean {
  if (legacyAction.kind === "ignore") {
    return !reducerIntent.refetch && !reducerIntent.resync;
  }

  if (legacyAction.status === "resyncing") {
    return reducerIntent.resync;
  }

  return reducerIntent.refetch || reducerIntent.resync;
}
