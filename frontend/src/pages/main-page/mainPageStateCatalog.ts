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
    primarySurfaces: ["Context input", "Workflow sidebar", "Empty TaskTree"],
    expectedUserAction: "Describe the goal they want Plato to plan.",
  },
  {
    id: "s2-understanding",
    label: "S2 Understanding",
    lifecycle: "understanding",
    userSituation:
      "Plato needs planning clarification before a TaskTree can be produced.",
    pageFocus:
      "Collect required authoring answers in the Main Work Area before continuing planning.",
    primarySurfaces: ["Authoring ASK", "Session context", "Context input disabled"],
    expectedUserAction: "Answer all required planning questions in one batch.",
  },
  {
    id: "s3-draft-ready",
    label: "S3 Draft Ready",
    lifecycle: "planning",
    userSituation: "A draft TaskTree exists and needs review before publication.",
    pageFocus: "Present the generated TaskTree as the main object of interaction.",
    primarySurfaces: ["TaskTree", "Session messages", "Context input"],
    expectedUserAction: "Review the draft, select a TaskNode, or refine the plan.",
  },
  {
    id: "s4-task-selected",
    label: "S4 Task Selected",
    lifecycle: "task_focus",
    userSituation: "The user selected a TaskNode while reviewing the TaskTree.",
    pageFocus: "Narrow the interaction scope from the session to a single TaskNode.",
    primarySurfaces: ["TaskTree", "Task-scoped projection", "Context inspector"],
    expectedUserAction: "Inspect the TaskNode or add guidance that only applies to it.",
  },
  {
    id: "s5-task-editing",
    label: "S5 Editing",
    lifecycle: "task_focus",
    userSituation: "The user is actively refining a selected TaskNode.",
    pageFocus: "Show that task-scoped input changes the TaskNode, not the whole plan.",
    primarySurfaces: ["TaskTree", "Session messages", "Context input"],
    expectedUserAction: "Provide task-specific instructions or corrections.",
  },
  {
    id: "s6-running",
    label: "S6 Running",
    lifecycle: "execution",
    userSituation: "A published TaskNode is executing.",
    pageFocus: "Keep the running Task visible while still allowing guidance.",
    primarySurfaces: ["TaskTree", "Task-scoped messages", "Context input"],
    expectedUserAction: "Monitor progress or append guidance to the running TaskNode.",
  },
  {
    id: "s7-confirmation",
    label: "S7 Confirmation",
    lifecycle: "execution",
    userSituation: "Execution is waiting for a user decision attached to a TaskNode.",
    pageFocus: "Put the confirmation action in the detail panel without hiding context.",
    primarySurfaces: ["Context inspector", "Confirmation options", "Session messages"],
    expectedUserAction: "Confirm, revise, or skip the pending action.",
  },
  {
    id: "s8-completed",
    label: "S8 Completed",
    lifecycle: "review",
    userSituation: "The session has produced a result card.",
    pageFocus: "Shift from execution progress to result review.",
    primarySurfaces: ["Result card", "TaskTree", "Context input"],
    expectedUserAction: "Review the result or request follow-up packaging.",
  },
  {
    id: "s9-file-changes",
    label: "S9 File Changes",
    lifecycle: "review",
    userSituation: "The user is reviewing file changes created by a TaskNode subtree.",
    pageFocus: "Explain concrete workspace changes before acceptance or audit.",
    primarySurfaces: ["File Change Summary", "TaskTree", "Audit link"],
    expectedUserAction: "Inspect changed files or ask Plato to explain a change.",
  },
  {
    id: "s10-permission-denied",
    label: "S10 Permission Denied",
    lifecycle: "recovery",
    userSituation: "The user can inspect the selected task but cannot mutate it.",
    pageFocus: "Keep the permission boundary explicit while preserving context.",
    primarySurfaces: ["TaskTree", "Permission detail", "Disabled input"],
    expectedUserAction: "Return, inspect, or wait for permission context to change.",
  },
  {
    id: "s11-stale-snapshot",
    label: "S11 Stale Snapshot",
    lifecycle: "recovery",
    userSituation: "The visible snapshot is stale after backend state changed.",
    pageFocus: "Disable high-risk actions and make resync the next safe action.",
    primarySurfaces: ["TaskTree", "Resync detail", "Stale warning"],
    expectedUserAction: "Refresh the snapshot before continuing.",
  },
  {
    id: "s12-backend-busy",
    label: "S12 Backend Busy",
    lifecycle: "recovery",
    userSituation: "A command was accepted but backend processing is delayed.",
    pageFocus: "Keep the current state readable while duplicate submit is disabled.",
    primarySurfaces: ["TaskTree", "Pending command detail", "Session messages"],
    expectedUserAction: "Wait for the next event or retry only after timeout.",
  },
  {
    id: "s13-command-failed",
    label: "S13 Command Failed",
    lifecycle: "recovery",
    userSituation: "A recoverable command error occurred without losing context.",
    pageFocus: "Show the error and keep retry/revise paths available.",
    primarySurfaces: ["TaskTree", "Recoverable error detail", "Context input"],
    expectedUserAction: "Retry the command or revise the task instruction.",
  },
  {
    id: "s14-execution-ask",
    label: "S14 Execution ASK",
    lifecycle: "execution",
    userSituation: "A Published Task is waiting for user input through ASK.",
    pageFocus:
      "Keep the TaskTree visible and answer the blocking ASK in the Detail Panel.",
    primarySurfaces: ["TaskTree", "Execution ASK detail", "Session messages"],
    expectedUserAction: "Answer, defer, or cancel the active ASK.",
  },
] as const satisfies readonly MainPageStateCatalogEntry[];

export function getMainPageStateCatalogEntry(
  stateId: MainPageStateId,
): MainPageStateCatalogEntry {
  return mainPageStateCatalog.find((entry) => entry.id === stateId) ??
    mainPageStateCatalog[0];
}
