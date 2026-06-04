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
} from "./mainPageUiTypes";
import type { MainPageStateMetadata } from "./runtime/adapter";

export type MainPageDetailView =
  | {
      kind: "executionAsk";
      ask: AskRequestView;
      commandError: string | null;
      header: MainPageDetailHeader;
      isAnsweringAsk: boolean;
      isCancellingAsk: boolean;
      isDeferringAsk: boolean;
      selectedTask?: TaskNodeCardView;
    }
  | {
      kind: "confirmation";
      commandError: string | null;
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
      kind: "note";
      body: string;
      header: MainPageDetailHeader;
    };

export type MainPageInputCommandMode =
  | "generate_task_tree"
  | "append_session_input"
  | "append_task_input";

export type MainPageInputViewModel = {
  disabled: boolean;
  disabledReason: string | null;
  mode: MainPageInputCommandMode;
  scope: MainPageInputScopeView;
  target: "session" | "task";
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
  fileChangeSummary: FileChangeSummaryView | null;
  isMessageScoped: boolean;
  messages: SessionMessageView[];
  result: ResultCardView | null;
  selectedTask: TaskNodeCardView | undefined;
  selectedTaskNodeId: TaskNodeId | null;
  taskTree: MainPageSnapshot["taskTree"];
  totalMessageCount: number;
  visibleMessageCount: number;
};

export type MainPageAuthoringAskViewModel = {
  asks: PlanningAskView[];
  commandError: string | null;
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
  confirmationError: string | null;
  detailOverride: DetailOverride;
  eventConnectionStatus: EventConnectionStatus;
  eventError: string | null;
  isAnsweringAuthoringAsk: boolean;
  executionAskError: string | null;
  isAnsweringAsk: boolean;
  isCancellingAsk: boolean;
  isDeferringAsk: boolean;
  inputDisabled: boolean;
  isPublishingTaskTree: boolean;
  isRetryingTask: boolean;
  isStoppingTask: boolean;
  isResolvingConfirmation: boolean;
  metadata: MainPageStateMetadata;
  selectedTaskNodeId: TaskNodeId | null;
  snapshot: MainPageSnapshot;
  taskTreeCommandError: string | null;
  uiNotice: string | null;
};

export function buildMainPageViewModel({
  auditRouteAvailable = true,
  authoringAskError,
  confirmationError,
  detailOverride,
  eventConnectionStatus,
  eventError,
  isAnsweringAuthoringAsk,
  executionAskError,
  isAnsweringAsk,
  isCancellingAsk,
  isDeferringAsk,
  inputDisabled,
  isPublishingTaskTree,
  isRetryingTask,
  isStoppingTask,
  isResolvingConfirmation,
  metadata,
  selectedTaskNodeId,
  snapshot,
  taskTreeCommandError,
  uiNotice,
}: BuildMainPageViewModelInput): MainPageViewModel {
  const nodes = snapshot.taskTree?.nodes ?? [];
  const authoringAsk = authoringAskViewFor({
    commandError: authoringAskError,
    isSubmitting: isAnsweringAuthoringAsk,
    planning: snapshot.planning,
  });
  const effectiveSelectedTaskNodeId =
    selectedTaskNodeId ?? metadata.initialSelectedTaskNodeId;
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
      fileChangeSummary,
      isMessageScoped: scopedProjection.isMessageScoped,
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
        snapshot.workflow.name,
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
      taskTreeId: snapshot.taskTree?.id ?? null,
      title:
        authoringAsk?.title ?? snapshot.taskTree?.title ?? "Start a new session",
      uiNotice,
    },
  };
}

function authoringAskViewFor({
  commandError,
  isSubmitting,
  planning,
}: {
  commandError: string | null;
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
        "Audit is unavailable in the current permission context."
      : null;

  return {
    ...route,
    disabledReason:
      permissionReason ??
      (auditRouteAvailable
        ? null
        : "Audit entry is reserved until the Audit Page UI is implemented."),
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
  executionAskError,
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
  wantsFileChangeView,
  wantsResultView,
}: {
  activeConfirmation: ConfirmationActionView | undefined;
  activeExecutionAsk: AskRequestView | null;
  commandError: string | null;
  executionAskError: string | null;
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
  wantsFileChangeView: boolean;
  wantsResultView: boolean;
}): MainPageDetailView {
  if (hasExecutionAskFocus && activeExecutionAsk) {
    return {
      kind: "executionAsk",
      ask: activeExecutionAsk,
      commandError: executionAskError,
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
}: {
  activeExecutionAsk: AskRequestView | null;
  hasExecutionAskFocus: boolean;
  hasConfirmationFocus: boolean;
  hasFileChangeView: boolean;
  hasResultView: boolean;
  metadata: MainPageStateMetadata;
  selectedTask: TaskNodeCardView | undefined;
}): MainPageDetailHeader {
  if (hasExecutionAskFocus && activeExecutionAsk) {
    return {
      eyebrow: "Execution ASK",
      title: selectedTask?.title ?? "Task needs input",
      body: activeExecutionAsk.reason || activeExecutionAsk.question,
    };
  }

  if (hasConfirmationFocus || hasResultView || hasFileChangeView) {
    return metadata.detail;
  }

  if (selectedTask) {
    return {
      eyebrow: "TaskNode",
      title: selectedTask.title,
      body: selectedTask.summary,
    };
  }

  return metadata.detail;
}

function shouldShowExecutionAskDetail({
  activeExecutionAsk,
  selectedTask,
}: {
  activeExecutionAsk: AskRequestView | null;
  selectedTask: TaskNodeCardView | undefined;
}): boolean {
  if (!activeExecutionAsk) {
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
    mode: taskTree === null ? "generate_task_tree" : "append_session_input",
    scope,
    target: "session",
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
        "Creating a TaskTree is unavailable in the current state.",
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
        "The selected TaskNode does not accept guidance in the current state.",
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
}: {
  detailOverride: DetailOverride;
  hasConfirmationFocus: boolean;
  metadata: MainPageStateMetadata;
  selectedTask: TaskNodeCardView | undefined;
}): MainPageInputScopeView {
  if (hasConfirmationFocus || detailOverride !== "auto") {
    return {
      label: metadata.inputScope.label,
      placeholder: metadata.inputScope.placeholder,
    };
  }

  if (selectedTask) {
    return {
      label: `Scope: selected task / ${selectedTask.title}`,
      placeholder: "Add guidance that only applies to this TaskNode.",
    };
  }

  return {
    label: metadata.inputScope.label,
    placeholder: metadata.inputScope.placeholder,
  };
}
