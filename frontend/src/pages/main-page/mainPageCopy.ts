import type { ConfirmationDecision } from "./mainPageUiTypes";

export const confirmationResolutionText: Record<
  Exclude<ConfirmationDecision, null>,
  string
> = {
  confirmed:
    "The confirmation was accepted. Plato can continue from this task.",
  revise:
    "A revision request was captured. Task-scoped input now refines this task.",
  skipped: "The confirmation was skipped. Plato will not perform this action.",
};
