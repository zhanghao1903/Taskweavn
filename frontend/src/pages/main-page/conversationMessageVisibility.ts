import type { SessionMessageView } from "../../shared/api/types";

export function isConversationVisible(message: SessionMessageView): boolean {
  return (message.conversationVisibility ?? "visible") === "visible";
}

export function isActivitySourceMessage(message: SessionMessageView): boolean {
  return message.conversationRender?.renderKind !== "ask_card";
}
