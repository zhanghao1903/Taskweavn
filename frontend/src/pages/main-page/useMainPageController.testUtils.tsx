import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import type { ReactNode } from "react";

import type {
  CommandResponse,
  QueryResponse,
  RuntimeInputRouteRequest,
  RuntimeInputRouteResult,
} from "../../shared/api/types";
import type {
  LoadMainPageSnapshot,
  MainPageAdapter,
} from "./runtime/adapter";
import type { MainPageStateId } from "./mockPlatoApi";
import {
  createMainPageMockAdapter,
  getMainPageMockSnapshot,
} from "./mockPlatoApi";
import { useMainPageController } from "./useMainPageController";

export function renderMainPageController({
  adapter = testAdapter(),
  initialStateId = "s3-draft-ready",
  initialTaskNodeId = null,
}: {
  adapter?: MainPageAdapter;
  initialStateId?: MainPageStateId;
  initialTaskNodeId?: string | null;
}) {
  return renderHook(
    () =>
      useMainPageController({
        adapter,
        initialStateId,
        initialTaskNodeId,
      }),
    {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={createTestQueryClient()}>
          {children}
        </QueryClientProvider>
      ),
    },
  );
}

export const loadImmediateSnapshot: LoadMainPageSnapshot = async (stateId) =>
  getMainPageMockSnapshot(stateId as MainPageStateId);

export function testAdapter(
  overrides: Partial<MainPageAdapter> = {},
): MainPageAdapter {
  return createMainPageMockAdapter({
    loadSnapshot: loadImmediateSnapshot,
    ...overrides,
  });
}

export function acceptedCommandResponse({
  commandId,
  taskNodeId,
}: {
  commandId: string;
  sessionId: string;
  taskNodeId?: string;
}): CommandResponse {
  return {
    requestId: `request-${commandId}`,
    ok: true,
    result: {
      commandId,
      status: "accepted",
      message: "accepted",
      affectedTaskRefs: taskNodeId
        ? [{ kind: "published", id: taskNodeId }]
        : [],
      objectRefs: [],
      affectedObjects: [],
      emittedMessageIds: [],
      publishedTaskIds: taskNodeId ? [`retry-${taskNodeId}`] : [],
      debugRefs: {},
    },
    error: null,
    refresh: {
      waitForEvents: false,
      suggestedQueries: ["session.snapshot"],
      affectedTaskRefs: taskNodeId
        ? [{ kind: "published", id: taskNodeId }]
        : [],
      affectedScopes: [],
    },
  };
}

export function rejectedCommandResponse({
  commandId,
  message,
  recoveryActions = [],
}: {
  commandId: string;
  message: string;
  recoveryActions?: string[];
}): CommandResponse {
  return {
    requestId: `request-${commandId}`,
    ok: false,
    result: {
      commandId,
      status: "rejected",
      message,
      affectedTaskRefs: [],
      objectRefs: [],
      affectedObjects: [],
      emittedMessageIds: [],
      publishedTaskIds: [],
      debugRefs: {},
    },
    error: {
      code: "command_rejected",
      details: {
        recoveryActions,
      },
      message,
      retryable: false,
    },
    refresh: {
      waitForEvents: false,
      suggestedQueries: ["session.snapshot", "asks", "task.tree", "task.detail"],
      affectedTaskRefs: [],
      affectedScopes: [],
    },
  };
}

export function answeredRuntimeInputResponse(
  request: RuntimeInputRouteRequest,
): QueryResponse<RuntimeInputRouteResult> {
  const now = "2026-06-14T00:00:00Z";

  return {
    requestId: `request-${request.commandId}`,
    ok: true,
    data: {
      sessionId: request.sessionId,
      decision: {
        id: `decision-${request.commandId}`,
        intent: "question",
        scope: {
          kind: request.selection.scopeKind,
          planId: request.selection.planId ?? null,
          taskNodeId: request.selection.taskNodeId ?? null,
        },
        confidence: "high",
        sideEffect: "no_effect",
        dispatchTarget: "read_only_inquiry",
        explanation: "The input was routed as a read-only question.",
        relatedRefs: [],
      },
      outcome: {
        status: "answered",
        userMessage: "Read-only answer ready.",
        recoveryActions: [],
      },
      activity: {
        id: `activity-${request.commandId}`,
        sessionId: request.sessionId,
        kind: "answer",
        title: "Read-only answer",
        body: "The task is still a draft. No state changed.",
        occurredAt: now,
        scopeKind: request.selection.scopeKind,
        planId: request.selection.planId ?? null,
        taskNodeId: request.selection.taskNodeId ?? null,
        sideEffect: "no_effect",
        relatedRefs: [],
        sourceKind: "router",
        disclosureLevel: "public",
      },
      commandResponse: null,
      inquiryResult: {
        inquiryId: request.commandId,
        sessionId: request.sessionId,
        scope: {
          kind: request.selection.scopeKind,
          planId: request.selection.planId ?? null,
          taskNodeId: request.selection.taskNodeId ?? null,
        },
        status: "answered",
        answer: {
          title: "Read-only answer",
          body: "The task is still a draft. No state changed.",
          confidence: "high",
        },
        evidenceRefs: [
          {
            kind: "task_status",
            refId: "task:task-visual-direction:status",
            label: "Task status",
            disclosure: "public",
            truncated: false,
          },
        ],
        warnings: [],
        activity: null,
        generatedAt: now,
      },
      generatedAt: now,
    },
    error: null,
    cursor: null,
    generatedAt: now,
  };
}

export function dispatchedRuntimeInputResponse(
  request: RuntimeInputRouteRequest,
): QueryResponse<RuntimeInputRouteResult> {
  const now = "2026-06-14T00:00:00Z";

  return {
    requestId: `request-${request.commandId}`,
    ok: true,
    data: {
      sessionId: request.sessionId,
      decision: {
        id: `decision-${request.commandId}`,
        intent: "guidance",
        scope: {
          kind: request.selection.scopeKind,
          planId: request.selection.planId ?? null,
          taskNodeId: request.selection.taskNodeId ?? null,
        },
        confidence: "high",
        sideEffect: "context_effect",
        dispatchTarget: "record_guidance",
        explanation: "Input recorded guidance as typed contract context.",
        relatedRefs: [],
      },
      outcome: {
        status: "dispatched",
        userMessage: "Guidance was recorded.",
        recoveryActions: [],
      },
      activity: {
        id: `activity-${request.commandId}`,
        sessionId: request.sessionId,
        kind: "guidance_recorded",
        title: "Guidance recorded",
        body: "Guidance was recorded.",
        occurredAt: now,
        scopeKind: request.selection.scopeKind,
        planId: request.selection.planId ?? null,
        taskNodeId: request.selection.taskNodeId ?? null,
        sideEffect: "context_effect",
        relatedRefs: [],
        sourceKind: "router",
        disclosureLevel: "public",
      },
      commandResponse: null,
      inquiryResult: null,
      generatedAt: now,
    },
    error: null,
    cursor: null,
    generatedAt: now,
  };
}

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}
