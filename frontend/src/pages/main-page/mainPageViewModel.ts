import type {
  AuditFilterKind,
  AskRequestView,
  ConfirmationActionView,
  FileChangeSummaryView,
  MainPageSnapshot,
  PlanningAskView,
  ResultCardView,
  SessionMessageView,
  SessionSummary,
  TaskNodeCardView,
  TaskNodeId,
} from "../../shared/api/types";
import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import {
  buildAuditSessionRoute,
  buildAuditTaskRoute,
} from "../../app/routes";
import type { BadgePresentation } from "./mainPageSelectors";
import {
  buildTaskScopedProjection,
  selectEventConnectionStatusPresentation,
  selectMainPagePrimaryStatusPresentation,
} from "./mainPageSelectors";
import type {
  DetailOverride,
  EventConnectionStatus,
  MainPageDetailHeader,
  MainPageInputScopeView,
  MainPageSelectionTarget,
} from "./mainPageUiTypes";
import type { MainPageStateMetadata } from "./runtime/adapter";

export type MainPageDetailView =
  | {
      kind: "executionAsk";
      ask: AskRequestView;
      commandError: string | null;
      commandRecoveryActions: ProductRecoveryAction[];
      header: MainPageDetailHeader;
      isAnsweringAsk: boolean;
      isCancellingAsk: boolean;
      isDeferringAsk: boolean;
      selectedTask?: TaskNodeCardView;
    }
  | {
      kind: "confirmation";
      commandError: string | null;
      commandRecoveryActions: ProductRecoveryAction[];
      confirmation: ConfirmationActionView | undefined;
      fallbackBody: string;
      header: MainPageDetailHeader;
      isResolvingConfirmation: boolean;
    }
  | {
      kind: "confirmationResolved";
      decision: "confirmed" | "revise" | "skipped";
      header: MainPageDetailHeader;
    }
  | {
      kind: "result";
      fileChangeSummary: FileChangeSummaryView | null;
      header: MainPageDetailHeader;
      result: ResultCardView;
    }
  | {
      kind: "fileChanges";
      fileChangeSummary: FileChangeSummaryView;
      header: MainPageDetailHeader;
      result: ResultCardView | null;
    }
  | {
      kind: "task";
      header: MainPageDetailHeader;
      isRetryingTask: boolean;
      isStoppingTask: boolean;
      selectedTask: TaskNodeCardView;
    }
  | {
      kind: "plan";
      header: MainPageDetailHeader;
      taskTree: NonNullable<MainPageSnapshot["taskTree"]>;
    }
  | {
      kind: "note";
      body: string;
      header: MainPageDetailHeader;
    };

export type MainPageInputCommandMode =
  | "generate_task_tree"
  | "append_plan_input"
  | "append_session_input"
  | "append_task_input";

export type MainPageInputViewModel = {
  disabled: boolean;
  disabledReason: string | null;
  mode: MainPageInputCommandMode;
  scope: MainPageInputScopeView;
  target: "session" | "plan" | "task";
  taskNodeId: TaskNodeId | null;
};

export type MainPageTopBarViewModel = {
  brandLabel: string;
  contextItems: string[];
  statuses: BadgePresentation[];
};

export type MainPageSidebarViewModel = {
  activeSession: SessionSummary;
  sessions: SessionSummary[];
};

export type MainPageWorkspaceViewModel = {
  auditEntry: MainPageAuditEntryViewModel;
  eventError: string | null;
  isPublishingTaskTree: boolean;
  showPublishTaskTree: boolean;
  taskTreeCommandError: string | null;
  taskTreeCommandRecoveryActions: ProductRecoveryAction[];
  taskTreeId: string | null;
  title: string;
  uiNotice: string | null;
};

export type MainPageAuditEntryViewModel = {
  disabledReason: string | null;
  href: string;
  isEnabled: boolean;
  label: string;
  returnFocus: "session" | "task" | "confirmation" | "result" | "file_change";
  scope: "session" | "task";
};

export type MainPageTaskWorkspaceViewModel = {
  allMessages: SessionMessageView[];
  authoringDiagnostic: MainPageAuthoringDiagnosticViewModel | null;
  fileChangeSummary: FileChangeSummaryView | null;
  isGeneratingTaskPlan: boolean;
  isMessageScoped: boolean;
  isTaskPlanSelected: boolean;
  messages: SessionMessageView[];
  result: ResultCardView | null;
  selectedTask: TaskNodeCardView | undefined;
  selectedTaskNodeId: TaskNodeId | null;
  taskTree: MainPageSnapshot["taskTree"];
  totalMessageCount: number;
  visibleMessageCount: number;
};

export type MainPageAuthoringDiagnosticViewModel = {
  code: "dirty_authoring_state";
  message: string;
  severity: "warning";
};

export type MainPageAuthoringAskViewModel = {
  asks: PlanningAskView[];
  commandError: string | null;
  commandRecoveryActions: ProductRecoveryAction[];
  isSubmitting: boolean;
  rawTaskId: string;
  summary: string | null;
  title: string;
};

export type MainPageWorkAreaView =
  | {
      kind: "authoringAsk";
      authoringAsk: MainPageAuthoringAskViewModel;
    }
  | {
      kind: "taskWorkspace";
    };

export type MainPageViewModel = {
  detail: MainPageDetailView;
  input: MainPageInputViewModel;
  mainWorkArea: MainPageWorkAreaView;
  sessionId: string;
  sidebar: MainPageSidebarViewModel;
  taskWorkspace: MainPageTaskWorkspaceViewModel;
  topBar: MainPageTopBarViewModel;
  workspace: MainPageWorkspaceViewModel;
};

export type BuildMainPageViewModelInput = {
  auditRouteAvailable?: boolean;
  authoringAskError: string | null;
  authoringAskRecoveryActions: ProductRecoveryAction[];
  confirmationError: string | null;
  confirmationRecoveryActions: ProductRecoveryAction[];
  detailOverride: DetailOverride;
  eventConnectionStatus: EventConnectionStatus;
  eventError: string | null;
  isAnsweringAuthoringAsk: boolean;
  executionAskError: string | null;
  executionAskRecoveryActions: ProductRecoveryAction[];
  isAnsweringAsk: boolean;
  isCancellingAsk: boolean;
  isDeferringAsk: boolean;
  inputDisabled: boolean;
  isPublishingTaskTree: boolean;
  isRetryingTask: boolean;
  isStoppingTask: boolean;
  isResolvingConfirmation: boolean;
  metadata: MainPageStateMetadata;
  selectionTarget?: MainPageSelectionTarget;
  selectedTaskNodeId: TaskNodeId | null;
  snapshot: MainPageSnapshot;
  taskTreeCommandError: string | null;
  taskTreeCommandRecoveryActions: ProductRecoveryAction[];
  uiNotice: string | null;
};

export function buildMainPageViewModel({
  auditRouteAvailable = true,
  authoringAskError,
  authoringAskRecoveryActions,
  confirmationError,
  confirmationRecoveryActions,
  detailOverride,
  eventConnectionStatus,
  eventError,
  isAnsweringAuthoringAsk,
  executionAskError,
  executionAskRecoveryActions,
  isAnsweringAsk,
  isCancellingAsk,
  isDeferringAsk,
  inputDisabled,
  isPublishingTaskTree,
  isRetryingTask,
  isStoppingTask,
  isResolvingConfirmation,
  metadata,
  selectionTarget,
  selectedTaskNodeId,
  snapshot,
  taskTreeCommandError,
  taskTreeCommandRecoveryActions,
  uiNotice,
}: BuildMainPageViewModelInput): MainPageViewModel {
  const nodes = snapshot.taskTree?.nodes ?? [];
  const authoringAsk = authoringAskViewFor({
    commandError: authoringAskError,
    commandRecoveryActions: authoringAskRecoveryActions,
    isSubmitting: isAnsweringAuthoringAsk,
    planning: snapshot.planning,
  });
  const effectiveSelectionTarget =
    selectionTarget ?? (selectedTaskNodeId ? "task" : "auto");
  const effectiveSelectedTaskNodeId =
    effectiveSelectionTarget === "plan"
      ? null
      : selectedTaskNodeId ?? metadata.initialSelectedTaskNodeId;
  const activeConfirmation =
    snapshot.pendingConfirmations.find(
      (confirmation) => confirmation.taskNodeId === effectiveSelectedTaskNodeId,
    ) ?? snapshot.pendingConfirmations[0];
  const activeExecutionAsk =
    snapshot.activeAsk?.status === "pending" ? snapshot.activeAsk : null;
  const hasConfirmationFocus =
    metadata.detail.mode === "confirmation" &&
    effectiveSelectedTaskNodeId === metadata.initialSelectedTaskNodeId;
  const wantsResultView =
    detailOverride === "result" ||
    (detailOverride === "auto" && metadata.detail.mode === "result");
  const wantsFileChangeView =
    detailOverride === "fileChanges" ||
    (detailOverride === "auto" && metadata.detail.mode === "fileChanges");
  const scopedProjection = buildTaskScopedProjection({
    fileChangeSummary: snapshot.fileChangeSummary,
    messages: snapshot.messages,
    nodes,
    result: snapshot.result,
    selectedTaskNodeId: effectiveSelectedTaskNodeId,
  });
  const {
    fileChangeSummary,
    messages,
    result,
    selectedTask,
    totalMessageCount,
    visibleMessageCount,
  } = scopedProjection;
  const hasExecutionAskFocus = shouldShowExecutionAskDetail({
    activeExecutionAsk,
    isTaskPlanExplicitlySelected: effectiveSelectionTarget === "plan",
    selectedTask,
  });
  const header = detailHeaderFor({
    activeExecutionAsk,
    hasExecutionAskFocus,
    hasConfirmationFocus,
    hasFileChangeView: wantsFileChangeView && fileChangeSummary !== null,
    hasResultView: wantsResultView && result !== null,
    metadata,
    selectedTask,
    taskTree: snapshot.taskTree,
  });
  const input = inputViewFor({
    hasAuthoringAsk: authoringAsk !== null,
    sessionPermissions: snapshot.permissions,
    inputDisabled,
    metadata,
    selectedTask,
    hasConfirmationFocus,
    detailOverride,
    taskTree: snapshot.taskTree,
  });
  const auditEntry = auditEntryFor({
    activeConfirmation,
    auditRouteAvailable,
    fileChangeSummary,
    hasConfirmationFocus,
    hasFileChangeView: wantsFileChangeView && fileChangeSummary !== null,
    hasResultView: wantsResultView && result !== null,
    result,
    selectedTask,
    sessionId: snapshot.session.id,
    sessionPermissions: snapshot.permissions,
  });

  return {
    detail: detailViewFor({
      activeConfirmation,
      activeExecutionAsk,
      commandError: confirmationError,
      commandRecoveryActions: confirmationRecoveryActions,
      executionAskRecoveryActions,
      executionAskError,
      fileChangeSummary,
      hasExecutionAskFocus,
      hasConfirmationFocus,
      header,
      isAnsweringAsk,
      isRetryingTask,
      isCancellingAsk,
      isDeferringAsk,
      isStoppingTask,
      isResolvingConfirmation,
      result,
      selectedTask,
      taskTree: snapshot.taskTree,
      wantsFileChangeView,
      wantsResultView,
    }),
    input,
    mainWorkArea:
      authoringAsk === null
        ? { kind: "taskWorkspace" }
        : { authoringAsk, kind: "authoringAsk" },
    sessionId: snapshot.session.id,
    sidebar: {
      activeSession: snapshot.session,
      sessions: snapshot.sessions,
    },
    taskWorkspace: {
      allMessages: snapshot.messages,
      authoringDiagnostic: authoringDiagnosticViewFor(snapshot.planning),
      fileChangeSummary,
      isGeneratingTaskPlan:
        authoringAsk === null && snapshot.taskTree === null && inputDisabled,
      isMessageScoped: scopedProjection.isMessageScoped,
      isTaskPlanSelected:
        snapshot.taskTree !== null && effectiveSelectedTaskNodeId === null,
      messages,
      result,
      selectedTask,
      selectedTaskNodeId: effectiveSelectedTaskNodeId,
      taskTree: snapshot.taskTree,
      totalMessageCount,
      visibleMessageCount,
    },
    topBar: {
      brandLabel: "柏拉图 Plato",
      contextItems: [
        snapshot.project.name,
        snapshot.session.name,
      ],
      statuses: [
        selectMainPagePrimaryStatusPresentation(snapshot, metadata),
        selectEventConnectionStatusPresentation(eventConnectionStatus),
      ],
    },
    workspace: {
      auditEntry,
      eventError,
      isPublishingTaskTree,
      showPublishTaskTree:
        authoringAsk === null && snapshot.taskTree?.status === "draft",
      taskTreeCommandError,
      taskTreeCommandRecoveryActions,
      taskTreeId: snapshot.taskTree?.id ?? null,
      title:
        authoringAsk?.title ??
        (snapshot.taskTree === null ? "Start a new session" : "Plan & Progress"),
      uiNotice,
    },
  };
}

function authoringDiagnosticViewFor(
  planning: MainPageSnapshot["planning"],
): MainPageAuthoringDiagnosticViewModel | null {
  const diagnostic = planning?.diagnostics?.find(
    (item) => item.code === "dirty_authoring_state",
  );

  if (!diagnostic) {
    return null;
  }

  return {
    code: "dirty_authoring_state",
    message: diagnostic.message,
    severity: "warning",
  };
}

function authoringAskViewFor({
  commandError,
  commandRecoveryActions,
  isSubmitting,
  planning,
}: {
  commandError: string | null;
  commandRecoveryActions: ProductRecoveryAction[];
  isSubmitting: boolean;
  planning: MainPageSnapshot["planning"];
}): MainPageAuthoringAskViewModel | null {
  const pendingAsks =
    planning?.asks.filter((ask) => ask.status === "pending") ?? [];
  const rawTaskId = planning?.sourceRawTaskId ?? null;

  if (!planning || !rawTaskId || pendingAsks.length === 0) {
    return null;
  }

  return {
    asks: pendingAsks,
    commandError,
    commandRecoveryActions,
    isSubmitting,
    rawTaskId,
    summary: planning.summary ?? null,
    title: planning.title ?? "Planning questions",
  };
}

function auditEntryFor({
  activeConfirmation,
  auditRouteAvailable,
  fileChangeSummary,
  hasConfirmationFocus,
  hasFileChangeView,
  hasResultView,
  result,
  selectedTask,
  sessionId,
  sessionPermissions,
}: {
  activeConfirmation: ConfirmationActionView | undefined;
  auditRouteAvailable: boolean;
  fileChangeSummary: FileChangeSummaryView | null;
  hasConfirmationFocus: boolean;
  hasFileChangeView: boolean;
  hasResultView: boolean;
  result: ResultCardView | null;
  selectedTask: TaskNodeCardView | undefined;
  sessionId: string;
  sessionPermissions: MainPageSnapshot["permissions"];
}): MainPageAuditEntryViewModel {
  const route = auditRouteFor({
    activeConfirmation,
    fileChangeSummary,
    hasConfirmationFocus,
    hasFileChangeView,
    hasResultView,
    result,
    selectedTask,
    sessionId,
  });
  const permissionReason =
    sessionPermissions && !sessionPermissions.canOpenAudit
      ? sessionPermissions.readonlyReason ??
        "Audit is unavailable until permissions change."
      : null;

  return {
    ...route,
    disabledReason:
      permissionReason ??
      (auditRouteAvailable
        ? null
        : "Audit is not available for this view yet."),
    isEnabled: auditRouteAvailable && permissionReason === null,
    label: "View audit",
  };
}

function auditRouteFor({
  activeConfirmation,
  fileChangeSummary,
  hasConfirmationFocus,
  hasFileChangeView,
  hasResultView,
  result,
  selectedTask,
  sessionId,
}: {
  activeConfirmation: ConfirmationActionView | undefined;
  fileChangeSummary: FileChangeSummaryView | null;
  hasConfirmationFocus: boolean;
  hasFileChangeView: boolean;
  hasResultView: boolean;
  result: ResultCardView | null;
  selectedTask: TaskNodeCardView | undefined;
  sessionId: string;
}): Pick<MainPageAuditEntryViewModel, "href" | "returnFocus" | "scope"> {
  if (hasConfirmationFocus && activeConfirmation) {
    return taskAuditRoute({
      entry: "from_confirmation",
      filter: "confirmations",
      returnFocus: "confirmation",
      sessionId,
      taskNodeId: activeConfirmation.taskNodeId,
    });
  }

  if (hasFileChangeView && fileChangeSummary?.taskNodeId) {
    return taskAuditRoute({
      entry: "from_file_change",
      filter: "files",
      returnFocus: "file_change",
      sessionId,
      taskNodeId: fileChangeSummary.taskNodeId,
    });
  }

  if (hasResultView && result) {
    return {
      href: buildAuditSessionRoute(sessionId, {
        entry: "from_result",
        filter: "results",
        returnFocus: "result",
        returnSessionId: sessionId,
      }),
      returnFocus: "result",
      scope: "session",
    };
  }

  if (selectedTask) {
    return taskAuditRoute({
      entry: "from_task",
      returnFocus: "task",
      sessionId,
      taskNodeId: selectedTask.id,
    });
  }

  return {
    href: buildAuditSessionRoute(sessionId, {
      entry: "from_session",
      returnFocus: "session",
      returnSessionId: sessionId,
    }),
    returnFocus: "session",
    scope: "session",
  };
}

function taskAuditRoute({
  entry,
  filter,
  returnFocus,
  sessionId,
  taskNodeId,
}: {
  entry: "from_task" | "from_confirmation" | "from_file_change";
  filter?: AuditFilterKind;
  returnFocus: "task" | "confirmation" | "file_change";
  sessionId: string;
  taskNodeId: string;
}): Pick<MainPageAuditEntryViewModel, "href" | "returnFocus" | "scope"> {
  return {
    href: buildAuditTaskRoute(sessionId, taskNodeId, {
      entry,
      filter,
      returnFocus,
      returnSessionId: sessionId,
      returnTaskNodeId: taskNodeId,
    }),
    returnFocus,
    scope: "task",
  };
}

function detailViewFor({
  activeConfirmation,
  activeExecutionAsk,
  commandError,
  commandRecoveryActions,
  executionAskError,
  executionAskRecoveryActions,
  fileChangeSummary,
  hasExecutionAskFocus,
  hasConfirmationFocus,
  header,
  isAnsweringAsk,
  isCancellingAsk,
  isDeferringAsk,
  isRetryingTask,
  isStoppingTask,
  isResolvingConfirmation,
  result,
  selectedTask,
  taskTree,
  wantsFileChangeView,
  wantsResultView,
}: {
  activeConfirmation: ConfirmationActionView | undefined;
  activeExecutionAsk: AskRequestView | null;
  commandError: string | null;
  commandRecoveryActions: ProductRecoveryAction[];
  executionAskError: string | null;
  executionAskRecoveryActions: ProductRecoveryAction[];
  fileChangeSummary: FileChangeSummaryView | null;
  hasExecutionAskFocus: boolean;
  hasConfirmationFocus: boolean;
  header: MainPageDetailHeader;
  isAnsweringAsk: boolean;
  isCancellingAsk: boolean;
  isDeferringAsk: boolean;
  isRetryingTask: boolean;
  isStoppingTask: boolean;
  isResolvingConfirmation: boolean;
  result: ResultCardView | null;
  selectedTask: TaskNodeCardView | undefined;
  taskTree: MainPageSnapshot["taskTree"];
  wantsFileChangeView: boolean;
  wantsResultView: boolean;
}): MainPageDetailView {
  if (hasExecutionAskFocus && activeExecutionAsk) {
    return {
      kind: "executionAsk",
      ask: activeExecutionAsk,
      commandError: executionAskError,
      commandRecoveryActions: executionAskRecoveryActions,
      header,
      isAnsweringAsk,
      isCancellingAsk,
      isDeferringAsk,
      selectedTask,
    };
  }

  if (hasConfirmationFocus) {
    return {
      kind: "confirmation",
      commandError,
      commandRecoveryActions,
      confirmation: activeConfirmation,
      fallbackBody: header.body,
      header,
      isResolvingConfirmation,
    };
  }

  if (wantsResultView && result) {
    return {
      kind: "result",
      fileChangeSummary,
      header,
      result,
    };
  }

  if (wantsFileChangeView && fileChangeSummary) {
    return {
      kind: "fileChanges",
      fileChangeSummary,
      header,
      result,
    };
  }

  if (selectedTask) {
    return {
      kind: "task",
      header,
      isRetryingTask,
      isStoppingTask,
      selectedTask,
    };
  }

  if (taskTree) {
    return {
      kind: "plan",
      header,
      taskTree,
    };
  }

  return {
    kind: "note",
    body: header.body,
    header,
  };
}

function detailHeaderFor({
  activeExecutionAsk,
  hasExecutionAskFocus,
  hasConfirmationFocus,
  hasFileChangeView,
  hasResultView,
  metadata,
  selectedTask,
  taskTree,
}: {
  activeExecutionAsk: AskRequestView | null;
  hasExecutionAskFocus: boolean;
  hasConfirmationFocus: boolean;
  hasFileChangeView: boolean;
  hasResultView: boolean;
  metadata: MainPageStateMetadata;
  selectedTask: TaskNodeCardView | undefined;
  taskTree: MainPageSnapshot["taskTree"];
}): MainPageDetailHeader {
  if (hasExecutionAskFocus && activeExecutionAsk) {
    return {
      eyebrow: "Task input",
      title: selectedTask?.title ?? "Task needs input",
      body: activeExecutionAsk.reason || activeExecutionAsk.question,
    };
  }

  if (hasConfirmationFocus || hasResultView || hasFileChangeView) {
    return metadata.detail;
  }

  if (selectedTask) {
    return {
      eyebrow: "Task",
      title: selectedTask.title,
      body: selectedTask.summary,
    };
  }

  if (taskTree) {
    return {
      eyebrow: metadata.detail.eyebrow,
      title: metadata.detail.title || taskTree.title,
      body:
        metadata.detail.body ||
        "Review or refine the generated task plan before publishing.",
    };
  }

  return metadata.detail;
}

function shouldShowExecutionAskDetail({
  activeExecutionAsk,
  isTaskPlanExplicitlySelected,
  selectedTask,
}: {
  activeExecutionAsk: AskRequestView | null;
  isTaskPlanExplicitlySelected: boolean;
  selectedTask: TaskNodeCardView | undefined;
}): boolean {
  if (!activeExecutionAsk) {
    return false;
  }

  if (isTaskPlanExplicitlySelected) {
    return false;
  }

  if (!selectedTask) {
    return true;
  }

  return (
    activeExecutionAsk.taskNodeId === selectedTask.id ||
    selectedTask.execution === "waiting_for_user"
  );
}

function inputViewFor({
  detailOverride,
  hasAuthoringAsk,
  hasConfirmationFocus,
  inputDisabled,
  metadata,
  sessionPermissions,
  selectedTask,
  taskTree,
}: {
  detailOverride: DetailOverride;
  hasAuthoringAsk: boolean;
  hasConfirmationFocus: boolean;
  inputDisabled: boolean;
  metadata: MainPageStateMetadata;
  sessionPermissions: MainPageSnapshot["permissions"];
  selectedTask: TaskNodeCardView | undefined;
  taskTree: MainPageSnapshot["taskTree"];
}): MainPageInputViewModel {
  const scope = inputScopeFor({
    detailOverride,
    hasConfirmationFocus,
    metadata,
    selectedTask,
    taskTree,
  });

  const availability = inputAvailabilityFor({
    hasAuthoringAsk,
    inputDisabled,
    selectedTask,
    sessionPermissions,
    taskTree,
  });

  if (selectedTask) {
    return {
      disabled: availability.disabled,
      disabledReason: availability.disabledReason,
      mode: "append_task_input",
      scope,
      target: "task",
      taskNodeId: selectedTask.id,
    };
  }

  return {
    disabled: availability.disabled,
    disabledReason: availability.disabledReason,
    mode: taskTree === null ? "generate_task_tree" : "append_plan_input",
    scope,
    target: taskTree === null ? "session" : "plan",
    taskNodeId: null,
  };
}

function inputAvailabilityFor({
  hasAuthoringAsk,
  inputDisabled,
  selectedTask,
  sessionPermissions,
  taskTree,
}: {
  hasAuthoringAsk: boolean;
  inputDisabled: boolean;
  selectedTask: TaskNodeCardView | undefined;
  sessionPermissions: MainPageSnapshot["permissions"];
  taskTree: MainPageSnapshot["taskTree"];
}): Pick<MainPageInputViewModel, "disabled" | "disabledReason"> {
  if (hasAuthoringAsk) {
    return {
      disabled: true,
      disabledReason: "Answer the planning questions in the main work area.",
    };
  }

  if (inputDisabled) {
    return {
      disabled: true,
      disabledReason: "Input command is submitting.",
    };
  }

  if (
    taskTree === null &&
    sessionPermissions !== undefined &&
    !sessionPermissions.canCreateTaskTree
  ) {
    return {
      disabled: true,
      disabledReason:
        sessionPermissions.readonlyReason ??
        "Creating a task plan is unavailable in the current state.",
    };
  }

  if (
    taskTree !== null &&
    sessionPermissions !== undefined &&
    !sessionPermissions.canAppendGuidance
  ) {
    return {
      disabled: true,
      disabledReason:
        sessionPermissions.readonlyReason ??
        "This session does not accept guidance in the current state.",
    };
  }

  if (selectedTask && !selectedTask.permissions.canAppendGuidance) {
    return {
      disabled: true,
      disabledReason:
        selectedTask.readonlyReason ??
        "The selected task does not accept guidance in the current state.",
    };
  }

  return {
    disabled: false,
    disabledReason: null,
  };
}

function inputScopeFor({
  detailOverride,
  hasConfirmationFocus,
  metadata,
  selectedTask,
  taskTree,
}: {
  detailOverride: DetailOverride;
  hasConfirmationFocus: boolean;
  metadata: MainPageStateMetadata;
  selectedTask: TaskNodeCardView | undefined;
  taskTree: MainPageSnapshot["taskTree"];
}): MainPageInputScopeView {
  if (hasConfirmationFocus || detailOverride !== "auto") {
    return {
      description: metadata.inputScope.description ?? null,
      label: metadata.inputScope.label,
      placeholder: metadata.inputScope.placeholder,
    };
  }

  if (selectedTask) {
    return {
      description: null,
      label: `Writing to ${taskIndexLabel(selectedTask)}`,
      placeholder: "Add guidance for this task.",
    };
  }

  if (taskTree) {
    return {
      description: null,
      label: "Writing to plan",
      placeholder: "Ask Plato to refine the overall plan.",
    };
  }

  return {
    description: metadata.inputScope.description ?? null,
    label: metadata.inputScope.label,
    placeholder: metadata.inputScope.placeholder,
  };
}

function taskIndexLabel(task: TaskNodeCardView): string {
  return `Task ${task.displayIndex ?? task.orderIndex + 1}`;
}
