import type {
  AppendSessionInputPayload,
  AppendTaskInputPayload,
  AnswerAskPayload,
  AnswerAuthoringAskBatchPayload,
  CancelAskPayload,
  DeferAskPayload,
  CreateSessionPayload,
  GenerateTaskTreePayload,
  PublishTaskTreePayload,
  RepairAuthoringStatePayload,
  RenameSessionPayload,
  ResolveConfirmationPayload,
  RetryTaskPayload,
  SessionLifecycleResult,
  StopTaskPayload,
  UpdateTaskNodePayload,
  WorkspaceCatalogResult,
} from "../../../shared/api/platoApi";
import type {
  CommandRequest,
  CommandResponse,
  AskId,
  ConfirmationId,
  MainPageSnapshot,
  SessionId,
  TaskNodeId,
  UiEvent,
  WorkspaceId,
} from "../../../shared/api/types";
import type {
  TokenUsageSummaryRequest,
  TokenUsageSummaryResponse,
} from "../../../shared/api/tokenUsageTypes";
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
  description?: string | null;
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
  workspaceId?: WorkspaceId | null,
) => Promise<MainPageRuntimeSnapshot>;

export type LoadTokenUsageSummary = (
  request: TokenUsageSummaryRequest,
  workspaceId?: WorkspaceId | null,
) => Promise<TokenUsageSummaryResponse>;

export type SessionLifecycleCommand<TPayload = void> = (
  payload: TPayload,
  workspaceId?: WorkspaceId | null,
) => Promise<SessionLifecycleResult>;

export type ResolveConfirmationCommand = (
  sessionId: SessionId,
  confirmationId: ConfirmationId,
  request: CommandRequest<ResolveConfirmationPayload>,
  workspaceId?: WorkspaceId | null,
) => Promise<CommandResponse>;

export type AnswerAskCommand = (
  sessionId: SessionId,
  askId: AskId,
  request: CommandRequest<AnswerAskPayload>,
  workspaceId?: WorkspaceId | null,
) => Promise<CommandResponse>;

export type AnswerAuthoringAskBatchCommand = (
  sessionId: SessionId,
  rawTaskId: string,
  request: CommandRequest<AnswerAuthoringAskBatchPayload>,
  workspaceId?: WorkspaceId | null,
) => Promise<CommandResponse>;

export type DeferAskCommand = (
  sessionId: SessionId,
  askId: AskId,
  request: CommandRequest<DeferAskPayload>,
  workspaceId?: WorkspaceId | null,
) => Promise<CommandResponse>;

export type CancelAskCommand = (
  sessionId: SessionId,
  askId: AskId,
  request: CommandRequest<CancelAskPayload>,
  workspaceId?: WorkspaceId | null,
) => Promise<CommandResponse>;

export type AppendSessionInputCommand = (
  request: CommandRequest<AppendSessionInputPayload>,
  workspaceId?: WorkspaceId | null,
) => Promise<CommandResponse>;

export type AppendTaskInputCommand = (
  sessionId: SessionId,
  taskNodeId: string,
  request: CommandRequest<AppendTaskInputPayload>,
  workspaceId?: WorkspaceId | null,
) => Promise<CommandResponse>;

export type GenerateTaskTreeCommand = (
  request: CommandRequest<GenerateTaskTreePayload>,
  workspaceId?: WorkspaceId | null,
) => Promise<CommandResponse>;

export type UpdateTaskNodeCommand = (
  sessionId: SessionId,
  taskNodeId: TaskNodeId,
  request: CommandRequest<UpdateTaskNodePayload>,
  workspaceId?: WorkspaceId | null,
) => Promise<CommandResponse>;

export type PublishTaskTreeCommand = (
  request: CommandRequest<PublishTaskTreePayload>,
  workspaceId?: WorkspaceId | null,
) => Promise<CommandResponse>;

export type RepairAuthoringStateCommand = (
  request: CommandRequest<RepairAuthoringStatePayload>,
  workspaceId?: WorkspaceId | null,
) => Promise<CommandResponse>;

export type RetryTaskCommand = (
  sessionId: SessionId,
  taskNodeId: TaskNodeId,
  request: CommandRequest<RetryTaskPayload>,
  workspaceId?: WorkspaceId | null,
) => Promise<CommandResponse>;

export type StopTaskCommand = (
  sessionId: SessionId,
  taskNodeId: TaskNodeId,
  request: CommandRequest<StopTaskPayload>,
  workspaceId?: WorkspaceId | null,
) => Promise<CommandResponse>;

export type SubscribeSessionEvents = (
  sessionId: SessionId,
  cursor: string | null,
  onEvent: (event: UiEvent) => void,
  workspaceId?: WorkspaceId | null,
) => () => void;

export type MainPageAdapter = {
  answerAsk: AnswerAskCommand;
  answerAuthoringAskBatch: AnswerAuthoringAskBatchCommand;
  appendSessionInput: AppendSessionInputCommand;
  appendTaskInput: AppendTaskInputCommand;
  cancelAsk: CancelAskCommand;
  createSession: SessionLifecycleCommand<CreateSessionPayload>;
  deferAsk: DeferAskCommand;
  deleteSession: SessionLifecycleCommand<SessionId>;
  generateTaskTree: GenerateTaskTreeCommand;
  loadSnapshot: LoadMainPageSnapshot;
  loadTokenUsageSummary?: LoadTokenUsageSummary;
  loadWorkspaceCatalog?: () => Promise<WorkspaceCatalogResult>;
  publishTaskTree: PublishTaskTreeCommand;
  repairAuthoringState: RepairAuthoringStateCommand;
  renameSession: SessionLifecycleCommand<
    RenameSessionPayload & { sessionId: SessionId }
  >;
  retryTask: RetryTaskCommand;
  resolveConfirmation: ResolveConfirmationCommand;
  runtimeKind: MainPageRuntimeKind;
  sessionId: SessionId | null;
  showStatePicker: boolean;
  stopTask: StopTaskCommand;
  subscribeSessionEvents: SubscribeSessionEvents;
  updateTaskNode: UpdateTaskNodeCommand;
  workspaceId?: WorkspaceId | null;
};

export function mainPageSnapshotQueryKey(
  adapter: Pick<MainPageAdapter, "runtimeKind" | "sessionId" | "workspaceId">,
  stateId: string,
  activeSessionId?: SessionId | null,
  activeWorkspaceId?: WorkspaceId | null,
):
  | readonly ["main-page", "fixture", string]
  | readonly ["main-page", "snapshot", string, string] {
  if (adapter.runtimeKind === "http") {
    return [
      "main-page",
      "snapshot",
      activeWorkspaceId ?? adapter.workspaceId ?? "current-workspace",
      activeSessionId ?? adapter.sessionId ?? "unknown-session",
    ];
  }

  return ["main-page", "fixture", stateId];
}

export function mainPageSnapshotIdentity(
  adapter: Pick<MainPageAdapter, "runtimeKind" | "sessionId" | "workspaceId">,
  stateId: string,
  snapshot: MainPageRuntimeSnapshot,
  activeSessionId?: SessionId | null,
  activeWorkspaceId?: WorkspaceId | null,
): string {
  if (adapter.runtimeKind === "http") {
    return `workspace:${activeWorkspaceId ?? adapter.workspaceId ?? "current"}:session:${
      activeSessionId ?? adapter.sessionId ?? snapshot.snapshot.session.id
    }`;
  }

  return `fixture:${stateId}`;
}
