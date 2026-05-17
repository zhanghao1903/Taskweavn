import type { BadgeTone } from "../../shared/components";
import type { SessionMessage } from "../../entities/message/model";
import type { ProjectSummary } from "../../entities/project/model";
import type { ResultCard } from "../../entities/result/model";
import type { SessionSummary } from "../../entities/session/model";
import type { TaskNodeId, TaskTree } from "../../entities/task/model";
import type { FileChangeSummary } from "../../entities/file-change/model";
import type { WorkflowSummary } from "../../entities/workflow/model";

export type MainPageStateId =
  | "s1-empty"
  | "s2-understanding"
  | "s3-draft-ready"
  | "s4-task-selected"
  | "s5-task-editing"
  | "s6-running"
  | "s7-confirmation"
  | "s8-completed"
  | "s9-file-changes";

export type MainPageDetailMode =
  | "workflow"
  | "session"
  | "task"
  | "editing"
  | "confirmation"
  | "result"
  | "fileChanges";

export type MainPageDetail = {
  mode: MainPageDetailMode;
  eyebrow: string;
  title: string;
  body: string;
  actionLabel?: string;
};

export type MainPageInputScope = {
  label: string;
  placeholder: string;
};

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

const baseMessages: SessionMessage[] = [
  {
    id: "message-draft-ready",
    sessionId: sessions[0].id,
    taskNodeId: null,
    kind: "informational",
    title: "Draft task tree ready",
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
      body: "Start with a natural language goal. Plato will turn it into a visible TaskTree before execution.",
    },
    inputScope: {
      label: "Scope: workflow",
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
      body: "The session is collecting intent before producing a draft TaskTree.",
    },
    inputScope: {
      label: "Scope: current session",
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
      eyebrow: "Draft TaskTree",
      title: "Review the generated structure",
      body: "Review the draft TaskTree before publishing. Select a TaskNode to inspect or refine it.",
    },
    inputScope: {
      label: "Scope: task tree",
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
      eyebrow: "TaskNode",
      title: "Visual direction",
      body: "This TaskNode defines the style baseline: colors, typography, and layout tone.",
    },
    inputScope: {
      label: "Scope: selected task",
      placeholder: "Add guidance for the selected TaskNode.",
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
      body: "Task-scoped input updates this TaskNode without changing the entire session plan.",
    },
    inputScope: {
      label: "Scope: selected task / Visual direction",
      placeholder: "Write instructions that only apply to this TaskNode.",
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
        body: "The implementation TaskNode is running in the isolated Session Workspace.",
        createdAt: "2026-05-17T10:05:00+08:00",
      },
    ],
    detail: {
      mode: "task",
      eyebrow: "Running task",
      title: "Initial implementation",
      body: "Plato is executing this TaskNode. You can append guidance, but completed nodes are read-only.",
    },
    inputScope: {
      label: "Scope: running task / Initial implementation",
      placeholder: "Append guidance for the running TaskNode.",
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
      body: "This confirmation is attached to the selected TaskNode and must be resolved before execution continues.",
      actionLabel: "Confirm baseline",
    },
    inputScope: {
      label: "Scope: confirmation / Visual direction",
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
      label: "Scope: completed session",
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
        body: "Parent nodes aggregate file changes from their child TaskNodes.",
        createdAt: "2026-05-17T10:15:00+08:00",
      },
    ],
    detail: {
      mode: "fileChanges",
      eyebrow: "File Change Summary",
      title: "Implementation changed 3 files",
      body: "Review changed files before accepting the result. Audit remains available for deeper traceability.",
    },
    inputScope: {
      label: "Scope: review",
      placeholder: "Ask Plato to explain a file change or prepare a follow-up.",
    },
    result,
    fileChangeSummary,
  }),
];

export const defaultMainPageStateId: MainPageStateId = "s3-draft-ready";

export function getMainPageState(stateId: MainPageStateId): MainPageFixture {
  return (
    mainPageStates.find((fixture) => fixture.id === stateId) ??
    mainPageStates[0]
  );
}
