import type {
  AppendSessionInputPayload,
  AppendTaskInputPayload,
  CreateSessionPayload,
  GenerateTaskTreePayload,
  PublishTaskTreePayload,
  RenameSessionPayload,
  ResolveConfirmationPayload,
  SessionLifecycleResult,
  UpdateTaskNodePayload,
} from "../../../shared/api/platoApi";
import type {
  CommandRequest,
  CommandResponse,
  ConfirmationId,
  MainPageSnapshot,
  SessionId,
  TaskNodeId,
  UiEvent,
} from "../../../shared/api/types";
import type { BadgeTone } from "../../../shared/components";

export type MainPageDetailMode =
  | "workflow"
  | "session"
  | "task"
  | "editing"
  | "confirmation"
  | "result"
  | "fileChanges";

export type MainPageDetail = {
  actionLabel?: string;
  body: string;
  eyebrow: string;
  mode: MainPageDetailMode;
  title: string;
};

export type MainPageInputScope = {
  label: string;
  placeholder: string;
};

export type MainPageStateMetadata = {
  detail: MainPageDetail;
  id: string;
  initialSelectedTaskNodeId: string | null;
  inputScope: MainPageInputScope;
  label: string;
  topStatus: string;
  topStatusTone: BadgeTone;
};

export type MainPageRuntimeSnapshot = {
  metadata: MainPageStateMetadata;
  snapshot: MainPageSnapshot;
};

export type MainPageRuntimeKind = "mock" | "http";

export type LoadMainPageSnapshot = (
  stateId: string,
  sessionId?: SessionId | null,
) => Promise<MainPageRuntimeSnapshot>;

export type SessionLifecycleCommand<TPayload = void> = (
  payload: TPayload,
) => Promise<SessionLifecycleResult>;

export type ResolveConfirmationCommand = (
  sessionId: SessionId,
  confirmationId: ConfirmationId,
  request: CommandRequest<ResolveConfirmationPayload>,
) => Promise<CommandResponse>;

export type AppendSessionInputCommand = (
  request: CommandRequest<AppendSessionInputPayload>,
) => Promise<CommandResponse>;

export type AppendTaskInputCommand = (
  sessionId: SessionId,
  taskNodeId: string,
  request: CommandRequest<AppendTaskInputPayload>,
) => Promise<CommandResponse>;

export type GenerateTaskTreeCommand = (
  request: CommandRequest<GenerateTaskTreePayload>,
) => Promise<CommandResponse>;

export type UpdateTaskNodeCommand = (
  sessionId: SessionId,
  taskNodeId: TaskNodeId,
  request: CommandRequest<UpdateTaskNodePayload>,
) => Promise<CommandResponse>;

export type PublishTaskTreeCommand = (
  request: CommandRequest<PublishTaskTreePayload>,
) => Promise<CommandResponse>;

export type SubscribeSessionEvents = (
  sessionId: SessionId,
  cursor: string | null,
  onEvent: (event: UiEvent) => void,
) => () => void;

export type MainPageAdapter = {
  appendSessionInput: AppendSessionInputCommand;
  appendTaskInput: AppendTaskInputCommand;
  createSession: SessionLifecycleCommand<CreateSessionPayload>;
  deleteSession: SessionLifecycleCommand<SessionId>;
  generateTaskTree: GenerateTaskTreeCommand;
  loadSnapshot: LoadMainPageSnapshot;
  publishTaskTree: PublishTaskTreeCommand;
  renameSession: SessionLifecycleCommand<
    RenameSessionPayload & { sessionId: SessionId }
  >;
  resolveConfirmation: ResolveConfirmationCommand;
  runtimeKind: MainPageRuntimeKind;
  sessionId: SessionId | null;
  showStatePicker: boolean;
  subscribeSessionEvents: SubscribeSessionEvents;
  updateTaskNode: UpdateTaskNodeCommand;
};

export function mainPageSnapshotQueryKey(
  adapter: Pick<MainPageAdapter, "runtimeKind" | "sessionId">,
  stateId: string,
  activeSessionId?: SessionId | null,
):
  | readonly ["main-page", "fixture", string]
  | readonly ["main-page", "snapshot", string] {
  if (adapter.runtimeKind === "http") {
    return [
      "main-page",
      "snapshot",
      activeSessionId ?? adapter.sessionId ?? "unknown-session",
    ];
  }

  return ["main-page", "fixture", stateId];
}

export function mainPageSnapshotIdentity(
  adapter: Pick<MainPageAdapter, "runtimeKind" | "sessionId">,
  stateId: string,
  snapshot: MainPageRuntimeSnapshot,
  activeSessionId?: SessionId | null,
): string {
  if (adapter.runtimeKind === "http") {
    return `session:${
      activeSessionId ?? adapter.sessionId ?? snapshot.snapshot.session.id
    }`;
  }

  return `fixture:${stateId}`;
}
