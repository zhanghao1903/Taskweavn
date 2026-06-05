import type { BadgeTone } from "../../shared/components";
import type { SessionMessage } from "../../entities/message/model";
import type { ProjectSummary } from "../../entities/project/model";
import type { ResultCard } from "../../entities/result/model";
import type { SessionSummary } from "../../entities/session/model";
import type { TaskNodeId, TaskTree } from "../../entities/task/model";
import type { FileChangeSummary } from "../../entities/file-change/model";
import type { WorkflowSummary } from "../../entities/workflow/model";
import type {
  MainPageDetail,
  MainPageDetailMode,
  MainPageInputScope,
} from "./runtime/adapter";

export type {
  MainPageDetail,
  MainPageDetailMode,
  MainPageInputScope,
};

export type MainPageStateId =
  | "s1-empty"
  | "s2-understanding"
  | "s3-draft-ready"
  | "s4-task-selected"
  | "s5-task-editing"
  | "s6-running"
  | "s7-confirmation"
  | "s8-completed"
  | "s9-file-changes"
  | "s10-permission-denied"
  | "s11-stale-snapshot"
  | "s12-backend-busy"
  | "s13-command-failed"
  | "s14-execution-ask";

export type MainPageFixture = {
  id: MainPageStateId;
  label: string;
  topStatus: string;
  topStatusTone: BadgeTone;
  project: ProjectSummary;
  workflow: WorkflowSummary;
  session: SessionSummary;
  sessions: SessionSummary[];
  taskTree: TaskTree | null;
  selectedTaskNodeId: TaskNodeId | null;
  messages: SessionMessage[];
  detail: MainPageDetail;
  inputScope: MainPageInputScope;
  result: ResultCard | null;
  fileChangeSummary: FileChangeSummary | null;
};

const project: ProjectSummary = {
  id: "project-personal-site",
  name: "Personal Website",
};

const workflow: WorkflowSummary = {
  id: "workflow-planning-execution",
  name: "Task Planning & Execution",
  description: "Turn a natural language goal into a visible task plan.",
};

const sessions: SessionSummary[] = [
  {
    id: "session-website-plan",
    projectId: project.id,
    workflowId: workflow.id,
    name: "Personal website plan",
    status: "draft_ready",
  },
  {
    id: "session-product-intro",
    projectId: project.id,
    workflowId: workflow.id,
    name: "Product intro",
    status: "new",
  },
];

const baseTaskTree: TaskTree = {
  id: "task-tree-website",
  title: "Personal website project plan",
  nodes: [
    {
      id: "task-requirements",
      parentId: null,
      title: "Requirement analysis",
      summary: "Clarify audience and content scope",
      status: "done",
    },
    {
      id: "task-information-architecture",
      parentId: null,
      title: "Information architecture",
      summary: "Define pages and navigation",
      status: "done",
    },
    {
      id: "task-visual-direction",
      parentId: null,
      title: "Visual direction",
      summary: "Choose colors, typography, and layout tone",
      status: "waiting_user",
    },
    {
      id: "task-implementation",
      parentId: null,
      title: "Initial implementation",
      summary: "Build the first app shell and static states",
      status: "queued",
    },
  ],
};

const runningTaskTree: TaskTree = {
  ...baseTaskTree,
  nodes: baseTaskTree.nodes.map((node) =>
    node.id === "task-implementation" ? { ...node, status: "running" } : node,
  ),
};

const completedTaskTree: TaskTree = {
  ...baseTaskTree,
  nodes: baseTaskTree.nodes.map((node) => ({ ...node, status: "done" })),
};

const failedTaskTree: TaskTree = {
  ...baseTaskTree,
  nodes: baseTaskTree.nodes.map((node) =>
    node.id === "task-implementation" ? { ...node, status: "failed" } : node,
  ),
};

const executionAskTaskTree: TaskTree = {
  ...baseTaskTree,
  nodes: baseTaskTree.nodes.map((node) =>
    node.id === "task-implementation"
      ? { ...node, status: "waiting_user" }
      : node,
  ),
};

const baseMessages: SessionMessage[] = [
  {
    id: "message-draft-ready",
    sessionId: sessions[0].id,
    taskNodeId: null,
    kind: "informational",
    title: "Draft task plan ready",
    body: "Plato produced a first task breakdown for review.",
    createdAt: "2026-05-17T10:00:00+08:00",
  },
];

const confirmationMessage: SessionMessage = {
  id: "message-confirmation",
  sessionId: sessions[0].id,
  taskNodeId: "task-visual-direction",
  kind: "actionable",
  title: "Visual direction needs confirmation",
  body: "Confirm the first visual baseline before implementation continues.",
  createdAt: "2026-05-17T10:03:00+08:00",
};

const result: ResultCard = {
  id: "result-website-plan",
  taskNodeId: "task-implementation",
  title: "Website plan complete",
  summary:
    "The first implementation plan is ready, including page structure, styling direction, and build tasks.",
};

const fileChangeSummary: FileChangeSummary = {
  taskNodeId: "task-implementation",
  changedFiles: ["package.json", "src/App.tsx", "src/styles.css"],
};

function state(
  fixture: Omit<
    MainPageFixture,
    "project" | "workflow" | "session" | "sessions"
  >,
): MainPageFixture {
  return {
    project,
    workflow,
    session: sessions[0],
    sessions,
    ...fixture,
  };
}

export const mainPageStates: MainPageFixture[] = [
  state({
    id: "s1-empty",
    label: "S1 Empty",
    topStatus: "New session",
    topStatusTone: "neutral",
    taskTree: null,
    selectedTaskNodeId: null,
    messages: [],
    detail: {
      mode: "workflow",
      eyebrow: "Workflow",
      title: workflow.name,
      body: "Start with a natural language goal. Plato will turn it into a visible task plan before execution.",
    },
    inputScope: {
      label: "Writing to workflow",
      placeholder: "Describe the goal you want Plato to plan.",
    },
    result: null,
    fileChangeSummary: null,
  }),
  state({
    id: "s2-understanding",
    label: "S2 Understanding",
    topStatus: "Understanding",
    topStatusTone: "blue",
    taskTree: null,
    selectedTaskNodeId: null,
    messages: [
      {
        id: "message-understanding",
        sessionId: sessions[0].id,
        taskNodeId: null,
        kind: "informational",
        title: "Understanding user goal",
        body: "Plato is extracting goals, constraints, and likely deliverables.",
        createdAt: "2026-05-17T10:00:00+08:00",
      },
    ],
    detail: {
      mode: "session",
      eyebrow: "Session",
      title: "Understanding goal",
      body: "The session is collecting intent before producing a draft task plan.",
    },
    inputScope: {
      label: "Writing to session",
      placeholder: "Add constraints, examples, or missing context.",
    },
    result: null,
    fileChangeSummary: null,
  }),
  state({
    id: "s3-draft-ready",
    label: "S3 Draft Ready",
    topStatus: "Draft ready",
    topStatusTone: "blue",
    taskTree: baseTaskTree,
    selectedTaskNodeId: null,
    messages: baseMessages,
    detail: {
      mode: "session",
      eyebrow: "Draft task plan",
      title: "Review the generated structure",
      body: "Review the draft task plan before publishing. Select a task to inspect or refine it.",
    },
    inputScope: {
      label: "Writing to task plan",
      placeholder: "Ask Plato to refine the overall plan.",
    },
    result: null,
    fileChangeSummary: null,
  }),
  state({
    id: "s4-task-selected",
    label: "S4 Task Selected",
    topStatus: "Task selected",
    topStatusTone: "blue",
    taskTree: baseTaskTree,
    selectedTaskNodeId: "task-visual-direction",
    messages: baseMessages,
    detail: {
      mode: "task",
      eyebrow: "Task",
      title: "Visual direction",
      body: "This task defines the style baseline: colors, typography, and layout tone.",
    },
    inputScope: {
      label: "Writing to selected task",
      placeholder: "Add guidance for the selected task.",
    },
    result: null,
    fileChangeSummary: null,
  }),
  state({
    id: "s5-task-editing",
    label: "S5 Editing",
    topStatus: "Editing task",
    topStatusTone: "warning",
    taskTree: baseTaskTree,
    selectedTaskNodeId: "task-visual-direction",
    messages: [
      ...baseMessages,
      {
        id: "message-editing",
        sessionId: sessions[0].id,
        taskNodeId: "task-visual-direction",
        kind: "response",
        title: "User guidance added",
        body: "Prefer a calm modern classical style, avoiding neon AI visuals.",
        createdAt: "2026-05-17T10:02:00+08:00",
      },
    ],
    detail: {
      mode: "editing",
      eyebrow: "Task editing",
      title: "Refining visual direction",
      body: "Task-scoped input updates this task without changing the entire session plan.",
    },
    inputScope: {
      label: "Writing to Visual direction",
      placeholder: "Write instructions that only apply to this task.",
    },
    result: null,
    fileChangeSummary: null,
  }),
  state({
    id: "s6-running",
    label: "S6 Running",
    topStatus: "Executing",
    topStatusTone: "blue",
    taskTree: runningTaskTree,
    selectedTaskNodeId: "task-implementation",
    messages: [
      ...baseMessages,
      {
        id: "message-running",
        sessionId: sessions[0].id,
        taskNodeId: "task-implementation",
        kind: "informational",
        title: "Implementation started",
        body: "The implementation task is running in the isolated Session Workspace.",
        createdAt: "2026-05-17T10:05:00+08:00",
      },
    ],
    detail: {
      mode: "task",
      eyebrow: "Running task",
      title: "Initial implementation",
      body: "Plato is executing this task. You can append guidance, but completed tasks are read-only.",
    },
    inputScope: {
      label: "Writing to Initial implementation",
      placeholder: "Append guidance for the running task.",
    },
    result: null,
    fileChangeSummary: null,
  }),
  state({
    id: "s7-confirmation",
    label: "S7 Confirmation",
    topStatus: "Waiting for user",
    topStatusTone: "warning",
    taskTree: runningTaskTree,
    selectedTaskNodeId: "task-visual-direction",
    messages: [...baseMessages, confirmationMessage],
    detail: {
      mode: "confirmation",
      eyebrow: "Confirmation required",
      title: "Confirm visual baseline",
      body: "This confirmation is attached to the selected task and must be resolved before execution continues.",
      actionLabel: "Confirm baseline",
    },
    inputScope: {
      label: "Answering Visual direction",
      placeholder: "Explain a change, or choose one of the confirmation options.",
    },
    result: null,
    fileChangeSummary: null,
  }),
  state({
    id: "s8-completed",
    label: "S8 Completed",
    topStatus: "Completed",
    topStatusTone: "success",
    taskTree: completedTaskTree,
    selectedTaskNodeId: "task-implementation",
    messages: [
      ...baseMessages,
      {
        id: "message-completed",
        sessionId: sessions[0].id,
        taskNodeId: "task-implementation",
        kind: "informational",
        title: "Result ready",
        body: "The initial implementation result is ready for review.",
        createdAt: "2026-05-17T10:12:00+08:00",
      },
    ],
    detail: {
      mode: "result",
      eyebrow: "Result",
      title: result.title,
      body: result.summary,
    },
    inputScope: {
      label: "Writing a follow-up",
      placeholder: "Ask a follow-up or request result packaging.",
    },
    result,
    fileChangeSummary: null,
  }),
  state({
    id: "s9-file-changes",
    label: "S9 File Changes",
    topStatus: "Review",
    topStatusTone: "success",
    taskTree: completedTaskTree,
    selectedTaskNodeId: "task-implementation",
    messages: [
      ...baseMessages,
      {
        id: "message-file-summary",
        sessionId: sessions[0].id,
        taskNodeId: "task-implementation",
        kind: "informational",
        title: "File changes summarized",
        body: "Parent tasks aggregate file changes from their child tasks.",
        createdAt: "2026-05-17T10:15:00+08:00",
      },
    ],
    detail: {
      mode: "fileChanges",
      eyebrow: "File changes",
      title: "Implementation changed 3 files",
      body: "Review changed files before accepting the result. Audit remains available for deeper traceability.",
    },
    inputScope: {
      label: "Writing in review",
      placeholder: "Ask Plato to explain a file change or prepare a follow-up.",
    },
    result,
    fileChangeSummary,
  }),
  state({
    id: "s10-permission-denied",
    label: "S10 Permission Denied",
    topStatus: "Read-only",
    topStatusTone: "danger",
    taskTree: baseTaskTree,
    selectedTaskNodeId: "task-visual-direction",
    messages: [
      ...baseMessages,
      {
        id: "message-permission-denied",
        sessionId: sessions[0].id,
        taskNodeId: "task-visual-direction",
        kind: "error",
        title: "Permission boundary",
        body: "This task is read-only in the current context. Edit and publish actions are disabled.",
        createdAt: "2026-05-17T10:18:00+08:00",
      },
    ],
    detail: {
      mode: "task",
      eyebrow: "Permission",
      title: "Editing is unavailable",
      body: "The selected task can be inspected, but mutation actions are disabled by the current permission state.",
    },
    inputScope: {
      label: "Input paused for read-only task",
      placeholder: "Input disabled until permission changes.",
    },
    result: null,
    fileChangeSummary: null,
  }),
  state({
    id: "s11-stale-snapshot",
    label: "S11 Sync Required",
    topStatus: "Needs sync",
    topStatusTone: "warning",
    taskTree: runningTaskTree,
    selectedTaskNodeId: "task-implementation",
    messages: [
      ...baseMessages,
      {
        id: "message-stale",
        sessionId: sessions[0].id,
        taskNodeId: "task-implementation",
        kind: "error",
        title: "Session needs refresh",
        body: "Visible task data changed. Refresh before taking high-risk actions.",
        createdAt: "2026-05-17T10:19:00+08:00",
      },
    ],
    detail: {
      mode: "session",
      eyebrow: "Resync required",
      title: "Refresh before continuing",
      body: "High-risk actions stay disabled until Plato reloads the latest session state.",
      actionLabel: "Resync",
    },
    inputScope: {
      label: "Input paused until refresh",
      placeholder: "Input disabled while waiting for resync.",
    },
    result: null,
    fileChangeSummary: null,
  }),
  state({
    id: "s12-backend-busy",
    label: "S12 Update Pending",
    topStatus: "Syncing",
    topStatusTone: "warning",
    taskTree: runningTaskTree,
    selectedTaskNodeId: "task-implementation",
    messages: [
      ...baseMessages,
      {
        id: "message-backend-busy",
        sessionId: sessions[0].id,
        taskNodeId: "task-implementation",
        kind: "informational",
        title: "Update accepted",
        body: "Plato is still applying the update. Duplicate submit is disabled.",
        createdAt: "2026-05-17T10:20:00+08:00",
      },
    ],
    detail: {
      mode: "task",
      eyebrow: "Pending update",
      title: "Applying update",
      body: "Plato is keeping the current task plan visible while waiting for the update to finish.",
    },
    inputScope: {
      label: "Writing to Initial implementation",
      placeholder: "Update is pending; duplicate submit is disabled.",
    },
    result: null,
    fileChangeSummary: null,
  }),
  state({
    id: "s13-command-failed",
    label: "S13 Action Needs Retry",
    topStatus: "Recoverable error",
    topStatusTone: "danger",
    taskTree: failedTaskTree,
    selectedTaskNodeId: "task-implementation",
    messages: [
      ...baseMessages,
      {
        id: "message-command-failed",
        sessionId: sessions[0].id,
        taskNodeId: "task-implementation",
        kind: "error",
        title: "Action needs retry",
        body: "The last action did not complete. Retry is available.",
        createdAt: "2026-05-17T10:21:00+08:00",
      },
    ],
    detail: {
      mode: "task",
      eyebrow: "Recoverable error",
      title: "Retry the last action",
      body: "The current task plan is still available. Retry or revise the task before continuing.",
      actionLabel: "Retry",
    },
    inputScope: {
      label: "Writing to Initial implementation",
      placeholder: "Revise the instruction or retry the last action.",
    },
    result: null,
    fileChangeSummary: null,
  }),
  state({
    id: "s14-execution-ask",
    label: "S14 Task Question",
    topStatus: "Waiting for user",
    topStatusTone: "warning",
    taskTree: executionAskTaskTree,
    selectedTaskNodeId: "task-implementation",
    messages: [
      ...baseMessages,
      {
        id: "message-execution-ask",
        sessionId: sessions[0].id,
        taskNodeId: "task-implementation",
        kind: "actionable",
        title: "Implementation needs input",
        body: "Choose the deployment target before execution can continue.",
        createdAt: "2026-05-17T10:22:00+08:00",
      },
    ],
    detail: {
      mode: "task",
      eyebrow: "Task input",
      title: "Initial implementation needs input",
      body: "The running task is blocked until this question is answered.",
    },
    inputScope: {
      label: "Answering Initial implementation",
      placeholder: "Answer the question in the detail panel.",
    },
    result: null,
    fileChangeSummary: null,
  }),
];

export const defaultMainPageStateId: MainPageStateId = "s3-draft-ready";

export function getMainPageState(stateId: MainPageStateId): MainPageFixture {
  return (
    mainPageStates.find((fixture) => fixture.id === stateId) ??
    mainPageStates[0]
  );
}
