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

export type InputTarget = "session" | "plan" | "task";

export type MainPageSelectionTarget = "auto" | "plan" | "task";

export type MainPageDetailHeader = {
  body: string;
  eyebrow: string;
  title: string;
};

export type MainPageInputScopeView = {
  description?: string | null;
  label: string;
  placeholder: string;
};
