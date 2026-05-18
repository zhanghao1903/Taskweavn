import type { TaskNodeId } from "../../shared/api/types";

export type DetailOverride = "auto" | "result" | "fileChanges";

export type ConfirmationDecision =
  | "confirmed"
  | "revise"
  | "skipped"
  | null;

export type EventConnectionStatus =
  | "connected"
  | "disconnected"
  | "resyncing";

export type InputTarget = "session" | "task";

export type LocalInputMessage = {
  content: string;
  createdAt: string;
  target: InputTarget;
  taskNodeId: TaskNodeId | null;
};

export type MainPageDetailHeader = {
  body: string;
  eyebrow: string;
  title: string;
};

export type MainPageInputScopeView = {
  label: string;
  placeholder: string;
};
