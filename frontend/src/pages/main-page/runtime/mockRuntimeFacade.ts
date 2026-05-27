import type { CommandResponse, MainPageSnapshot, UiEvent } from "../../../shared/api/types";
import {
  createInitialRuntimeState,
  reduceRuntimeState,
  type RuntimeAction,
  type RuntimeCommandTarget,
  type RuntimeEffect,
  type RuntimeReducerOptions,
  type RuntimeState,
  type RuntimeWarning,
} from "../../../shared/runtime/runtimeReducer";
import {
  loadMainPageMockSnapshot,
  type MainPageMockSnapshot,
} from "../mockPlatoApi";
import type { MainPageStateMetadata } from "./adapter";

export type MainPageMockRuntimeFacadeOptions = {
  compareCursor?: RuntimeReducerOptions["compareCursor"];
  loadSnapshot?: (stateId: string) => Promise<MainPageMockSnapshot>;
};

export type MainPageMockRuntimeDispatchResult = {
  effects: RuntimeEffect[];
  state: RuntimeState<MainPageSnapshot>;
  warnings: RuntimeWarning[];
};

export type MainPageMockRuntimeSnapshotLoadResult =
  MainPageMockRuntimeDispatchResult & {
    metadata: MainPageStateMetadata;
  };

export class MainPageMockRuntimeFacade {
  private readonly compareCursor: RuntimeReducerOptions["compareCursor"];
  private readonly loadSnapshotFn: (stateId: string) => Promise<MainPageMockSnapshot>;
  private currentStateId: string | null = null;
  private metadataValue: MainPageStateMetadata | null = null;
  private stateValue = createInitialRuntimeState<MainPageSnapshot>("main");

  constructor(options: MainPageMockRuntimeFacadeOptions = {}) {
    this.compareCursor = options.compareCursor;
    this.loadSnapshotFn = options.loadSnapshot ?? loadMainPageMockSnapshot;
  }

  get state(): RuntimeState<MainPageSnapshot> {
    return this.stateValue;
  }

  get metadata(): MainPageStateMetadata | null {
    return this.metadataValue;
  }

  async load(
    stateId: string,
  ): Promise<MainPageMockRuntimeSnapshotLoadResult> {
    const runtimeSnapshot = await this.loadSnapshotFn(stateId);
    this.currentStateId = stateId;
    this.metadataValue = runtimeSnapshot.metadata;

    const result = this.dispatch({
      kind: "snapshot.loaded",
      page: "main",
      snapshot: runtimeSnapshot.snapshot,
    });

    return {
      ...result,
      metadata: runtimeSnapshot.metadata,
    };
  }

  dispatch(action: RuntimeAction): MainPageMockRuntimeDispatchResult {
    const result = reduceRuntimeState(this.stateValue, action, {
      compareCursor: this.compareCursor,
    });
    this.stateValue = result.state as RuntimeState<MainPageSnapshot>;

    return {
      effects: result.effects,
      state: this.stateValue,
      warnings: result.warnings,
    };
  }

  receiveEvent(event: UiEvent): MainPageMockRuntimeDispatchResult {
    return this.dispatch({ event, kind: "event.received" });
  }

  applyCommandResponse(
    response: CommandResponse,
    options: {
      fallbackCommandId: string;
      target?: RuntimeCommandTarget;
    },
  ): MainPageMockRuntimeDispatchResult {
    if (response.ok && response.result?.status === "accepted") {
      return this.dispatch({
        kind: "command.accepted",
        result: response.result,
        target: options.target,
      });
    }

    return this.dispatch({
      commandId: response.result?.commandId ?? options.fallbackCommandId,
      error:
        response.error ??
        new Error("Command failed without a structured API error."),
      kind: "command.failed",
    });
  }

  async flushMockEffects(
    effects: readonly RuntimeEffect[],
    options: {
      nextStateId?: string;
    } = {},
  ): Promise<MainPageMockRuntimeDispatchResult | null> {
    const effect = effects.find(
      (candidate) =>
        candidate.kind === "resync" ||
        (candidate.kind === "query_snapshot" && candidate.page === "main"),
    );

    if (!effect) {
      return null;
    }

    const nextStateId = options.nextStateId ?? this.currentStateId;
    if (nextStateId === null) {
      return this.dispatch({
        error: new Error("Cannot flush mock runtime effects before load()."),
        kind: "resync.failed",
      });
    }

    const runtimeSnapshot = await this.loadSnapshotFn(nextStateId);
    this.currentStateId = nextStateId;
    this.metadataValue = runtimeSnapshot.metadata;

    return this.dispatch(
      effect.kind === "resync"
        ? { kind: "resync.finished", snapshot: runtimeSnapshot.snapshot }
        : {
            kind: "snapshot.loaded",
            page: "main",
            snapshot: runtimeSnapshot.snapshot,
          },
    );
  }
}

export function createMainPageMockRuntimeFacade(
  options: MainPageMockRuntimeFacadeOptions = {},
): MainPageMockRuntimeFacade {
  return new MainPageMockRuntimeFacade(options);
}
