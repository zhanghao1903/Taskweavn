import type {
  AppendSessionInputPayload,
  AppendTaskInputPayload,
  GenerateTaskTreePayload,
  PublishTaskTreePayload,
  ResolveConfirmationPayload,
  UpdateTaskNodePayload,
} from "../../shared/api/platoApi";
import type {
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
  defaultMainPageStateId,
  getMainPageState,
  mainPageStates,
} from "./fixtures";
import { mainPageStateCatalog } from "./mainPageStateCatalog";
import type { MainPageStateId } from "./fixtures";
import type {
  AppendSessionInputCommand,
  AppendTaskInputCommand,
  GenerateTaskTreeCommand,
  LoadMainPageSnapshot,
  MainPageAdapter,
  MainPageRuntimeSnapshot,
  MainPageStateMetadata as RuntimeMainPageStateMetadata,
  PublishTaskTreeCommand,
  ResolveConfirmationCommand,
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
  GenerateTaskTreeCommand,
  LoadMainPageSnapshot,
  MainPageAdapter,
  MainPageRuntimeSnapshot as MainPageMockSnapshot,
  MainPageStateId,
  PublishTaskTreeCommand,
  ResolveConfirmationCommand,
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
      session: toSessionSummary(fixture.session),
      taskTree: fixture.taskTree
        ? toTaskTreeView(fixture.taskTree, fixture.session.id, fixture.session.status)
        : null,
      messages: fixture.messages,
      pendingConfirmations: toPendingConfirmations(fixture),
      result: fixture.result ? toResultCardView(fixture.result, fixture.session.id) : null,
      fileChangeSummary: fixture.fileChangeSummary
        ? toFileChangeSummaryView(fixture.fileChangeSummary, fixture.session.id)
        : null,
      auditLinks: [
        {
          label: "View audit",
          href: `/sessions/${fixture.session.id}/audit`,
          severity: "info",
        },
      ],
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

export async function appendTaskInputMockCommand(
  sessionId: SessionId,
  taskNodeId: string,
  request: CommandRequest<AppendTaskInputPayload>,
): Promise<CommandResponse> {
  await delay(60);

  return acceptedCommandResponse({
    commandId: request.commandId,
    message: `Task input accepted for ${taskNodeId}.`,
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
    message: "TaskTree generation accepted.",
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
    message: `TaskNode update accepted for ${taskNodeId}.`,
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
    message: "TaskTree publish accepted.",
    sessionId: request.sessionId,
  });
}

export const subscribeSessionEventsMock: SubscribeSessionEvents = () => () => {
  // The default mock stream is intentionally quiet. Tests inject events.
};

export const mainPageMockAdapter: MainPageAdapter = {
  appendSessionInput: appendSessionInputMockCommand,
  appendTaskInput: appendTaskInputMockCommand,
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
  resolveConfirmation: resolveConfirmationMockCommand,
  runtimeKind: "mock",
  sessionId: null,
  showStatePicker: true,
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

function toTaskTreeView(
  taskTree: NonNullable<(typeof mainPageStates)[number]["taskTree"]>,
  sessionId: string,
  sessionStatus: string,
): TaskTreeView {
  return {
    id: taskTree.id,
    sessionId,
    title: taskTree.title,
    status: taskTreeStatusFor(sessionStatus),
    nodes: taskTree.nodes.map((node, index): TaskNodeCardView => {
      const status = node.status as TaskNodeCardView["status"];

      return {
        id: node.id,
        taskRef: {
          kind: sessionStatus === "draft_ready" ? "draft" : "published",
          id: node.id,
        },
        parentId: node.parentId,
        title: node.title,
        summary: node.summary,
        status,
        depth: 0,
        orderIndex: index,
        badges: {
          pendingConfirmationCount: status === "waiting_user" ? 1 : 0,
          unreadMessageCount: 0,
          directFileChangeCount: node.id === "task-implementation" ? 3 : 0,
          subtreeFileChangeCount: node.id === "task-implementation" ? 3 : 0,
        },
        permissions: {
          canEdit: status === "draft" || status === "queued",
          canAppendGuidance: status === "running" || status === "waiting_user",
          canResolveConfirmation: status === "waiting_user",
          canPublish: sessionStatus === "draft_ready",
          canCancel: status === "draft" || status === "queued",
          canRetry: status === "failed",
        },
        version: 1,
      };
    }),
    version: 1,
  };
}

function taskTreeStatusFor(sessionStatus: string): TaskTreeStatus {
  if (sessionStatus === "completed") {
    return "completed";
  }

  if (sessionStatus === "running" || sessionStatus === "waiting_user") {
    return "running";
  }

  return "draft";
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
    summary: `Recursive summary: ${summary.changedFiles.length} files changed in this TaskNode subtree.`,
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
    summary: "Updated by the selected TaskNode.",
    ownerTaskNodeId,
  };
}
