import type {
  ConfirmationActionView,
  FileChangeSummaryView,
  MainPageSnapshot,
  ResultCardView,
  SessionMessageView,
  SessionSummary,
  TaskNodeCardView,
  TaskNodeId,
} from "../../shared/api/types";
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
  eventError: string | null;
  isPublishingTaskTree: boolean;
  showPublishTaskTree: boolean;
  taskTreeCommandError: string | null;
  taskTreeId: string | null;
  title: string;
  uiNotice: string | null;
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

export type MainPageViewModel = {
  detail: MainPageDetailView;
  input: MainPageInputViewModel;
  sessionId: string;
  sidebar: MainPageSidebarViewModel;
  taskWorkspace: MainPageTaskWorkspaceViewModel;
  topBar: MainPageTopBarViewModel;
  workspace: MainPageWorkspaceViewModel;
};

export type BuildMainPageViewModelInput = {
  confirmationError: string | null;
  detailOverride: DetailOverride;
  eventConnectionStatus: EventConnectionStatus;
  eventError: string | null;
  inputDisabled: boolean;
  isPublishingTaskTree: boolean;
  isResolvingConfirmation: boolean;
  metadata: MainPageStateMetadata;
  selectedTaskNodeId: TaskNodeId | null;
  snapshot: MainPageSnapshot;
  taskTreeCommandError: string | null;
  uiNotice: string | null;
};

export function buildMainPageViewModel({
  confirmationError,
  detailOverride,
  eventConnectionStatus,
  eventError,
  inputDisabled,
  isPublishingTaskTree,
  isResolvingConfirmation,
  metadata,
  selectedTaskNodeId,
  snapshot,
  taskTreeCommandError,
  uiNotice,
}: BuildMainPageViewModelInput): MainPageViewModel {
  const nodes = snapshot.taskTree?.nodes ?? [];
  const effectiveSelectedTaskNodeId =
    selectedTaskNodeId ?? metadata.initialSelectedTaskNodeId;
  const activeConfirmation =
    snapshot.pendingConfirmations.find(
      (confirmation) => confirmation.taskNodeId === effectiveSelectedTaskNodeId,
    ) ?? snapshot.pendingConfirmations[0];
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
  const header = detailHeaderFor({
    hasConfirmationFocus,
    hasFileChangeView: wantsFileChangeView && fileChangeSummary !== null,
    hasResultView: wantsResultView && result !== null,
    metadata,
    selectedTask,
  });
  const input = inputViewFor({
    sessionPermissions: snapshot.permissions,
    inputDisabled,
    metadata,
    selectedTask,
    hasConfirmationFocus,
    detailOverride,
    taskTree: snapshot.taskTree,
  });

  return {
    detail: detailViewFor({
      activeConfirmation,
      commandError: confirmationError,
      fileChangeSummary,
      hasConfirmationFocus,
      header,
      isResolvingConfirmation,
      result,
      selectedTask,
      wantsFileChangeView,
      wantsResultView,
    }),
    input,
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
      eventError,
      isPublishingTaskTree,
      showPublishTaskTree: snapshot.taskTree?.status === "draft",
      taskTreeCommandError,
      taskTreeId: snapshot.taskTree?.id ?? null,
      title: snapshot.taskTree?.title ?? "Start a new session",
      uiNotice,
    },
  };
}

function detailViewFor({
  activeConfirmation,
  commandError,
  fileChangeSummary,
  hasConfirmationFocus,
  header,
  isResolvingConfirmation,
  result,
  selectedTask,
  wantsFileChangeView,
  wantsResultView,
}: {
  activeConfirmation: ConfirmationActionView | undefined;
  commandError: string | null;
  fileChangeSummary: FileChangeSummaryView | null;
  hasConfirmationFocus: boolean;
  header: MainPageDetailHeader;
  isResolvingConfirmation: boolean;
  result: ResultCardView | null;
  selectedTask: TaskNodeCardView | undefined;
  wantsFileChangeView: boolean;
  wantsResultView: boolean;
}): MainPageDetailView {
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
  hasConfirmationFocus,
  hasFileChangeView,
  hasResultView,
  metadata,
  selectedTask,
}: {
  hasConfirmationFocus: boolean;
  hasFileChangeView: boolean;
  hasResultView: boolean;
  metadata: MainPageStateMetadata;
  selectedTask: TaskNodeCardView | undefined;
}): MainPageDetailHeader {
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

function inputViewFor({
  detailOverride,
  hasConfirmationFocus,
  inputDisabled,
  metadata,
  sessionPermissions,
  selectedTask,
  taskTree,
}: {
  detailOverride: DetailOverride;
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
  inputDisabled,
  selectedTask,
  sessionPermissions,
  taskTree,
}: {
  inputDisabled: boolean;
  selectedTask: TaskNodeCardView | undefined;
  sessionPermissions: MainPageSnapshot["permissions"];
  taskTree: MainPageSnapshot["taskTree"];
}): Pick<MainPageInputViewModel, "disabled" | "disabledReason"> {
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
