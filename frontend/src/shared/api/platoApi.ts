import type {
  AskId,
  AskListResult,
  AuditEntryKind,
  AuditFilterKind,
  AuditPageSnapshot,
  AuditRecord,
  AuditRecordDetail,
  AuditRecordId,
  AuditRecordKind,
  CommandRequest,
  CommandResponse,
  ConfirmationId,
  EvidenceDetail,
  EvidenceId,
  EventCursor,
  MainPageSnapshot,
  ProductRecoveryAction,
  QueryResponse,
  RuntimeInputRouteRequest,
  RuntimeInputRouteResult,
  SessionActivityTimelineResult,
  SessionId,
  SessionSummary,
  TaskNodeId,
  UiEvent,
  UiEventType,
  WorkspaceId,
} from "./types";
export type { ProductRecoveryAction } from "./types";
import type {
  TokenUsageSummaryRequest,
  TokenUsageSummaryResponse,
} from "./tokenUsageTypes";
import { ApiClient } from "./client";
import type { ApiClientOptions } from "./client";
import {
  createFrontendLogger,
  toLoggableError,
} from "../logging/frontendLogger";
import { summarizeCommandResponse, summarizeUiEvent } from "./traceSummary";

export type CreateSessionPayload = {
  name?: string;
  initialInput?: string;
};

export type RenameSessionPayload = {
  name: string;
};

export type SessionLifecycleResult = {
  deletedSessionId?: SessionId;
  nextSessionId?: SessionId | null;
  session?: Partial<SessionSummary> & { id: SessionId; name: string };
  sessionId?: SessionId;
};

export type SessionListResult = {
  sessions: SessionSummary[];
};

export type SessionActivityRequest = {
  sessionId: SessionId;
  limit?: number;
  cursor?: EventCursor | null;
};

export type WorkspaceRouteOptions = {
  workspaceId?: WorkspaceId | null;
};

export type WorkspaceStatus =
  | "available"
  | "unavailable"
  | "starting"
  | "failed";

export type WorkspaceCatalogEntry = {
  workspaceId: WorkspaceId;
  label: string;
  status: WorkspaceStatus;
  isCurrent: boolean;
  sessionCount: number;
  recentSessions: SessionSummary[];
  updatedAt: string | null;
};

export type WorkspaceCatalogResult = {
  currentWorkspaceId: WorkspaceId;
  workspaces: WorkspaceCatalogEntry[];
};

export type AppendSessionInputPayload = {
  content: string;
  mode: "global_guidance" | "generate_task_tree";
};

export type GenerateTaskTreePayload = {
  prompt: string;
  context?: Record<string, unknown>;
};

export type UpdateTaskNodePayload = {
  title?: string;
  summary?: string;
  fullIntent?: string;
  constraints?: string[];
  updateMode?: "node_fields" | "replace_children" | "replace_subtree";
  preserveRootId?: boolean;
};

export type AppendTaskInputPayload = {
  content: string;
  mode: "guidance" | "revision_request" | "clarification_answer";
};

export type PublishTaskTreePayload = {
  taskTreeId: string;
  startImmediately: boolean;
};

export type RetryTaskPayload = {
  instruction?: string;
  startImmediately: boolean;
};

export type StopTaskPayload = {
  reason?: string;
};

export type ResolveConfirmationPayload = {
  value: string;
  note?: string;
};

export type AnswerAskPayload = {
  selectedOptionIds: string[];
  text?: string | null;
};

export type AnswerAuthoringAskItemPayload = {
  askId: string;
  value: string;
};

export type AnswerAuthoringAskBatchPayload = {
  answers: AnswerAuthoringAskItemPayload[];
};

export type DeferAskPayload = {
  reason?: string | null;
};

export type CancelAskPayload = {
  reason: string;
};

export type RepairAuthoringStatePayload = {
  reason: "dirty_authoring_state";
};

export type ListAsksRequest = {
  sessionId: SessionId;
  status?: string;
  taskNodeId?: TaskNodeId;
};

export type AuditSnapshotRequest = {
  sessionId: SessionId;
  taskNodeId?: TaskNodeId;
  entry?: AuditEntryKind;
  filter?: AuditFilterKind;
  recordId?: AuditRecordId;
  includeDetail?: boolean;
  limit?: number;
  cursor?: string | null;
};

export type AuditRecordsRequest = {
  sessionId: SessionId;
  taskNodeId?: TaskNodeId;
  filter?: AuditFilterKind;
  kind?: AuditRecordKind;
  from?: string;
  to?: string;
  limit?: number;
  cursor?: string | null;
  includeHiddenReasons?: boolean;
};

export type AuditRecordsResult = {
  records: AuditRecord[];
  nextCursor: string | null;
  totalCount: number | null;
};

export type AuditRecordDetailRequest = {
  sessionId: SessionId;
  recordId: AuditRecordId;
  includeEvidence?: boolean;
  includeSanitizedPayload?: boolean;
};

export type EvidenceDetailRequest = {
  sessionId: SessionId;
  evidenceId: EvidenceId;
  includeSanitizedPayload?: boolean;
};

export type DiagnosticExportSection = {
  name: string;
  status: "included" | "partial" | "missing" | "skipped";
  warnings: string[];
};

export type DiagnosticBundleExportResult = {
  schemaVersion: "plato.diagnostics_export.v1";
  bundleId: string;
  bundleDir: string;
  bundleDirLabel: string;
  zipPath: string | null;
  zipPathLabel: string | null;
  manifestPath: string;
  manifestPathLabel: string;
  createdAt: string;
  redactionProfile: string;
  includedSections: string[];
  sections: DiagnosticExportSection[];
  warnings: string[];
  fileCount: number;
};

export type SettingsReadinessStatus =
  | "ready"
  | "needs_configuration"
  | "degraded";

export type SettingsReadinessIssue = {
  code: string;
  severity: "blocking" | "warning";
  message: string;
  recoveryActions: ProductRecoveryAction[];
  envVars: string[];
};

export type SettingsReadinessFirstRun = {
  ready: boolean;
  blockingIssueCodes: string[];
  recommendedActions: ProductRecoveryAction[];
};

export type SettingsReadinessThinking = {
  configured: boolean;
  enabled?: boolean | null;
  effort?: string | null;
};

export type SettingsReadinessOpenRouterRouting = {
  configured: boolean;
  invalidEnvVars: string[];
  providerOrderCount: number;
  providerOnlyCount: number;
  providerIgnoreCount: number;
  allowFallbacks?: boolean | null;
  requireParameters?: boolean | null;
  dataCollectionConfigured: boolean;
  zdr?: boolean | null;
};

export type SettingsReadinessLlm = {
  provider: string;
  providerSource: "default" | "env";
  model: string;
  modelSource: "default" | "env";
  configured: boolean;
  apiKeyConfigured: boolean;
  missingEnvVars: string[];
  requestTimeoutSeconds: number | null;
  requestTimeoutConfigured: boolean;
  requestTimeoutValid: boolean;
  thinking: SettingsReadinessThinking;
  routing?: SettingsReadinessOpenRouterRouting | null;
};

export type SettingsReadinessLoggingProfile = {
  id: string;
  description: string;
};

export type SettingsReadinessLogging = {
  enabled: boolean;
  level: string;
  selectedProfile?: string | null;
  selectedProfileKnown: boolean;
  defaultProfile?: string | null;
  profiles: SettingsReadinessLoggingProfile[];
};

export type SettingsReadinessDiagnostics = {
  bundleExportAvailable: boolean;
  httpExportRouteAvailable: boolean;
  cliCommandTemplate: string;
};

export type SettingsReadinessReport = {
  schemaVersion: "plato.settings_readiness.v1";
  generatedAt: string;
  workspaceRootLabel: string;
  status: SettingsReadinessStatus;
  firstRun: SettingsReadinessFirstRun;
  llm: SettingsReadinessLlm;
  logging: SettingsReadinessLogging;
  diagnostics: SettingsReadinessDiagnostics;
  blockingIssues: SettingsReadinessIssue[];
  warnings: SettingsReadinessIssue[];
};

export type SettingsProvider = "litellm" | "deepseek" | "openrouter";

export type SettingsWebSearchProvider = "tavily";

export type SettingsConfigSource = "default" | "env" | "stored";

export type SettingsApiKeySource = "none" | "env" | "stored";

export type SettingsWebSearchStatus = "disabled" | "missing_key" | "ready";

export type SettingsConfigProviderOption = {
  id: SettingsProvider;
  label: string;
  requiredApiKeyEnvVars: string[];
  preferredApiKeyEnvVar: string;
};

export type SettingsConfigWebSearchProviderOption = {
  id: SettingsWebSearchProvider;
  label: string;
  requiredApiKeyEnvVars: string[];
  preferredApiKeyEnvVar: string;
};

export type SettingsConfigSummary = {
  schemaVersion: "plato.settings_config.v1";
  generatedAt: string;
  workspaceRootLabel: string;
  llm: {
    provider: string;
    providerSource: SettingsConfigSource;
    providerOptions: SettingsConfigProviderOption[];
    model: string;
    modelSource: SettingsConfigSource;
    apiKeyConfigured: boolean;
    apiKeySource: SettingsApiKeySource;
    apiKeyEnvVar: string;
  };
  webSearch: {
    enabled: boolean;
    provider: string;
    providerSource: SettingsConfigSource;
    providerOptions: SettingsConfigWebSearchProviderOption[];
    mode: string;
    maxResults: number;
    fetchEnabled: boolean;
    fetchMaxUrls: number;
    fetchMaxCharsPerUrl: number;
    fetchMaxTotalChars: number;
    fetchStatus: SettingsWebSearchStatus;
    apiKeyConfigured: boolean;
    apiKeySource: SettingsApiKeySource;
    apiKeyEnvVar: string;
    status: SettingsWebSearchStatus;
  };
  logging: {
    enabled: boolean;
    level: string;
    selectedProfile?: string | null;
    selectedProfileSource: SettingsConfigSource;
    selectedProfileKnown: boolean;
    defaultProfile?: string | null;
    profiles: SettingsReadinessLoggingProfile[];
  };
  diagnostics: {
    bundleExportAvailable: boolean;
    httpExportRouteAvailable: boolean;
  };
};

export type UpdateSettingsConfigPayload = {
  llm?: {
    provider: SettingsProvider;
    model: string;
    apiKey?: string;
  };
  logging?: {
    selectedProfile?: string | null;
  };
  webSearch?: {
    enabled: boolean;
    provider: SettingsWebSearchProvider;
    mode: "basic";
    maxResults: number;
    fetchEnabled?: boolean;
    fetchMaxUrls?: number;
    fetchMaxCharsPerUrl?: number;
    fetchMaxTotalChars?: number;
    apiKey?: string;
  };
};

export type SettingsConfigUpdateResult = {
  schemaVersion: "plato.settings_config_update.v1";
  updatedAt: string;
  config: SettingsConfigSummary;
  readiness: SettingsReadinessReport;
};

export type PlatoApi = {
  getSettingsReadiness(): Promise<QueryResponse<SettingsReadinessReport>>;
  recheckSettingsReadiness(): Promise<QueryResponse<SettingsReadinessReport>>;
  getSettingsConfig(): Promise<QueryResponse<SettingsConfigSummary>>;
  updateSettingsConfig(
    payload: UpdateSettingsConfigPayload,
  ): Promise<QueryResponse<SettingsConfigUpdateResult>>;
  listWorkspaces(): Promise<QueryResponse<WorkspaceCatalogResult>>;
  listSessions(
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<SessionListResult>>;
  createSession(
    payload: CreateSessionPayload,
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<SessionLifecycleResult>>;
  getSessionSnapshot(
    sessionId: SessionId,
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<MainPageSnapshot>>;
  getSessionActivity(
    request: SessionActivityRequest,
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<SessionActivityTimelineResult>>;
  routeRuntimeInput(
    request: RuntimeInputRouteRequest,
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<RuntimeInputRouteResult>>;
  getAuditSnapshot(
    request: AuditSnapshotRequest,
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<AuditPageSnapshot>>;
  listAuditRecords(
    request: AuditRecordsRequest,
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<AuditRecordsResult>>;
  getAuditRecordDetail(
    request: AuditRecordDetailRequest,
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<AuditRecordDetail>>;
  getEvidenceDetail(
    request: EvidenceDetailRequest,
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<EvidenceDetail>>;
  exportDiagnosticBundle(
    sessionId: SessionId,
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<DiagnosticBundleExportResult>>;
  getTokenUsageSummary(
    request: TokenUsageSummaryRequest,
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<TokenUsageSummaryResponse>>;
  renameSession(
    sessionId: SessionId,
    payload: RenameSessionPayload,
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<SessionLifecycleResult>>;
  deleteSession(
    sessionId: SessionId,
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<SessionLifecycleResult>>;
  appendSessionInput(
    request: CommandRequest<AppendSessionInputPayload>,
    options?: WorkspaceRouteOptions,
  ): Promise<CommandResponse>;
  generateTaskTree(
    request: CommandRequest<GenerateTaskTreePayload>,
    options?: WorkspaceRouteOptions,
  ): Promise<CommandResponse>;
  updateTaskNode(
    sessionId: SessionId,
    taskNodeId: TaskNodeId,
    request: CommandRequest<UpdateTaskNodePayload>,
    options?: WorkspaceRouteOptions,
  ): Promise<CommandResponse>;
  appendTaskInput(
    sessionId: SessionId,
    taskNodeId: TaskNodeId,
    request: CommandRequest<AppendTaskInputPayload>,
    options?: WorkspaceRouteOptions,
  ): Promise<CommandResponse>;
  publishTaskTree(
    request: CommandRequest<PublishTaskTreePayload>,
    options?: WorkspaceRouteOptions,
  ): Promise<CommandResponse>;
  retryTask(
    sessionId: SessionId,
    taskNodeId: TaskNodeId,
    request: CommandRequest<RetryTaskPayload>,
    options?: WorkspaceRouteOptions,
  ): Promise<CommandResponse>;
  stopTask(
    sessionId: SessionId,
    taskNodeId: TaskNodeId,
    request: CommandRequest<StopTaskPayload>,
    options?: WorkspaceRouteOptions,
  ): Promise<CommandResponse>;
  resolveConfirmation(
    sessionId: SessionId,
    confirmationId: ConfirmationId,
    request: CommandRequest<ResolveConfirmationPayload>,
    options?: WorkspaceRouteOptions,
  ): Promise<CommandResponse>;
  listAsks(
    request: ListAsksRequest,
    options?: WorkspaceRouteOptions,
  ): Promise<QueryResponse<AskListResult>>;
  answerAsk(
    sessionId: SessionId,
    askId: AskId,
    request: CommandRequest<AnswerAskPayload>,
    options?: WorkspaceRouteOptions,
  ): Promise<CommandResponse>;
  answerAuthoringAskBatch(
    sessionId: SessionId,
    rawTaskId: string,
    request: CommandRequest<AnswerAuthoringAskBatchPayload>,
    options?: WorkspaceRouteOptions,
  ): Promise<CommandResponse>;
  repairAuthoringState(
    request: CommandRequest<RepairAuthoringStatePayload>,
    options?: WorkspaceRouteOptions,
  ): Promise<CommandResponse>;
  deferAsk(
    sessionId: SessionId,
    askId: AskId,
    request: CommandRequest<DeferAskPayload>,
    options?: WorkspaceRouteOptions,
  ): Promise<CommandResponse>;
  cancelAsk(
    sessionId: SessionId,
    askId: AskId,
    request: CommandRequest<CancelAskPayload>,
    options?: WorkspaceRouteOptions,
  ): Promise<CommandResponse>;
  subscribeSessionEvents(
    sessionId: SessionId,
    cursor: EventCursor | null,
    onEvent: (event: UiEvent) => void,
    options?: WorkspaceRouteOptions,
  ): () => void;
};

export type EventSourceLike = {
  addEventListener(
    type: string,
    listener: (event: { data: string }) => void,
  ): void;
  close(): void;
};

export type EventSourceFactory = (url: string) => EventSourceLike;

export type HttpPlatoApiOptions = ApiClientOptions & {
  eventSourceFactory?: EventSourceFactory;
};

const uiEventTypes: UiEventType[] = [
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
];

const platoApiLogger = createFrontendLogger("plato-api");

export function createHttpPlatoApi(options: HttpPlatoApiOptions): PlatoApi {
  const client = new ApiClient(options);
  const eventSourceFactory =
    options.eventSourceFactory ?? createDefaultEventSource;

  return {
    getSettingsReadiness() {
      return client.getJson<QueryResponse<SettingsReadinessReport>>(
        "/api/v1/settings/readiness",
      );
    },
    recheckSettingsReadiness() {
      return client.postJson<QueryResponse<SettingsReadinessReport>>(
        "/api/v1/settings/readiness/recheck",
        {},
      );
    },
    getSettingsConfig() {
      return client.getJson<QueryResponse<SettingsConfigSummary>>(
        "/api/v1/settings/config",
      );
    },
    updateSettingsConfig(payload) {
      return client.patchJson<QueryResponse<SettingsConfigUpdateResult>>(
        "/api/v1/settings/config",
        payload,
      );
    },
    listWorkspaces() {
      return client.getJson<QueryResponse<WorkspaceCatalogResult>>(
        "/api/v1/workspaces",
      );
    },
    listSessions(options) {
      return client.getJson<QueryResponse<SessionListResult>>(
        sessionsBase(options),
      );
    },
    createSession(payload, options) {
      return client.postJson<QueryResponse<SessionLifecycleResult>>(
        sessionsBase(options),
        payload,
      );
    },
    getSessionSnapshot(sessionId, options) {
      return client.getJson<QueryResponse<MainPageSnapshot>>(
        `${sessionBase(sessionId, options)}/snapshot`,
      );
    },
    getSessionActivity(request, options) {
      return client.getJson<QueryResponse<SessionActivityTimelineResult>>(
        withQuery(`${sessionBase(request.sessionId, options)}/activity`, {
          cursor: request.cursor ?? undefined,
          limit: numberQuery(request.limit),
        }),
      );
    },
    routeRuntimeInput(request, options) {
      return client.postJson<QueryResponse<RuntimeInputRouteResult>>(
        `${sessionBase(request.sessionId, options)}/runtime-input/route`,
        request,
      );
    },
    getAuditSnapshot(request, options) {
      return client.getJson<QueryResponse<AuditPageSnapshot>>(
        withQuery(auditBasePath(request, options), {
          cursor: request.cursor ?? undefined,
          entry: request.entry,
          filter: request.filter,
          includeDetail: booleanQuery(request.includeDetail),
          limit: numberQuery(request.limit),
          recordId: request.recordId,
        }),
      );
    },
    listAuditRecords(request, options) {
      return client.getJson<QueryResponse<AuditRecordsResult>>(
        withQuery(`${auditBasePath(request, options)}/records`, {
          cursor: request.cursor ?? undefined,
          filter: request.filter,
          from: request.from,
          includeHiddenReasons: booleanQuery(request.includeHiddenReasons),
          kind: request.kind,
          limit: numberQuery(request.limit),
          to: request.to,
        }),
      );
    },
    getAuditRecordDetail(request, options) {
      return client.getJson<QueryResponse<AuditRecordDetail>>(
        withQuery(
          `${sessionBase(request.sessionId, options)}/audit/records/${segment(
            request.recordId,
          )}`,
          {
            includeEvidence: booleanQuery(request.includeEvidence),
            includeSanitizedPayload: booleanQuery(
              request.includeSanitizedPayload,
            ),
          },
        ),
      );
    },
    getEvidenceDetail(request, options) {
      return client.getJson<QueryResponse<EvidenceDetail>>(
        withQuery(
          `${sessionBase(request.sessionId, options)}/audit/evidence/${segment(
            request.evidenceId,
          )}`,
          {
            includeSanitizedPayload: booleanQuery(
              request.includeSanitizedPayload,
            ),
          },
        ),
      );
    },
    exportDiagnosticBundle(sessionId, options) {
      return client.postJson<QueryResponse<DiagnosticBundleExportResult>>(
        `${sessionBase(sessionId, options)}/diagnostics/export`,
        {},
      );
    },
    getTokenUsageSummary(request, options) {
      return client.getJson<QueryResponse<TokenUsageSummaryResponse>>(
        withQuery(usageBase(options), {
          dimension: request.dimension,
          from: request.from,
          model: request.model,
          planId: request.planId,
          provider: request.provider,
          sessionId: request.sessionId,
          taskNodeId: request.taskNodeId,
          to: request.to,
        }),
      );
    },
    renameSession(sessionId, payload, options) {
      return client.patchJson<QueryResponse<SessionLifecycleResult>>(
        sessionBase(sessionId, options),
        payload,
      );
    },
    deleteSession(sessionId, options) {
      return client.postJson<QueryResponse<SessionLifecycleResult>>(
        `${sessionBase(sessionId, options)}/delete`,
        {},
      );
    },
    appendSessionInput(request, options) {
      return client.postJson<CommandResponse>(
        `${sessionBase(request.sessionId, options)}/input`,
        request,
      );
    },
    generateTaskTree(request, options) {
      return client.postJson<CommandResponse>(
        `${sessionBase(request.sessionId, options)}/task-tree/generate`,
        request,
      );
    },
    updateTaskNode(sessionId, taskNodeId, request, options) {
      return client.patchJson<CommandResponse>(
        `${sessionBase(sessionId, options)}/tasks/${segment(taskNodeId)}`,
        request,
      );
    },
    appendTaskInput(sessionId, taskNodeId, request, options) {
      return client.postJson<CommandResponse>(
        `${sessionBase(sessionId, options)}/tasks/${segment(taskNodeId)}/input`,
        request,
      );
    },
    publishTaskTree(request, options) {
      return client.postJson<CommandResponse>(
        `${sessionBase(request.sessionId, options)}/task-tree/publish`,
        request,
      );
    },
    retryTask(sessionId, taskNodeId, request, options) {
      return client.postJson<CommandResponse>(
        `${sessionBase(sessionId, options)}/tasks/${segment(taskNodeId)}/retry`,
        request,
      );
    },
    async stopTask(sessionId, taskNodeId, request, options) {
      platoApiLogger.info("command.stop.request", {
        commandId: request.commandId,
        reason: request.payload.reason ?? null,
        sessionId,
        taskNodeId,
      });
      const response = await client.postJson<CommandResponse>(
        `${sessionBase(sessionId, options)}/tasks/${segment(taskNodeId)}/stop`,
        request,
      );
      platoApiLogger.info("command.stop.response", {
        ...summarizeCommandResponse(response),
        commandId: request.commandId,
        sessionId,
        taskNodeId,
      });
      return response;
    },
    resolveConfirmation(sessionId, confirmationId, request, options) {
      return client.postJson<CommandResponse>(
        `${sessionBase(sessionId, options)}/confirmations/${segment(
          confirmationId,
        )}/respond`,
        request,
      );
    },
    listAsks(request, options) {
      return client.getJson<QueryResponse<AskListResult>>(
        withQuery(`${sessionBase(request.sessionId, options)}/asks`, {
          status: request.status,
          taskNodeId: request.taskNodeId,
        }),
      );
    },
    answerAsk(sessionId, askId, request, options) {
      return client.postJson<CommandResponse>(
        `${sessionBase(sessionId, options)}/asks/${segment(askId)}/answer`,
        request,
      );
    },
    answerAuthoringAskBatch(sessionId, rawTaskId, request, options) {
      return client.postJson<CommandResponse>(
        `${sessionBase(sessionId, options)}/authoring/raw-tasks/${segment(
          rawTaskId,
        )}/asks/answers`,
        request,
      );
    },
    repairAuthoringState(request, options) {
      return client.postJson<CommandResponse>(
        `${sessionBase(request.sessionId, options)}/authoring/repair`,
        request,
      );
    },
    deferAsk(sessionId, askId, request, options) {
      return client.postJson<CommandResponse>(
        `${sessionBase(sessionId, options)}/asks/${segment(askId)}/defer`,
        request,
      );
    },
    cancelAsk(sessionId, askId, request, options) {
      return client.postJson<CommandResponse>(
        `${sessionBase(sessionId, options)}/asks/${segment(askId)}/cancel`,
        request,
      );
    },
    subscribeSessionEvents(sessionId, cursor, onEvent, options) {
      const query = cursor === null ? "" : `?cursor=${segment(cursor)}`;
      const url = `${client.baseUrl}${sessionBase(
        sessionId,
        options,
      )}/events${query}`;
      platoApiLogger.info("events.subscribe.start", {
        sessionId,
      });

      let source: EventSourceLike;
      try {
        source = eventSourceFactory(url);
      } catch (error) {
        platoApiLogger.error("events.subscribe.failed", {
          error: toLoggableError(error),
          sessionId,
        });
        throw error;
      }

      const handleEvent = (event: { data: string }) => {
        try {
          const parsed = JSON.parse(event.data) as UiEvent;
          platoApiLogger.debug("events.message", {
            ...summarizeUiEvent(parsed),
          });
          onEvent(parsed);
        } catch (error) {
          platoApiLogger.error("events.message.invalid", {
            error: toLoggableError(error),
            rawData: event.data,
            sessionId,
          });
        }
      };

      source.addEventListener("message", handleEvent);
      for (const eventType of uiEventTypes) {
        source.addEventListener(eventType, handleEvent);
      }

      return () => {
        platoApiLogger.info("events.subscribe.stop", {
          sessionId,
        });
        source.close();
      };
    },
  };
}

function segment(value: string): string {
  return encodeURIComponent(value);
}

function sessionsBase(options?: WorkspaceRouteOptions): string {
  const workspaceId = options?.workspaceId ?? null;
  if (workspaceId) {
    return `/api/v1/workspaces/${segment(workspaceId)}/sessions`;
  }

  return "/api/v1/sessions";
}

function sessionBase(
  sessionId: SessionId,
  options?: WorkspaceRouteOptions,
): string {
  return `${sessionsBase(options)}/${segment(sessionId)}`;
}

function usageBase(options?: WorkspaceRouteOptions): string {
  const workspaceId = options?.workspaceId ?? null;
  if (workspaceId) {
    return `/api/v1/workspaces/${segment(workspaceId)}/usage/token-summary`;
  }

  return "/api/v1/usage/token-summary";
}

function auditBasePath(request: {
  sessionId: SessionId;
  taskNodeId?: TaskNodeId;
}, options?: WorkspaceRouteOptions): string {
  if (request.taskNodeId !== undefined) {
    return `${sessionBase(request.sessionId, options)}/tasks/${segment(
      request.taskNodeId,
    )}/audit`;
  }

  return `${sessionBase(request.sessionId, options)}/audit`;
}

function withQuery(
  path: string,
  query: Record<string, string | undefined>,
): string {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") {
      params.set(key, value);
    }
  }

  const queryString = params.toString();
  return queryString.length > 0 ? `${path}?${queryString}` : path;
}

function booleanQuery(value: boolean | undefined): string | undefined {
  return value === undefined ? undefined : String(value);
}

function numberQuery(value: number | undefined): string | undefined {
  return value === undefined ? undefined : String(value);
}

function createDefaultEventSource(url: string): EventSourceLike {
  if (typeof EventSource === "undefined") {
    throw new Error("EventSource is not available in this environment.");
  }

  return new EventSource(url);
}
