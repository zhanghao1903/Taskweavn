import type {
  SessionActivityItemKind,
  SessionActivityItemView,
  SessionActivitySourceKind,
  SessionMessageView,
} from "../../shared/api/types";

const readOnlyInquiryActivityTitle = "Read-only question answered";

export function activityItemsFromMessages(
  messages: readonly SessionMessageView[],
): SessionActivityItemView[] {
  return messages.map((message) => {
    const kind = activityKindFromMessage(message);
    const isReadOnlyInquiry = message.title === readOnlyInquiryActivityTitle;
    const sourceId =
      isReadOnlyInquiry && message.relatedCommandId
        ? message.relatedCommandId
        : message.id;
    const sourceKind: SessionActivitySourceKind = isReadOnlyInquiry
      ? "router"
      : "message_stream";

    return {
      body: message.body,
      disclosureLevel: "public",
      id: isReadOnlyInquiry
        ? `activity:inquiry:${sourceId}`
        : `activity:message:${message.id}`,
      kind,
      occurredAt: message.createdAt,
      planId: null,
      relatedRefs:
        message.activityRelatedRefs && message.activityRelatedRefs.length > 0
          ? message.activityRelatedRefs
          : [
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
      sourceId,
      sourceKind,
      taskNodeId: message.taskNodeId,
      title: message.title,
    };
  });
}

function activityKindFromMessage(
  message: SessionMessageView,
): SessionActivityItemKind {
  if (message.title === "Plan archived") {
    return "plan_updated";
  }
  if (message.title === readOnlyInquiryActivityTitle) {
    return "answer";
  }
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
