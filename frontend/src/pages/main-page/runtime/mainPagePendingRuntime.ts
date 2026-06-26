import type { ProductRecoveryAction } from "../../../shared/api/platoApi";
import type {
  SessionActivityItemView,
  SessionMessageView,
  TaskNodeId,
  WorkspaceId,
} from "../../../shared/api/types";

export type PendingRuntimeScopeKind = "session" | "plan" | "task";

export type PendingRuntimeItemStatus =
  | "pending"
  | "accepted"
  | "failed"
  | "rejected";

type PendingRuntimeCommandStatus =
  | "local_pending"
  | "accepted"
  | "failed"
  | "rejected";

type PendingRuntimeItemKind = "local_user_input" | "local_understanding";

export type PendingRuntimeCommandScope = {
  scopeKind: PendingRuntimeScopeKind;
  planId: string | null;
  taskNodeId: TaskNodeId | null;
};

type PendingRuntimeCommand = {
  commandId: string;
  failureMessage: string | null;
  recoveryActions: ProductRecoveryAction[];
  scope: PendingRuntimeCommandScope;
  sessionId: string;
  status: PendingRuntimeCommandStatus;
  submittedAt: string;
  submittedBody: string;
  workspaceId: WorkspaceId | null;
};

type LocalPendingRuntimeItem = {
  body: string;
  commandId: string;
  createdAt: string;
  failureMessage: string | null;
  id: string;
  kind: PendingRuntimeItemKind;
  recoveryActions: ProductRecoveryAction[];
  scope: PendingRuntimeCommandScope;
  sessionId: string;
  status: PendingRuntimeItemStatus;
  workspaceId: WorkspaceId | null;
};

export type MainPagePendingRuntimeState = {
  items: LocalPendingRuntimeItem[];
  pendingCommands: Record<string, PendingRuntimeCommand>;
  sessionId: string | null;
  workspaceId: WorkspaceId | null;
};

export type MainPagePendingRuntimeAction =
  | {
      body: string;
      commandId: string;
      createdAt: string;
      scope: PendingRuntimeCommandScope;
      sessionId: string;
      type: "runtime_input.submit_started";
      workspaceId: WorkspaceId | null;
    }
  | {
      commandId: string;
      type: "runtime_input.command_accepted";
    }
  | {
      commandId: string;
      message: string;
      recoveryActions: ProductRecoveryAction[];
      type: "runtime_input.command_rejected";
    }
  | {
      commandId: string;
      message: string;
      recoveryActions: ProductRecoveryAction[];
      type: "runtime_input.command_failed";
    }
  | {
      commandId: string;
      type: "runtime_input.command_reconciled";
    }
  | {
      activities: SessionActivityItemView[];
      messages: SessionMessageView[];
      sessionId: string;
      type: "snapshot.hydrated";
      workspaceId: WorkspaceId | null;
    }
  | {
      sessionId: string | null;
      type: "runtime.reset_scope";
      workspaceId: WorkspaceId | null;
    };

export function createInitialPendingRuntimeState({
  sessionId,
  workspaceId,
}: {
  sessionId: string | null;
  workspaceId: WorkspaceId | null;
}): MainPagePendingRuntimeState {
  return {
    items: [],
    pendingCommands: {},
    sessionId,
    workspaceId,
  };
}

export function mainPagePendingRuntimeReducer(
  state: MainPagePendingRuntimeState,
  action: MainPagePendingRuntimeAction,
): MainPagePendingRuntimeState {
  switch (action.type) {
    case "runtime.reset_scope":
      return createInitialPendingRuntimeState({
        sessionId: action.sessionId,
        workspaceId: action.workspaceId,
      });

    case "runtime_input.submit_started":
      return startRuntimeInputSubmit(state, action);

    case "runtime_input.command_accepted":
      return updateCommandStatus(state, action.commandId, {
        failureMessage: null,
        recoveryActions: [],
        status: "accepted",
      });

    case "runtime_input.command_rejected":
      return updateCommandStatus(state, action.commandId, {
        failureMessage: action.message,
        recoveryActions: action.recoveryActions,
        status: "rejected",
      });

    case "runtime_input.command_failed":
      return updateCommandStatus(state, action.commandId, {
        failureMessage: action.message,
        recoveryActions: action.recoveryActions,
        status: "failed",
      });

    case "runtime_input.command_reconciled":
      return removeCommandItems(state, action.commandId);

    case "snapshot.hydrated":
      if (
        state.sessionId !== action.sessionId ||
        state.workspaceId !== action.workspaceId
      ) {
        return createInitialPendingRuntimeState({
          sessionId: action.sessionId,
          workspaceId: action.workspaceId,
        });
      }

      return reconcileHydratedSnapshot(state, action.messages, action.activities);
  }
}

export function projectPendingRuntimeActivityItems(
  state: MainPagePendingRuntimeState,
): SessionActivityItemView[] {
  return state.items.map((item) => {
    if (item.kind === "local_user_input") {
      return {
        id: item.id,
        body: item.body,
        disclosureLevel: "public",
        kind: "user_input",
        occurredAt: item.createdAt,
        planId: item.scope.planId,
        relatedRefs: [],
        scopeKind: item.scope.scopeKind,
        sessionId: item.sessionId,
        sideEffect: "context_effect",
        sourceId: item.commandId,
        sourceKind: "router",
        taskNodeId: item.scope.taskNodeId,
        title: "User input",
      };
    }

    return {
      id: item.id,
      body: pendingUnderstandingBody(item),
      disclosureLevel: "public",
      kind:
        item.status === "failed" || item.status === "rejected"
          ? "recovery_note"
          : "router_interpretation",
      occurredAt: item.createdAt,
      planId: item.scope.planId,
      relatedRefs: [],
      scopeKind: item.scope.scopeKind,
      sessionId: item.sessionId,
      sideEffect: "no_effect",
      sourceId: item.commandId,
      sourceKind: "router",
      taskNodeId: item.scope.taskNodeId,
      title:
        item.status === "failed"
          ? "Runtime input failed"
          : item.status === "rejected"
            ? "Runtime input rejected"
            : "Plato is understanding",
    };
  });
}

function startRuntimeInputSubmit(
  state: MainPagePendingRuntimeState,
  action: Extract<
    MainPagePendingRuntimeAction,
    { type: "runtime_input.submit_started" }
  >,
): MainPagePendingRuntimeState {
  const command: PendingRuntimeCommand = {
    commandId: action.commandId,
    failureMessage: null,
    recoveryActions: [],
    scope: action.scope,
    sessionId: action.sessionId,
    status: "local_pending",
    submittedAt: action.createdAt,
    submittedBody: action.body,
    workspaceId: action.workspaceId,
  };
  const nextItems: LocalPendingRuntimeItem[] = [
    {
      body: action.body,
      commandId: action.commandId,
      createdAt: action.createdAt,
      failureMessage: null,
      id: pendingItemId(action.commandId, "local_user_input"),
      kind: "local_user_input",
      recoveryActions: [],
      scope: action.scope,
      sessionId: action.sessionId,
      status: "pending",
      workspaceId: action.workspaceId,
    },
    {
      body: "Understanding your request...",
      commandId: action.commandId,
      createdAt: action.createdAt,
      failureMessage: null,
      id: pendingItemId(action.commandId, "local_understanding"),
      kind: "local_understanding",
      recoveryActions: [],
      scope: action.scope,
      sessionId: action.sessionId,
      status: "pending",
      workspaceId: action.workspaceId,
    },
  ];

  return {
    ...state,
    items: [
      ...nextItems,
      ...state.items.filter((item) => item.commandId !== action.commandId),
    ],
    pendingCommands: {
      ...state.pendingCommands,
      [action.commandId]: command,
    },
    sessionId: action.sessionId,
    workspaceId: action.workspaceId,
  };
}

function updateCommandStatus(
  state: MainPagePendingRuntimeState,
  commandId: string,
  nextStatus: {
    failureMessage: string | null;
    recoveryActions: ProductRecoveryAction[];
    status: Exclude<PendingRuntimeCommandStatus, "local_pending">;
  },
): MainPagePendingRuntimeState {
  const command = state.pendingCommands[commandId];
  if (command === undefined) {
    return state;
  }

  return {
    ...state,
    items: state.items.map((item) =>
      item.commandId === commandId
        ? {
            ...item,
            failureMessage: nextStatus.failureMessage,
            recoveryActions: nextStatus.recoveryActions,
            status: nextStatus.status,
          }
        : item,
    ),
    pendingCommands: {
      ...state.pendingCommands,
      [commandId]: {
        ...command,
        failureMessage: nextStatus.failureMessage,
        recoveryActions: nextStatus.recoveryActions,
        status: nextStatus.status,
      },
    },
  };
}

function removeCommandItems(
  state: MainPagePendingRuntimeState,
  commandId: string,
): MainPagePendingRuntimeState {
  const pendingCommands = { ...state.pendingCommands };
  delete pendingCommands[commandId];
  return {
    ...state,
    items: state.items.filter((item) => item.commandId !== commandId),
    pendingCommands,
  };
}

function reconcileHydratedSnapshot(
  state: MainPagePendingRuntimeState,
  messages: SessionMessageView[],
  activities: SessionActivityItemView[],
): MainPagePendingRuntimeState {
  const items = state.items.filter((item) => {
    const command = state.pendingCommands[item.commandId];
    if (command === undefined) {
      return false;
    }

    if (command.status === "failed" || command.status === "rejected") {
      return true;
    }

    if (
      item.kind === "local_user_input" &&
      hasDurableUserInput(command, messages, activities)
    ) {
      return false;
    }

    if (
      item.kind === "local_understanding" &&
      hasDurableRuntimeResult(command, messages, activities)
    ) {
      return false;
    }

    return true;
  });
  const liveCommandIds = new Set(items.map((item) => item.commandId));
  const pendingCommands = Object.fromEntries(
    Object.entries(state.pendingCommands).filter(([commandId]) =>
      liveCommandIds.has(commandId),
    ),
  );

  return {
    ...state,
    items,
    pendingCommands,
  };
}

function hasDurableUserInput(
  command: PendingRuntimeCommand,
  messages: SessionMessageView[],
  activities: SessionActivityItemView[],
): boolean {
  return (
    messages.some((message) => isDurableUserMessage(command, message)) ||
    activities.some(
      (activity) =>
        activity.sourceKind === "router" &&
        activity.sourceId === command.commandId &&
        activity.kind === "user_input",
    )
  );
}

function hasDurableRuntimeResult(
  command: PendingRuntimeCommand,
  messages: SessionMessageView[],
  activities: SessionActivityItemView[],
): boolean {
  return (
    messages.some(
      (message) =>
        message.relatedCommandId === command.commandId &&
        !isDurableUserMessage(command, message),
    ) ||
    activities.some(
      (activity) =>
        activity.sourceKind === "router" &&
        activity.sourceId === command.commandId &&
        activity.kind !== "user_input",
    )
  );
}

function isDurableUserMessage(
  command: PendingRuntimeCommand,
  message: SessionMessageView,
): boolean {
  if (message.sessionId !== command.sessionId) {
    return false;
  }

  if (
    message.relatedCommandId === command.commandId &&
    (isSameBody(message.body, command.submittedBody) ||
      message.title.toLowerCase().includes("input"))
  ) {
    return true;
  }

  return isWeakBodyMatch({
    candidateBody: message.body,
    candidateTimestamp: message.createdAt,
    submittedAt: command.submittedAt,
    submittedBody: command.submittedBody,
  });
}

function pendingItemId(
  commandId: string,
  kind: PendingRuntimeItemKind,
): string {
  return `activity:runtime-input:${commandId}:${kind}`;
}

function pendingUnderstandingBody(item: LocalPendingRuntimeItem): string {
  if (item.status === "failed" || item.status === "rejected") {
    return item.failureMessage ?? "Question routing failed. Please retry.";
  }

  return item.body;
}

function isWeakBodyMatch({
  candidateBody,
  candidateTimestamp,
  submittedAt,
  submittedBody,
}: {
  candidateBody: string;
  candidateTimestamp: string;
  submittedAt: string;
  submittedBody: string;
}): boolean {
  return (
    isSameBody(candidateBody, submittedBody) &&
    isWithinWeakMatchWindow(candidateTimestamp, submittedAt)
  );
}

function isSameBody(left: string, right: string): boolean {
  return normalizeBody(left) === normalizeBody(right);
}

function isWithinWeakMatchWindow(left: string, right: string): boolean {
  const leftTime = Date.parse(left);
  const rightTime = Date.parse(right);

  if (!Number.isFinite(leftTime) || !Number.isFinite(rightTime)) {
    return false;
  }

  return Math.abs(leftTime - rightTime) <= 5 * 60 * 1000;
}

function normalizeBody(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}
