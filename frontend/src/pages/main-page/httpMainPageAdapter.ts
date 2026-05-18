import type { PlatoApi } from "../../shared/api/platoApi";
import type {
  MainPageSnapshot,
  QueryResponse,
  SessionId,
} from "../../shared/api/types";
import type { BadgeTone } from "../../shared/components";
import type { MainPageDetail, MainPageInputScope } from "./fixtures";
import type {
  MainPageAdapter,
  MainPageMockSnapshot,
  MainPageStateId,
  MainPageStateMetadata,
} from "./mockPlatoApi";

export type HttpMainPageAdapterOptions = {
  api: PlatoApi;
  liveLabel?: string;
  sessionId: SessionId;
};

export function createHttpMainPageAdapter({
  api,
  liveLabel = "Live Session",
  sessionId,
}: HttpMainPageAdapterOptions): MainPageAdapter {
  return {
    appendSessionInput(request) {
      return api.appendSessionInput(request);
    },
    appendTaskInput(nextSessionId, taskNodeId, request) {
      return api.appendTaskInput(nextSessionId, taskNodeId, request);
    },
    async loadSnapshot(stateId) {
      const response = await api.getSessionSnapshot(sessionId);
      const snapshot = unwrapSnapshot(response);

      return {
        metadata: metadataFromSnapshot(snapshot, stateId, liveLabel),
        snapshot,
      };
    },
    resolveConfirmation(nextSessionId, confirmationId, request) {
      return api.resolveConfirmation(nextSessionId, confirmationId, request);
    },
    subscribeSessionEvents(nextSessionId, cursor, onEvent) {
      return api.subscribeSessionEvents(nextSessionId, cursor, onEvent);
    },
  };
}

function unwrapSnapshot(
  response: QueryResponse<MainPageSnapshot>,
): MainPageSnapshot {
  if (!response.ok || response.data === null) {
    throw new Error(response.error?.message ?? "Unable to load session snapshot.");
  }

  return response.data;
}

function metadataFromSnapshot(
  snapshot: MainPageSnapshot,
  stateId: MainPageStateId,
  liveLabel: string,
): MainPageMockSnapshot["metadata"] {
  const selectedTaskNodeId =
    snapshot.pendingConfirmations[0]?.taskNodeId ??
    snapshot.taskTree?.nodes.find((node) =>
      ["waiting_user", "running"].includes(node.status),
    )?.id ??
    snapshot.taskTree?.nodes[0]?.id ??
    null;

  return {
    id: stateId,
    label: liveLabel,
    detail: detailFromSnapshot(snapshot, selectedTaskNodeId),
    initialSelectedTaskNodeId: selectedTaskNodeId,
    inputScope: inputScopeFromSnapshot(selectedTaskNodeId),
    topStatus: sessionStatusLabel(snapshot.session.status),
    topStatusTone: sessionStatusTone(snapshot.session.status),
  } satisfies MainPageStateMetadata;
}

function detailFromSnapshot(
  snapshot: MainPageSnapshot,
  selectedTaskNodeId: string | null,
): MainPageDetail {
  const confirmation = snapshot.pendingConfirmations[0];
  if (confirmation) {
    return {
      mode: "confirmation",
      eyebrow: "Waiting for user",
      title: confirmation.title,
      body: confirmation.body,
    };
  }

  if (snapshot.fileChangeSummary) {
    return {
      mode: "fileChanges",
      eyebrow: "File changes",
      title: "Changed files",
      body: snapshot.fileChangeSummary.summary,
    };
  }

  if (snapshot.result) {
    return {
      mode: "result",
      eyebrow: "Result",
      title: snapshot.result.title,
      body: snapshot.result.summary,
    };
  }

  if (selectedTaskNodeId !== null) {
    const selectedTask = snapshot.taskTree?.nodes.find(
      (node) => node.id === selectedTaskNodeId,
    );

    return {
      mode: "task",
      eyebrow: "Task",
      title: selectedTask?.title ?? "Selected task",
      body: selectedTask?.summary ?? "Review or refine the selected task.",
    };
  }

  if (snapshot.taskTree) {
    return {
      mode: "session",
      eyebrow: "Session",
      title: snapshot.taskTree.title,
      body: "Review the generated TaskTree before execution continues.",
    };
  }

  return {
    mode: "workflow",
    eyebrow: "Workflow",
    title: snapshot.workflow.name,
    body:
      snapshot.workflow.inputHint ??
      "Describe the goal you want Plato to turn into a TaskTree.",
  };
}

function inputScopeFromSnapshot(
  selectedTaskNodeId: string | null,
): MainPageInputScope {
  if (selectedTaskNodeId !== null) {
    return {
      label: "Scope: selected task",
      placeholder: "Add guidance, constraints, or clarification for this task.",
    };
  }

  return {
    label: "Scope: session",
    placeholder: "Describe the goal or add guidance for this session.",
  };
}

function sessionStatusLabel(status: MainPageSnapshot["session"]["status"]): string {
  const labels: Record<MainPageSnapshot["session"]["status"], string> = {
    completed: "Completed",
    draft_ready: "Draft ready",
    failed: "Failed",
    new: "New session",
    running: "Running",
    understanding: "Understanding",
    waiting_user: "Waiting for user",
  };

  return labels[status];
}

function sessionStatusTone(status: MainPageSnapshot["session"]["status"]): BadgeTone {
  const tones: Record<MainPageSnapshot["session"]["status"], BadgeTone> = {
    completed: "success",
    draft_ready: "blue",
    failed: "danger",
    new: "neutral",
    running: "blue",
    understanding: "blue",
    waiting_user: "warning",
  };

  return tones[status];
}
