import type {
  AppendSessionInputPayload,
  AppendTaskInputPayload,
  AnswerAskPayload,
  AnswerAuthoringAskBatchPayload,
  CancelAskPayload,
  DeferAskPayload,
  GenerateTaskTreePayload,
  PublishTaskTreePayload,
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
  ResultCardView,
  SessionId,
  SessionStatus,
  SessionSummary,
  TaskNodeCardView,
  TaskTreeStatus,
  TaskTreeView,
} from "../../shared/api/types";
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
  CancelAskCommand,
  DeferAskCommand,
  GenerateTaskTreeCommand,
  LoadMainPageSnapshot,
  MainPageAdapter,
  MainPageRuntimeSnapshot,
  MainPageStateMetadata as RuntimeMainPageStateMetadata,
  PublishTaskTreeCommand,
  ResolveConfirmationCommand,
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
  CancelAskCommand,
  DeferAskCommand,
  GenerateTaskTreeCommand,
  LoadMainPageSnapshot,
  MainPageAdapter,
  MainPageRuntimeSnapshot as MainPageMockSnapshot,
  MainPageStateId,
  PublishTaskTreeCommand,
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
      messages: fixture.messages,
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
  askId: AskId,
  request: CommandRequest<AnswerAskPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: `ASK answer accepted for ${askId}.`,
    sessionId,
  });
}

export async function answerAuthoringAskBatchMockCommand(
  sessionId: SessionId,
  rawTaskId: string,
  request: CommandRequest<AnswerAuthoringAskBatchPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: `Authoring ASK answers accepted for ${rawTaskId}.`,
    sessionId,
  });
}

export async function deferAskMockCommand(
  sessionId: SessionId,
  askId: AskId,
  request: CommandRequest<DeferAskPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: `ASK defer accepted for ${askId}.`,
    sessionId,
  });
}

export async function cancelAskMockCommand(
  sessionId: SessionId,
  askId: AskId,
  request: CommandRequest<CancelAskPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: `ASK cancel accepted for ${askId}.`,
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

export async function retryTaskMockCommand(
  sessionId: SessionId,
  taskNodeId: string,
  request: CommandRequest<RetryTaskPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: `Task retry accepted for ${taskNodeId}.`,
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
    message: `Task stop requested for ${taskNodeId}.`,
    sessionId,
    taskNodeId,
  });
}

export const subscribeSessionEventsMock: SubscribeSessionEvents = () => () => {
  // The default mock stream is intentionally quiet. Tests inject events.
};

export const mainPageMockAdapter: MainPageAdapter = {
  answerAsk: answerAskMockCommand,
  answerAuthoringAskBatch: answerAuthoringAskBatchMockCommand,
  appendSessionInput: appendSessionInputMockCommand,
  appendTaskInput: appendTaskInputMockCommand,
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
  publishTaskTree: publishTaskTreeMockCommand,
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
  sessionId,
  taskNodeId,
}: {
  commandId: string;
  message: string;
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
      objectRefs: [],
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
        "The initial TaskTree depends on the site's primary purpose and audience.",
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

function permissionsForFixture(
  stateId: MainPageStateId,
): NonNullable<MainPageRuntimeSnapshot["snapshot"]["permissions"]> {
  const readonly = stateId === "s10-permission-denied";
  const stale = stateId === "s11-stale-snapshot";

  return {
    canAppendGuidance: !readonly && !stale,
    canCreateTaskTree: stateId === "s1-empty",
    canOpenAudit: true,
    canOpenSettings: true,
    canPublishTaskTree: stateId === "s3-draft-ready",
    readonlyReason: readonly
      ? "Current permission context is read-only."
      : stale
        ? "Snapshot is stale; resync before mutating."
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
        body: "Created the first runnable shell, connected the Main Page states, and prepared the review path for the TaskTree workflow.",
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
