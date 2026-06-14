import type {
  SessionActivityItemKind,
  SessionActivityItemView,
  SessionMessageView,
} from "../../shared/api/types";

export function activityItemsFromMessages(
  messages: readonly SessionMessageView[],
): SessionActivityItemView[] {
  return messages.map((message) => {
    const kind = activityKindFromMessage(message);
    return {
      body: message.body,
      disclosureLevel: "public",
      id: `activity:message:${message.id}`,
      kind,
      occurredAt: message.createdAt,
      planId: null,
      relatedRefs: [
        {
          id: message.id,
          kind: "message",
          label: message.title,
          objectRef: {
            id: message.id,
            kind: "message",
          },
        },
      ],
      scopeKind: message.taskNodeId === null ? "session" : "task",
      sessionId: message.sessionId,
      sideEffect:
        kind === "user_input"
          ? "context_effect"
          : kind === "confirmation_requested"
            ? "authorization_effect"
            : kind === "recovery_note"
              ? "state_effect"
              : "no_effect",
      sourceId: message.id,
      sourceKind: "message_stream",
      taskNodeId: message.taskNodeId,
      title: message.title,
    };
  });
}

function activityKindFromMessage(
  message: SessionMessageView,
): SessionActivityItemKind {
  if (message.kind === "response") {
    return "answer";
  }
  if (message.kind === "actionable") {
    return "confirmation_requested";
  }
  if (message.kind === "error") {
    return "recovery_note";
  }
  if (message.title.toLowerCase().startsWith("user")) {
    return "user_input";
  }
  return "execution_update";
}
