import type {
  AppendSessionInputPayload,
  AppendTaskInputPayload,
  AnswerAskPayload,
  AnswerAuthoringAskBatchPayload,
  ArchivePlanPayload,
  CancelAskPayload,
  DeferAskPayload,
  GenerateTaskTreePayload,
  PublishTaskTreePayload,
  RepairAuthoringStatePayload,
  ResolveConfirmationPayload,
  RetryTaskPayload,
  StopTaskPayload,
  UpdateTaskNodePayload,
} from "../../shared/api/platoApi";
import type {
  AskId,
  CommandRequest,
  CommandResponse,
  ConfirmationId,
  ConfirmationActionView,
  FileChangeSummaryView,
  QueryResponse,
  ResultCardView,
  RuntimeInputRouteResult,
  SessionId,
  SessionMessageView,
  SessionStatus,
  SessionSummary,
  TaskNodeCardView,
  TaskTreeStatus,
  TaskTreeView,
} from "../../shared/api/types";
import type {
  TokenUsageSummaryRequest,
  TokenUsageSummaryResponse,
} from "../../shared/api/tokenUsageTypes";
import {
  deriveLegacyTaskNodeStatusDimensions,
  mapLegacySessionStatusToPlanningState,
  mapLegacyTaskTreeStatusToReadiness,
} from "../../shared/api/statusCompatibility";
import {
  defaultMainPageStateId,
  getMainPageState,
  mainPageStates,
} from "./fixtures";
import { mainPageStateCatalog } from "./mainPageStateCatalog";
import type { MainPageStateId } from "./fixtures";
import type {
  AppendSessionInputCommand,
  AppendTaskInputCommand,
  AnswerAskCommand,
  AnswerAuthoringAskBatchCommand,
  ArchivePlanCommand,
  CancelAskCommand,
  DeferAskCommand,
  GenerateTaskTreeCommand,
  LoadMainPageSnapshot,
  MainPageAdapter,
  MainPageRuntimeSnapshot,
  MainPageStateMetadata as RuntimeMainPageStateMetadata,
  PublishTaskTreeCommand,
  RepairAuthoringStateCommand,
  ResolveConfirmationCommand,
  RouteRuntimeInputCommand,
  StopTaskCommand,
  SubscribeSessionEvents,
  UpdateTaskNodeCommand,
} from "./runtime/adapter";

export type MainPageStateOption = {
  id: MainPageStateId;
  label: string;
};

export type MainPageStateMetadata = MainPageStateOption &
  RuntimeMainPageStateMetadata;

export { defaultMainPageStateId };
export type {
  AppendSessionInputCommand,
  AppendTaskInputCommand,
  AnswerAskCommand,
  AnswerAuthoringAskBatchCommand,
  ArchivePlanCommand,
  CancelAskCommand,
  DeferAskCommand,
  GenerateTaskTreeCommand,
  LoadMainPageSnapshot,
  MainPageAdapter,
  MainPageRuntimeSnapshot as MainPageMockSnapshot,
  MainPageStateId,
  PublishTaskTreeCommand,
  RepairAuthoringStateCommand,
  ResolveConfirmationCommand,
  StopTaskCommand,
  SubscribeSessionEvents,
  UpdateTaskNodeCommand,
};

export function listMainPageStateOptions(): MainPageStateOption[] {
  return mainPageStateCatalog.map((state) => ({
    id: state.id,
    label: state.label,
  }));
}

export function getMainPageMockSnapshot(
  stateId: MainPageStateId,
): MainPageRuntimeSnapshot {
  const fixture = getMainPageState(stateId);
  const sessionStatus = sessionStatusForFixture(fixture.id);
  const activeAsk = activeAskForFixture(fixture.id, fixture.session.id);

  return {
    metadata: {
      id: fixture.id,
      label: fixture.label,
      detail: fixture.detail,
      initialSelectedTaskNodeId: fixture.selectedTaskNodeId,
      inputScope: fixture.inputScope,
      topStatus: fixture.topStatus,
      topStatusTone: fixture.topStatusTone,
    },
    snapshot: {
      schemaVersion: "plato.main.v1",
      project: fixture.project,
      workflows: [
        {
          ...fixture.workflow,
          deliveryKind: "task_tree",
          inputHint: "Describe the work you want Plato to plan.",
        },
      ],
      workflow: {
        ...fixture.workflow,
        deliveryKind: "task_tree",
        inputHint: "Describe the work you want Plato to plan.",
      },
      sessions: fixture.sessions.map(toSessionSummary),
      session: toSessionSummary({
        ...fixture.session,
        status: sessionStatus,
      }),
      planning: {
        asks: planningAsksForFixture(fixture.id),
        state: mapLegacySessionStatusToPlanningState(sessionStatus),
        sourceRawTaskId:
          fixture.id === "s2-understanding" ? "raw-task-website-goal" : null,
        summary: fixture.detail.body,
        title: fixture.detail.title,
        validation: null,
      },
      taskTree: fixture.taskTree
        ? toTaskTreeView(
            fixture.taskTree,
            fixture.session.id,
            sessionStatus,
            fixture.id,
          )
        : null,
      messages: [
        ...fixture.messages.map((message) =>
          fixture.id === "s14-execution-ask" &&
          message.id === "message-execution-ask"
            ? {
                ...message,
                conversationVisibility: "activity_only" as const,
                title: "ASK requested",
              }
            : message,
        ),
        ...conversationAskMessagesForFixture(
          fixture.id,
          fixture.session.id,
          activeAsk,
        ),
      ],
      pendingConfirmations: toPendingConfirmations(fixture),
      pendingAsks: activeAsk ? [activeAsk] : [],
      activeAsk,
      result: fixture.result ? toResultCardView(fixture.result, fixture.session.id) : null,
      fileChangeSummary: fixture.fileChangeSummary
        ? toFileChangeSummaryView(fixture.fileChangeSummary, fixture.session.id)
        : null,
      auditLinks: [
        {
          label: "View audit",
          href: `/sessions/${fixture.session.id}/audit`,
          severity: fixture.id === "s9-file-changes" ? "warning" : "info",
        },
      ],
      auditSummary: {
        completeness: fixture.id === "s9-file-changes" ? "partial" : "not_started",
        href: `/sessions/${fixture.session.id}/audit`,
        summary:
          fixture.id === "s9-file-changes"
            ? "Audit has a warning for file-change validation coverage."
            : "Audit is not available for this state yet.",
        updatedAt: "2026-05-17T10:20:00+08:00",
        verdict: fixture.id === "s9-file-changes" ? "warning" : "not_available",
      },
      permissions: permissionsForFixture(fixture.id),
      cursor: `cursor-${fixture.id}`,
      generatedAt: "2026-05-17T10:20:00+08:00",
    },
  };
}

export async function loadMainPageMockSnapshot(
  stateId: string,
): Promise<MainPageRuntimeSnapshot> {
  await delay(40);

  return getMainPageMockSnapshot(stateId as MainPageStateId);
}

export async function resolveConfirmationMockCommand(
  sessionId: SessionId,
  confirmationId: ConfirmationId,
  request: CommandRequest<ResolveConfirmationPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return {
    requestId: `request-${request.commandId}`,
    ok: true,
    result: {
      commandId: request.commandId,
      status: "accepted",
      message: `Confirmation ${confirmationId} resolved.`,
      affectedTaskRefs: [
        {
          kind: "published",
          id: confirmationId.replace("confirmation-", "task-"),
        },
      ],
      objectRefs: [],
      affectedObjects: [],
      emittedMessageIds: [`message-${request.commandId}`],
      publishedTaskIds: [],
      debugRefs: {},
    },
    error: null,
    refresh: {
      waitForEvents: true,
      suggestedQueries: [
        `GET /api/v1/sessions/${sessionId}/messages`,
        `GET /api/v1/sessions/${sessionId}/task-tree`,
      ],
      affectedTaskRefs: [],
      affectedScopes: [],
    },
  };
}

export async function appendSessionInputMockCommand(
  request: CommandRequest<AppendSessionInputPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: "Session input accepted.",
    sessionId: request.sessionId,
  });
}

export async function answerAskMockCommand(
  sessionId: SessionId,
  _askId: AskId,
  request: CommandRequest<AnswerAskPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: "Answer received.",
    sessionId,
  });
}

export async function answerAuthoringAskBatchMockCommand(
  sessionId: SessionId,
  _rawTaskId: string,
  request: CommandRequest<AnswerAuthoringAskBatchPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: "Planning answers received.",
    sessionId,
  });
}

export async function repairAuthoringStateMockCommand(
  request: CommandRequest<RepairAuthoringStatePayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: "Authoring state repaired.",
    sessionId: request.sessionId,
  });
}

export async function deferAskMockCommand(
  sessionId: SessionId,
  _askId: AskId,
  request: CommandRequest<DeferAskPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: "Question deferred.",
    sessionId,
  });
}

export async function cancelAskMockCommand(
  sessionId: SessionId,
  _askId: AskId,
  request: CommandRequest<CancelAskPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: "Question canceled.",
    sessionId,
  });
}

export async function appendTaskInputMockCommand(
  sessionId: SessionId,
  taskNodeId: string,
  request: CommandRequest<AppendTaskInputPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: "Task input accepted.",
    sessionId,
    taskNodeId,
  });
}

export async function generateTaskTreeMockCommand(
  request: CommandRequest<GenerateTaskTreePayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: "Task plan generation accepted.",
    sessionId: request.sessionId,
  });
}

export async function updateTaskNodeMockCommand(
  sessionId: SessionId,
  taskNodeId: string,
  request: CommandRequest<UpdateTaskNodePayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: "Task update accepted.",
    sessionId,
    taskNodeId,
  });
}

export async function publishTaskTreeMockCommand(
  request: CommandRequest<PublishTaskTreePayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: "Task plan publish accepted.",
    sessionId: request.sessionId,
  });
}

export async function archivePlanMockCommand(
  sessionId: SessionId,
  planId: string,
  request: CommandRequest<ArchivePlanPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: "Plan archived.",
    sessionId,
    objectRefs: [{ kind: "plan", id: planId }],
  });
}

export async function retryTaskMockCommand(
  sessionId: SessionId,
  taskNodeId: string,
  request: CommandRequest<RetryTaskPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: "Task retry accepted.",
    sessionId,
    taskNodeId,
  });
}

export async function stopTaskMockCommand(
  sessionId: SessionId,
  taskNodeId: string,
  request: CommandRequest<StopTaskPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: "Task stop requested.",
    sessionId,
    taskNodeId,
  });
}

export const routeRuntimeInputMockCommand: RouteRuntimeInputCommand = async (
  request,
) => {
  await delay(30);

  const now = "2026-05-17T10:21:00+08:00";
  const answerBody = `This is a read-only answer for "${request.content}". No plan, task, or workspace state was changed.`;
  const result: RuntimeInputRouteResult = {
    sessionId: request.sessionId,
    decision: {
      id: `decision-${request.commandId}`,
      intent: "question",
      scope: {
        kind: request.selection.scopeKind,
        planId: request.selection.planId ?? null,
        taskNodeId: request.selection.taskNodeId ?? null,
      },
      confidence: "high",
      sideEffect: "no_effect",
      dispatchTarget: "read_only_inquiry",
      explanation: "Mock runtime input treated this input as a question.",
      relatedRefs: [],
    },
    outcome: {
      status: "answered",
      userMessage: answerBody,
      recoveryActions: [],
    },
    activity: {
      id: `activity-${request.commandId}`,
      sessionId: request.sessionId,
      kind: "answer",
      title: "Read-only answer",
      body: answerBody,
      occurredAt: now,
      scopeKind: request.selection.scopeKind,
      planId: request.selection.planId ?? null,
      taskNodeId: request.selection.taskNodeId ?? null,
      sideEffect: "no_effect",
      relatedRefs: [],
      sourceKind: "router",
      disclosureLevel: "public",
    },
    commandResponse: null,
    inquiryResult: {
      inquiryId: request.commandId,
      sessionId: request.sessionId,
      scope: {
        kind: request.selection.scopeKind,
        planId: request.selection.planId ?? null,
        taskNodeId: request.selection.taskNodeId ?? null,
      },
      status: "answered",
      answer: {
        title: "Read-only answer",
        body: answerBody,
        confidence: "high",
      },
      evidenceRefs: [
        {
          kind: "session_status",
          refId: `session:${request.sessionId}:status`,
          label: "Mock session status",
          disclosure: "public",
          truncated: false,
        },
      ],
      warnings: [],
      activity: null,
      generatedAt: now,
    },
    generatedAt: now,
  };

  return {
    requestId: `request-${request.commandId}`,
    ok: true,
    data: result,
    error: null,
    cursor: null,
    generatedAt: now,
  } satisfies QueryResponse<RuntimeInputRouteResult>;
};

export const subscribeSessionEventsMock: SubscribeSessionEvents = () => () => {
  // The default mock stream is intentionally quiet. Tests inject events.
};

export const mainPageMockAdapter: MainPageAdapter = {
  answerAsk: answerAskMockCommand,
  answerAuthoringAskBatch: answerAuthoringAskBatchMockCommand,
  appendSessionInput: appendSessionInputMockCommand,
  appendTaskInput: appendTaskInputMockCommand,
  archivePlan: archivePlanMockCommand,
  cancelAsk: cancelAskMockCommand,
  async createSession(payload) {
    await delay(20);
    return {
      sessionId: "mock-session-new",
      session: {
        id: "mock-session-new",
        name: payload.name ?? "New session",
      },
    };
  },
  async deleteSession() {
    await delay(20);
    return {
      deletedSessionId: "mock-session",
      nextSessionId: null,
    };
  },
  deferAsk: deferAskMockCommand,
  generateTaskTree: generateTaskTreeMockCommand,
  loadSnapshot: loadMainPageMockSnapshot,
  async loadTokenUsageSummary(request) {
    await delay(20);
    return mockTokenUsageSummary(request);
  },
  publishTaskTree: publishTaskTreeMockCommand,
  repairAuthoringState: repairAuthoringStateMockCommand,
  async renameSession(payload) {
    await delay(20);
    return {
      sessionId: payload.sessionId,
      session: {
        id: payload.sessionId,
        name: payload.name,
      },
    };
  },
  retryTask: retryTaskMockCommand,
  resolveConfirmation: resolveConfirmationMockCommand,
  routeRuntimeInput: routeRuntimeInputMockCommand,
  runtimeKind: "mock",
  sessionId: null,
  showStatePicker: true,
  stopTask: stopTaskMockCommand,
  subscribeSessionEvents: subscribeSessionEventsMock,
  updateTaskNode: updateTaskNodeMockCommand,
};

export function createMainPageMockAdapter(
  overrides: Partial<MainPageAdapter> = {},
): MainPageAdapter {
  return {
    ...mainPageMockAdapter,
    ...overrides,
  };
}

function acceptedCommandResponse({
  commandId,
  message,
  objectRefs = [],
  sessionId,
  taskNodeId,
}: {
  commandId: string;
  message: string;
  objectRefs?: NonNullable<CommandResponse["result"]>["objectRefs"];
  sessionId: string;
  taskNodeId?: string;
}): CommandResponse {
  return {
    requestId: `request-${commandId}`,
    ok: true,
    result: {
      commandId,
      status: "accepted",
      message,
      affectedTaskRefs: taskNodeId
        ? [
            {
              kind: "published",
              id: taskNodeId,
            },
          ]
        : [],
      objectRefs,
      affectedObjects: [],
      emittedMessageIds: [`message-${commandId}`],
      publishedTaskIds: [],
      debugRefs: {},
    },
    error: null,
    refresh: {
      waitForEvents: true,
      suggestedQueries: [`GET /api/v1/sessions/${sessionId}/messages`],
      affectedTaskRefs: taskNodeId
        ? [
            {
              kind: "published",
              id: taskNodeId,
            },
          ]
        : [],
      affectedScopes: [],
    },
  };
}

function mockTokenUsageSummary(
  request: TokenUsageSummaryRequest,
): TokenUsageSummaryResponse {
  const now = "2026-05-17T10:20:00+08:00";
  const id =
    request.taskNodeId ??
    request.planId ??
    request.sessionId ??
    "mock-workspace";

  return {
    dimension: request.dimension,
    totals: {
      dimension: request.dimension,
      id: "total",
      label: "Total",
      workspaceId: "mock-workspace",
      sessionId: request.sessionId ?? "mock-session",
      planId: request.planId ?? null,
      taskNodeId: request.taskNodeId ?? null,
      callCount: 3,
      unknownUsageCallCount: 0,
      inputTokens: 12400,
      outputTokens: 2100,
      totalTokens: 14500,
      reasoningTokens: 640,
      cachedTokens: 5200,
      cacheHitTokens: 5200,
      cacheMissTokens: 7200,
      cacheHitRatio: 0.4193548387,
      cacheRateSource: "hit_miss_tokens",
      firstOccurredAt: "2026-05-17T10:00:00+08:00",
      lastOccurredAt: now,
    },
    rows: [
      {
        dimension: request.dimension,
        id,
        label: `${request.dimension} ${id}`,
        workspaceId: "mock-workspace",
        sessionId: request.sessionId ?? "mock-session",
        planId: request.planId ?? null,
        taskNodeId: request.taskNodeId ?? null,
        callCount: 3,
        unknownUsageCallCount: 0,
        inputTokens: 12400,
        outputTokens: 2100,
        totalTokens: 14500,
        reasoningTokens: 640,
        cachedTokens: 5200,
        cacheHitTokens: 5200,
        cacheMissTokens: 7200,
        cacheHitRatio: 0.4193548387,
        cacheRateSource: "hit_miss_tokens",
        firstOccurredAt: "2026-05-17T10:00:00+08:00",
        lastOccurredAt: now,
      },
    ],
  };
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

function toSessionSummary(session: (typeof mainPageStates)[number]["session"]): SessionSummary {
  return {
    ...session,
    status: session.status as SessionStatus,
    createdAt: "2026-05-17T10:00:00+08:00",
    updatedAt: "2026-05-17T10:20:00+08:00",
    workspaceLabel: "Isolated session workspace",
  };
}

function sessionStatusForFixture(stateId: MainPageStateId): SessionStatus {
  switch (stateId) {
    case "s1-empty":
    case "s15-read-only-answer":
    case "s17-conversation-visual-samples":
      return "new";
    case "s2-understanding":
      return "understanding";
    case "s3-draft-ready":
    case "s4-task-selected":
    case "s5-task-editing":
    case "s10-permission-denied":
      return "draft_ready";
    case "s6-running":
    case "s11-stale-snapshot":
    case "s12-backend-busy":
    case "s16-direct-task":
      return "running";
    case "s7-confirmation":
    case "s14-execution-ask":
      return "waiting_user";
    case "s8-completed":
    case "s9-file-changes":
      return "completed";
    case "s13-command-failed":
      return "failed";
  }
}

function planningAsksForFixture(
  stateId: MainPageStateId,
): NonNullable<MainPageRuntimeSnapshot["snapshot"]["planning"]>["asks"] {
  if (stateId !== "s2-understanding") {
    return [];
  }

  return [
    {
      id: "authoring-ask-site-type",
      question: "What kind of website should Plato plan first?",
      reason:
        "The initial task plan depends on the site's primary purpose and audience.",
      required: true,
      options: [
        { label: "Portfolio", tone: "primary", value: "portfolio" },
        { label: "Blog", value: "blog" },
        { label: "Product site", value: "product_site" },
      ],
      status: "pending",
    },
    {
      id: "authoring-ask-style",
      question: "Which visual direction should guide the first draft?",
      reason:
        "A style direction keeps page structure, copy, and implementation tasks aligned.",
      required: true,
      options: [
        { label: "Quiet editorial", tone: "primary", value: "quiet_editorial" },
        { label: "Technical portfolio", value: "technical_portfolio" },
        { label: "Studio showcase", value: "studio_showcase" },
      ],
      status: "pending",
    },
  ];
}

function activeAskForFixture(
  stateId: MainPageStateId,
  sessionId: SessionId,
): MainPageRuntimeSnapshot["snapshot"]["activeAsk"] {
  if (stateId !== "s14-execution-ask") {
    return null;
  }

  return {
    id: "ask-deployment-target",
    sessionId,
    taskNodeId: "task-implementation",
    taskRef: {
      kind: "published",
      id: "task-implementation",
    },
    question: "Where should the first deployment target point?",
    reason:
      "The implementation task needs a target before it can configure deployment files.",
    suggestedOptions: [
      {
        id: "vercel",
        label: "Vercel",
        description: "Use Vercel for the first static deployment path.",
      },
      {
        id: "netlify",
        label: "Netlify",
        description: "Use Netlify for the first static deployment path.",
      },
    ],
    answerType: "single_choice",
    allowFreeText: true,
    allowNoOptionWithText: false,
    blocking: true,
    attachmentsSupported: false,
    status: "pending",
    answerId: null,
    resumeHint: "Resume implementation after persisting the answer.",
    createdAt: "2026-05-17T10:22:00+08:00",
    answeredAt: null,
    deferredAt: null,
    cancelledAt: null,
    expiredAt: null,
  };
}

function conversationAskMessagesForFixture(
  stateId: MainPageStateId,
  sessionId: SessionId,
  activeAsk: MainPageRuntimeSnapshot["snapshot"]["activeAsk"],
): SessionMessageView[] {
  if (stateId === "s2-understanding") {
    const questions = planningAsksForFixture(stateId);
    return [
      {
        id: "conversation-ask:authoring:raw-task-website-goal",
        sessionId,
        taskNodeId: null,
        kind: "actionable",
        title: "Plato question",
        body: "Clarify the website goal before Plato drafts the plan.",
        createdAt: "2026-05-17T10:10:00+08:00",
        conversationRender: {
          protocolVersion: "plato.conversation.render.v1",
          renderKind: "ask_card",
          askCard: {
            cardId: "conversation-ask:authoring:raw-task-website-goal",
            domain: "authoring",
            status: "pending",
            title: "Planning questions",
            body: "Clarify the website goal before Plato drafts the plan.",
            rawTaskId: "raw-task-website-goal",
            questions: questions.map((question) => ({
              id: question.id,
              prompt: question.question,
              reason: question.reason,
              required: question.required,
              answered: false,
              answerType:
                question.options.length > 0
                  ? ("single_choice" as const)
                  : ("free_text" as const),
              allowFreeText: question.options.length === 0,
              options: question.options.map((option) => ({
                id: option.value,
                value: option.value,
                label: option.label,
                selected: false,
              })),
              answerText: null,
            })),
            answerText: null,
            createdAt: "2026-05-17T10:10:00+08:00",
            resolvedAt: null,
            canAnswer: true,
            canDefer: false,
            canCancel: false,
            readonlyReason: null,
          },
        },
        conversationVisibility: "visible",
      },
    ];
  }

  if (stateId !== "s14-execution-ask" || activeAsk == null) {
    return [];
  }

  return [
    {
      id: `conversation-ask:execution:${activeAsk.id}`,
      sessionId,
      taskNodeId: activeAsk.taskNodeId ?? null,
      taskRef: activeAsk.taskRef,
      kind: "actionable",
      title: "Plato question",
      body: activeAsk.question,
      createdAt: activeAsk.createdAt,
      conversationRender: {
        protocolVersion: "plato.conversation.render.v1",
        renderKind: "ask_card",
        askCard: {
          cardId: `conversation-ask:execution:${activeAsk.id}`,
          domain: "execution",
          status: activeAsk.status,
          title: "Task needs input",
          body: activeAsk.reason,
          askId: activeAsk.id,
          taskNodeId: activeAsk.taskNodeId,
          questions: [
            {
              id: activeAsk.id,
              prompt: activeAsk.question,
              reason: activeAsk.reason,
              required: true,
              answered: false,
              answerType: activeAsk.answerType,
              allowFreeText:
                activeAsk.allowFreeText ||
                activeAsk.allowNoOptionWithText,
              options: activeAsk.suggestedOptions.map((option) => ({
                id: option.id,
                value: option.id,
                label: option.label,
                description: option.description,
                selected: false,
              })),
              answerText: null,
            },
          ],
          answerText: null,
          createdAt: activeAsk.createdAt,
          resolvedAt: null,
          canAnswer: true,
          canDefer: true,
          canCancel: true,
          readonlyReason: null,
        },
      },
      conversationVisibility: "visible",
    },
  ];
}

function permissionsForFixture(
  stateId: MainPageStateId,
): NonNullable<MainPageRuntimeSnapshot["snapshot"]["permissions"]> {
  const readonly = stateId === "s10-permission-denied";
  const stale = stateId === "s11-stale-snapshot";

  return {
    canAppendGuidance: !readonly && !stale,
    canCreateTaskTree:
      stateId === "s1-empty" || stateId === "s15-read-only-answer",
    canOpenAudit: true,
    canOpenSettings: true,
    canPublishTaskTree: stateId === "s3-draft-ready",
    readonlyReason: readonly
      ? "This task is read-only right now."
      : stale
        ? "Session view is stale; refresh before making changes."
        : null,
  };
}

function toTaskTreeView(
  taskTree: NonNullable<(typeof mainPageStates)[number]["taskTree"]>,
  sessionId: string,
  sessionStatus: string,
  stateId: MainPageStateId,
): TaskTreeView {
  const status = taskTreeStatusFor(sessionStatus);
  const nodes = taskTree.nodes.map((node, index): TaskNodeCardView => {
    const nodeStatus = node.status as TaskNodeCardView["status"];
    const isExecutionAskNode =
      stateId === "s14-execution-ask" && node.id === "task-implementation";
    const pendingConfirmationCount =
      !isExecutionAskNode && nodeStatus === "waiting_user" ? 1 : 0;
    const dimensions = deriveLegacyTaskNodeStatusDimensions({
      badges: {
        directFileChangeCount: node.id === "task-implementation" ? 3 : 0,
        pendingConfirmationCount,
        subtreeFileChangeCount: node.id === "task-implementation" ? 3 : 0,
        unreadMessageCount: 0,
      },
      status: nodeStatus,
    });

    return {
      id: node.id,
      taskRef: {
        kind: sessionStatus === "draft_ready" ? "draft" : "published",
        id: node.id,
      },
      parentId: node.parentId,
      title: node.title,
      summary: node.summary,
      status: nodeStatus,
      readiness: dimensions.readiness,
      execution: isExecutionAskNode ? "waiting_for_user" : dimensions.execution,
      confirmation: isExecutionAskNode ? null : dimensions.confirmation,
      auditVerdict: dimensions.auditVerdict,
      depth: 0,
      orderIndex: index,
      displayIndex: index + 1,
      badges: {
        pendingConfirmationCount,
        unreadMessageCount: 0,
        directFileChangeCount: node.id === "task-implementation" ? 3 : 0,
        subtreeFileChangeCount: node.id === "task-implementation" ? 3 : 0,
      },
      permissions: {
        canEdit: nodeStatus === "draft" || nodeStatus === "queued",
        canAppendGuidance: nodeStatus === "running" || nodeStatus === "waiting_user",
        canResolveConfirmation:
          !isExecutionAskNode && nodeStatus === "waiting_user",
        canPublish: sessionStatus === "draft_ready",
        canCancel:
          nodeStatus === "draft" || nodeStatus === "queued" || nodeStatus === "running",
        canRetry: nodeStatus === "failed",
      },
      readonlyReason: nodeStatus === "done" ? "Completed tasks are read-only." : null,
      version: 1,
    };
  });

  return {
    id: taskTree.id,
    sessionId,
    title: taskTree.title,
    status,
    readiness: mapLegacyTaskTreeStatusToReadiness(status),
    executionRollup: executionRollupForNodes(nodes),
    nodes,
    version: 1,
    generatedAt: "2026-05-17T10:20:00+08:00",
  };
}

function taskTreeStatusFor(sessionStatus: string): TaskTreeStatus {
  if (sessionStatus === "completed") {
    return "completed";
  }

  if (sessionStatus === "running" || sessionStatus === "waiting_user") {
    return "running";
  }

  if (sessionStatus === "failed") {
    return "failed";
  }

  return "draft";
}

function executionRollupForNodes(
  nodes: TaskNodeCardView[],
): NonNullable<TaskTreeView["executionRollup"]> {
  return nodes.reduce(
    (rollup, node) => {
      const execution = node.execution ?? "unknown";

      return {
        ...rollup,
        blockedByConfirmation:
          rollup.blockedByConfirmation + (node.confirmation === "pending" ? 1 : 0),
        cancelled: rollup.cancelled + (execution === "cancelled" ? 1 : 0),
        done: rollup.done + (execution === "done" ? 1 : 0),
        failed: rollup.failed + (execution === "failed" ? 1 : 0),
        notStarted: rollup.notStarted + (execution === "not_started" ? 1 : 0),
        pending: rollup.pending + (execution === "pending" ? 1 : 0),
        running: rollup.running + (execution === "running" ? 1 : 0),
        total: rollup.total + 1,
        unknown: rollup.unknown + (execution === "unknown" ? 1 : 0),
      };
    },
    {
      blockedByConfirmation: 0,
      cancelled: 0,
      done: 0,
      failed: 0,
      notStarted: 0,
      pending: 0,
      running: 0,
      total: 0,
      unknown: 0,
    },
  );
}

function toPendingConfirmations(
  fixture: ReturnType<typeof getMainPageState>,
): ConfirmationActionView[] {
  const taskNodeId = fixture.selectedTaskNodeId;

  if (fixture.detail.mode !== "confirmation" || taskNodeId === null) {
    return [];
  }

  return [
    {
      id: "confirmation-visual-baseline",
      sessionId: fixture.session.id,
      taskNodeId,
      taskRef: {
        kind: "published",
        id: taskNodeId,
      },
      title: fixture.detail.title,
      body: fixture.detail.body,
      options: [
        {
          value: "confirmed",
          label: fixture.detail.actionLabel ?? "Confirm",
          tone: "primary",
        },
        {
          value: "revise",
          label: "Revise task",
          tone: "secondary",
        },
        {
          value: "skipped",
          label: "Skip",
          tone: "danger",
        },
      ],
      defaultOptionValue: "confirmed",
      status: "pending",
      riskLabel: "Needs user confirmation",
      createdAt: "2026-05-17T10:03:00+08:00",
      resolvedAt: null,
    },
  ];
}

function toResultCardView(
  result: NonNullable<(typeof mainPageStates)[number]["result"]>,
  sessionId: string,
): ResultCardView {
  return {
    ...result,
    sessionId,
    taskNodeId: result.taskNodeId,
    sections: [
      {
        title: "Delivered structure",
        body: "Created the first runnable shell, connected the Main Page states, and prepared the review path for task planning.",
        kind: "list",
      },
      {
        title: "Next review focus",
        body: "Check whether the generated page structure, visual tone, and file changes match the intended product baseline before accepting the result.",
        kind: "text",
      },
    ],
    updatedAt: "2026-05-17T10:12:00+08:00",
  };
}

function toFileChangeSummaryView(
  summary: NonNullable<(typeof mainPageStates)[number]["fileChangeSummary"]>,
  sessionId: string,
): FileChangeSummaryView {
  return {
    sessionId,
    taskNodeId: summary.taskNodeId,
    recursive: true,
    changedFiles: summary.changedFiles.map((path) =>
      toFileChangeItem(path, summary.taskNodeId),
    ),
    summary: `Recursive summary: ${summary.changedFiles.length} files changed in the selected task and its children.`,
    updatedAt: "2026-05-17T10:15:00+08:00",
  };
}

function toFileChangeItem(
  path: string,
  ownerTaskNodeId: string | null,
): FileChangeSummaryView["changedFiles"][number] {
  if (path === "package.json") {
    return {
      path,
      changeType: "modified",
      summary: "Updated frontend dependencies and scripts.",
      ownerTaskNodeId,
    };
  }

  if (path === "src/App.tsx") {
    return {
      path,
      changeType: "created",
      summary: "Added Plato app shell and Main Page entry.",
      ownerTaskNodeId,
    };
  }

  if (path === "src/styles.css") {
    return {
      path,
      changeType: "created",
      summary: "Added baseline styling for the first prototype.",
      ownerTaskNodeId,
    };
  }

  return {
    path,
    changeType: "modified",
    summary: "Updated by the selected task.",
    ownerTaskNodeId,
  };
}
