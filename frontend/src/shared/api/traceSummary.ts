import type {
  CommandResponse,
  MainPageSnapshot,
  TaskNodeCardView,
  UiEvent,
} from "./types";

export function summarizeMainPageSnapshot(snapshot: MainPageSnapshot) {
  const nodes = snapshot.taskTree?.nodes ?? [];

  return {
    messageCount: snapshot.messages.length,
    pendingConfirmationCount: snapshot.pendingConfirmations.length,
    sessionId: snapshot.session.id,
    sessionStatus: snapshot.session.status,
    taskNodeCount: nodes.length,
    taskNodes: nodes.map(summarizeTaskNode),
    taskTreeStatus: snapshot.taskTree?.status ?? null,
  };
}

export function summarizeCommandResponse(response: CommandResponse) {
  return {
    affectedScopes: response.refresh.affectedScopes.map((scope) => ({
      kind: scope.kind,
      taskRef: scope.taskRef ?? null,
    })),
    affectedTaskRefs: response.refresh.affectedTaskRefs,
    debugRefs: response.result?.debugRefs ?? {},
    error: response.error
      ? {
          code: response.error.code,
          message: response.error.message,
          retryable: response.error.retryable,
        }
      : null,
    ok: response.ok,
    requestId: response.requestId,
    resultMessage: response.result?.message ?? null,
    resultStatus: response.result?.status ?? null,
    suggestedQueries: response.refresh.suggestedQueries,
    waitForEvents: response.refresh.waitForEvents,
  };
}

export function summarizeUiEvent(event: UiEvent) {
  return {
    eventId: event.eventId,
    eventType: event.eventType,
    payload: summarizeEventPayload(event.payload),
    sessionId: event.sessionId,
  };
}

function summarizeTaskNode(node: TaskNodeCardView) {
  return {
    errorRef: node.errorRef ?? null,
    execution: node.execution ?? null,
    id: node.id,
    interruptionRequested: node.interruptionRequested ?? false,
    status: node.status,
    title: shortText(node.title),
  };
}

function summarizeEventPayload(payload: Record<string, unknown>) {
  const keys = [
    "reason",
    "taskNodeId",
    "taskNodeIds",
    "taskRef",
    "taskRefs",
    "message",
  ];
  const summary: Record<string, unknown> = {};
  for (const key of keys) {
    if (key in payload) {
      summary[key] = payload[key];
    }
  }
  return summary;
}

function shortText(value: string, limit = 80): string {
  return value.length <= limit ? value : `${value.slice(0, limit)}...`;
}
