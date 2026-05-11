import type {
  ConfirmationActionView,
  SessionMessageView,
  SessionOverview,
  TaskFileChangeSummary,
  TaskNodeDetail,
  TaskNodeSummary,
  TaskTreeView,
} from "../contracts";

const now = "2026-05-11T10:30:00+08:00";

export const taskNodes: TaskNodeSummary[] = [
  {
    taskId: "task-plan",
    parentId: null,
    title: "生成个人网站任务树",
    intentPreview: "把用户的自然语言目标拆成可确认的 Task Tree List。",
    status: "done",
    orderIndex: 0,
    depth: 0,
    badges: [{ label: "completed", tone: "success" }],
    childIds: ["task-home", "task-style", "task-review"],
    hasPendingConfirmation: false,
    unreadMessageCount: 0,
    fileChangeCount: 3,
  },
  {
    taskId: "task-home",
    parentId: "task-plan",
    title: "创建首页结构",
    intentPreview: "生成首页 HTML，包含 hero、项目、联系方式区域。",
    status: "running",
    orderIndex: 1,
    depth: 1,
    badges: [
      { label: "running", tone: "info" },
      { label: "1 ask", tone: "warning" },
    ],
    childIds: [],
    hasPendingConfirmation: true,
    unreadMessageCount: 2,
    fileChangeCount: 1,
  },
  {
    taskId: "task-style",
    parentId: "task-plan",
    title: "设计页面样式",
    intentPreview: "建立极简、低装饰、响应式的 CSS 视觉系统。",
    status: "pending",
    orderIndex: 2,
    depth: 1,
    badges: [{ label: "pending", tone: "neutral" }],
    childIds: [],
    hasPendingConfirmation: false,
    unreadMessageCount: 1,
    fileChangeCount: 0,
  },
  {
    taskId: "task-review",
    parentId: "task-plan",
    title: "自检并总结",
    intentPreview: "检查文件结构、链接与响应式布局，生成交付总结。",
    status: "draft",
    orderIndex: 3,
    depth: 1,
    badges: [{ label: "draft", tone: "neutral" }],
    childIds: [],
    hasPendingConfirmation: false,
    unreadMessageCount: 0,
    fileChangeCount: 0,
  },
];

const taskById = new Map(taskNodes.map((task) => [task.taskId, task]));

export const taskTrees: TaskTreeView[] = [
  {
    rootTaskId: "task-plan",
    nodes: taskNodes,
  },
];

export const sessionOverview: SessionOverview = {
  sessionId: "demo-session",
  name: "Personal website build",
  status: "awaiting_user",
  activeTaskId: "task-home",
  rootTasks: taskNodes.filter((task) => task.parentId === null),
  pendingConfirmationCount: 1,
};

export const taskDetails: Record<string, TaskNodeDetail> = {
  "task-plan": {
    summary: taskById.get("task-plan")!,
    intent:
      "将用户创建个人网站的目标拆解成可确认、可编辑、可执行的 Task Tree List。",
    constraints: ["保持 Task Tree 为树形结构", "所有确认动作绑定具体 Task Node"],
    permissions: {
      canEdit: false,
      canAppendGuidance: false,
      canResolveConfirmation: false,
      canPublish: false,
      canCancel: false,
      canRetry: false,
    },
    resultSummary: {
      result: "已生成初始任务树，包含首页结构、样式设计和自检总结。",
      failureReason: null,
      nextSteps: ["等待当前首页结构任务确认后继续执行。"],
    },
  },
  "task-home": {
    summary: taskById.get("task-home")!,
    intent:
      "创建首页 HTML 骨架，包含清晰的个人介绍、项目列表、联系方式和基础语义结构。",
    constraints: ["不要营销式大 hero", "内容区需要方便后续修改", "保持无障碍语义标签"],
    permissions: {
      canEdit: false,
      canAppendGuidance: true,
      canResolveConfirmation: true,
      canPublish: false,
      canCancel: false,
      canRetry: false,
    },
    resultSummary: {
      result: null,
      failureReason: null,
      nextSteps: ["确认是否允许写入 index.html。"],
    },
  },
  "task-style": {
    summary: taskById.get("task-style")!,
    intent:
      "为个人网站建立 CSS 视觉系统，优先可读性、节奏和响应式体验。",
    constraints: ["极简", "不要大面积渐变", "桌面和窄屏都不能重叠"],
    permissions: {
      canEdit: true,
      canAppendGuidance: true,
      canResolveConfirmation: false,
      canPublish: true,
      canCancel: true,
      canRetry: false,
    },
    resultSummary: {
      result: null,
      failureReason: null,
      nextSteps: ["可继续补充视觉偏好。"],
    },
  },
  "task-review": {
    summary: taskById.get("task-review")!,
    intent: "完成后检查页面结构、文件引用、响应式布局，并生成交付总结。",
    constraints: ["只读检查", "总结要包含文件变更清单"],
    permissions: {
      canEdit: true,
      canAppendGuidance: true,
      canResolveConfirmation: false,
      canPublish: true,
      canCancel: true,
      canRetry: false,
    },
    resultSummary: {
      result: null,
      failureReason: null,
      nextSteps: [],
    },
  },
};

export const messages: SessionMessageView[] = [
  {
    messageId: "msg-1",
    sessionId: "demo-session",
    taskId: null,
    type: "user",
    author: "user",
    content: "帮我创建一个个人网站，包含首页、项目列表和联系方式。",
    createdAt: "2026-05-11T10:21:00+08:00",
  },
  {
    messageId: "msg-2",
    sessionId: "demo-session",
    taskId: "task-plan",
    type: "agent",
    author: "agent",
    content: "我已将目标拆成 3 个子任务，先创建结构，再补样式，最后自检总结。",
    createdAt: "2026-05-11T10:22:00+08:00",
  },
  {
    messageId: "msg-3",
    sessionId: "demo-session",
    taskId: "task-style",
    type: "user",
    author: "user",
    content: "页面风格要极简，不要大面积渐变。",
    createdAt: "2026-05-11T10:23:00+08:00",
  },
  {
    messageId: "msg-4",
    sessionId: "demo-session",
    taskId: "task-home",
    type: "confirmation",
    author: "agent",
    content: "需要确认：是否允许创建 index.html？",
    createdAt: now,
    relatedConfirmationId: "confirm-write-index",
  },
];

export const confirmations: ConfirmationActionView[] = [
  {
    confirmationId: "confirm-write-index",
    sessionId: "demo-session",
    taskId: "task-home",
    title: "允许写入首页文件？",
    description:
      "TaskWeavn 准备创建 index.html。该操作会修改 workspace 文件，需要用户确认。",
    riskLabel: "medium risk",
    options: [
      { value: "approve", label: "允许", tone: "primary" },
      { value: "skip", label: "跳过", tone: "neutral" },
      { value: "deny", label: "拒绝", tone: "danger" },
    ],
    defaultValue: "skip",
    status: "pending",
  },
];

export const fileChanges: TaskFileChangeSummary[] = [
  {
    fileChangeId: "file-1",
    ownerTaskId: "task-home",
    path: "personal-site/index.html",
    changeType: "created",
    summary: "创建首页 HTML 结构。",
    fromDescendant: false,
  },
  {
    fileChangeId: "file-2",
    ownerTaskId: "task-home",
    path: "personal-site/index.html",
    changeType: "modified",
    summary: "补充项目列表占位区域。",
    fromDescendant: true,
  },
];
