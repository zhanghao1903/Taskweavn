import type { MainPageStateId } from "./fixtures";

export type MainPageStateLifecycle =
  | "empty"
  | "understanding"
  | "planning"
  | "task_focus"
  | "execution"
  | "review"
  | "recovery";

export type MainPageStateCatalogEntry = {
  id: MainPageStateId;
  label: string;
  lifecycle: MainPageStateLifecycle;
  userSituation: string;
  pageFocus: string;
  primarySurfaces: readonly string[];
  expectedUserAction: string;
};

export const mainPageStateCatalog = [
  {
    id: "s1-empty",
    label: "S1 Empty",
    lifecycle: "empty",
    userSituation: "The user has opened a Workflow but has not entered a goal.",
    pageFocus: "Show the Workflow entry point and make natural-language input obvious.",
    primarySurfaces: ["Context input", "Workflow sidebar", "Empty task plan"],
    expectedUserAction: "Describe the goal they want Plato to plan.",
  },
  {
    id: "s2-understanding",
    label: "S2 Understanding",
    lifecycle: "understanding",
    userSituation:
      "Plato needs planning clarification before a task plan can be produced.",
    pageFocus:
      "Collect required authoring answers in the Main Work Area before continuing planning.",
    primarySurfaces: ["Planning questions", "Session context", "Context input disabled"],
    expectedUserAction: "Answer all required planning questions in one batch.",
  },
  {
    id: "s3-draft-ready",
    label: "S3 Draft Ready",
    lifecycle: "planning",
    userSituation: "A draft task plan exists and needs review before publication.",
    pageFocus: "Present the generated task plan as the main object of interaction.",
    primarySurfaces: ["Task plan", "Latest activity", "Context input"],
    expectedUserAction: "Review the draft, select a task, or refine the plan.",
  },
  {
    id: "s4-task-selected",
    label: "S4 Task Selected",
    lifecycle: "task_focus",
    userSituation: "The user selected a task while reviewing the task plan.",
    pageFocus: "Narrow the interaction scope from the session to a single task.",
    primarySurfaces: ["Task plan", "Latest activity", "Details"],
    expectedUserAction: "Inspect the task or add guidance that only applies to it.",
  },
  {
    id: "s5-task-editing",
    label: "S5 Editing",
    lifecycle: "task_focus",
    userSituation: "The user is actively refining a selected task.",
    pageFocus: "Show that task-scoped input changes the selected task, not the whole plan.",
    primarySurfaces: ["Task plan", "Latest activity", "Context input"],
    expectedUserAction: "Provide task-specific instructions or corrections.",
  },
  {
    id: "s6-running",
    label: "S6 Running",
    lifecycle: "execution",
    userSituation: "A published task is executing.",
    pageFocus: "Keep the running task visible while still allowing guidance.",
    primarySurfaces: ["Task plan", "Task updates", "Context input"],
    expectedUserAction: "Monitor progress or append guidance to the running task.",
  },
  {
    id: "s7-confirmation",
    label: "S7 Confirmation",
    lifecycle: "execution",
    userSituation: "Execution is waiting for a user decision attached to a task.",
    pageFocus: "Put the confirmation action in the detail panel without hiding context.",
    primarySurfaces: ["Details", "Confirmation options", "Latest activity"],
    expectedUserAction: "Confirm, revise, or skip the pending action.",
  },
  {
    id: "s8-completed",
    label: "S8 Completed",
    lifecycle: "review",
    userSituation: "The session has produced a result summary.",
    pageFocus: "Shift from execution progress to result review.",
    primarySurfaces: ["Result summary", "Task plan", "Context input"],
    expectedUserAction: "Review the result or request follow-up packaging.",
  },
  {
    id: "s9-file-changes",
    label: "S9 File Changes",
    lifecycle: "review",
    userSituation: "The user is reviewing file changes created by a task branch.",
    pageFocus: "Explain concrete workspace changes before acceptance or audit.",
    primarySurfaces: ["File changes", "Task plan", "Audit link"],
    expectedUserAction: "Inspect changed files or ask Plato to explain a change.",
  },
  {
    id: "s10-permission-denied",
    label: "S10 Permission Denied",
    lifecycle: "recovery",
    userSituation: "The user can inspect the selected task but cannot change it.",
    pageFocus: "Keep the permission boundary explicit while preserving context.",
    primarySurfaces: ["Task plan", "Permission detail", "Disabled input"],
    expectedUserAction: "Return, inspect, or wait for permissions to change.",
  },
  {
    id: "s11-stale-snapshot",
    label: "S11 Sync Required",
    lifecycle: "recovery",
    userSituation: "The visible session state changed and needs refresh.",
    pageFocus: "Disable high-risk actions and make resync the next safe action.",
    primarySurfaces: ["Task plan", "Resync detail", "Stale warning"],
    expectedUserAction: "Refresh the session before continuing.",
  },
  {
    id: "s12-backend-busy",
    label: "S12 Update Pending",
    lifecycle: "recovery",
    userSituation: "An update was accepted and Plato is still applying it.",
    pageFocus: "Keep the current state readable while preventing repeated updates.",
    primarySurfaces: ["Task plan", "Pending update detail", "Latest activity"],
    expectedUserAction: "Wait for the next event or retry only after timeout.",
  },
  {
    id: "s13-command-failed",
    label: "S13 Action Needs Retry",
    lifecycle: "recovery",
    userSituation: "A recoverable action error occurred without losing context.",
    pageFocus: "Show the error and keep retry/revise paths available.",
    primarySurfaces: ["Task plan", "Recoverable error detail", "Context input"],
    expectedUserAction: "Retry the last action or revise the task instruction.",
  },
  {
    id: "s14-execution-ask",
    label: "S14 Task Question",
    lifecycle: "execution",
    userSituation: "A published task is waiting for user input.",
    pageFocus:
      "Keep the task plan visible and answer the blocking question in the Details panel.",
    primarySurfaces: ["Task plan", "Task question", "Latest activity"],
    expectedUserAction: "Answer, defer, or cancel the active question.",
  },
] as const satisfies readonly MainPageStateCatalogEntry[];

export function getMainPageStateCatalogEntry(
  stateId: MainPageStateId,
): MainPageStateCatalogEntry {
  return mainPageStateCatalog.find((entry) => entry.id === stateId) ??
    mainPageStateCatalog[0];
}
