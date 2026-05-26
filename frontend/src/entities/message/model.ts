import type { SessionId } from "../session/model";
import type { TaskNodeId } from "../task/model";

export type MessageId = string;

export type MessageKind = "informational" | "actionable" | "response" | "error";

export type SessionMessage = {
  id: MessageId;
  sessionId: SessionId;
  taskNodeId: TaskNodeId | null;
  kind: MessageKind;
  title: string;
  body: string;
  createdAt: string;
};
