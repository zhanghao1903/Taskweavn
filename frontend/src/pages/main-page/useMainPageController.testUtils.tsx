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

export function needsClarificationRuntimeInputResponse(
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
        intent: "clarification",
        scope: {
          kind: request.selection.scopeKind,
          planId: request.selection.planId ?? null,
          taskNodeId: request.selection.taskNodeId ?? null,
        },
        confidence: "high",
        sideEffect: "no_effect",
        dispatchTarget: "clarification",
        explanation: "The input is missing the WeChat message text.",
        relatedRefs: [],
      },
      outcome: {
        status: "needs_clarification",
        userMessage: "要发送给文件传输助手的消息内容是什么？没有创建发送任务。",
        recoveryActions: ["edit_input"],
        pendingClarification: {
          kind: "wechat_send",
          reasonCode: "missing_message",
          contactDisplayName: "文件传输助手",
          messageText: null,
          missingSlots: ["messageText"],
          originalContent: request.content,
        },
      },
      activity: null,
      commandResponse: null,
      inquiryResult: null,
      generatedAt: now,
    },
    error: null,
    cursor: null,
    generatedAt: now,
  };
}

export function rejectedRuntimeInputResponse(
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
        intent: "execution_request",
        scope: {
          kind: request.selection.scopeKind,
          planId: request.selection.planId ?? null,
          taskNodeId: request.selection.taskNodeId ?? null,
        },
        confidence: "high",
        sideEffect: "execution_request",
        dispatchTarget: "execution_handoff",
        explanation:
          "Input published a bounded, confirmation-gated WeChat send task through Execution Plane.",
        relatedRefs: [],
      },
      outcome: {
        status: "rejected",
        userMessage: "当前执行环境不支持微信发送能力。没有发送消息。",
        recoveryActions: ["retry_command"],
      },
      activity: {
        id: `activity-${request.commandId}`,
        sessionId: request.sessionId,
        kind: "recovery_note",
        title: "Runtime input routed",
        body: "当前执行环境不支持微信发送能力。没有发送消息。",
        occurredAt: now,
        scopeKind: request.selection.scopeKind,
        planId: request.selection.planId ?? null,
        taskNodeId: request.selection.taskNodeId ?? null,
        sideEffect: "state_effect",
        relatedRefs: [],
        sourceKind: "router",
        sourceId: `decision-${request.commandId}`,
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

export function commandRejectedRuntimeInputResponse(
  request: RuntimeInputRouteRequest,
): QueryResponse<RuntimeInputRouteResult> {
  const now = "2026-06-14T00:00:00Z";
  const message =
    "当前执行环境不支持微信发送能力。没有发送消息。 错误代码：capability_not_available 错误信息：no execution environment can satisfy the requested capability";

  return {
    requestId: `request-${request.commandId}`,
    ok: true,
    data: {
      sessionId: request.sessionId,
      decision: {
        id: `decision-${request.commandId}`,
        intent: "execution_request",
        scope: {
          kind: request.selection.scopeKind,
          planId: request.selection.planId ?? null,
          taskNodeId: request.selection.taskNodeId ?? null,
        },
        confidence: "high",
        sideEffect: "execution_request",
        dispatchTarget: "execution_handoff",
        explanation:
          "Input published a bounded, confirmation-gated WeChat send task through Execution Plane.",
        relatedRefs: [],
      },
      outcome: {
        status: "rejected",
        userMessage: message,
        recoveryActions: ["open_settings", "retry_command"],
      },
      activity: {
        id: `activity-${request.commandId}`,
        sessionId: request.sessionId,
        kind: "recovery_note",
        title: "Runtime input routed",
        body: message,
        occurredAt: now,
        scopeKind: request.selection.scopeKind,
        planId: request.selection.planId ?? null,
        taskNodeId: request.selection.taskNodeId ?? null,
        sideEffect: "state_effect",
        relatedRefs: [],
        sourceKind: "router",
        sourceId: `decision-${request.commandId}`,
        disclosureLevel: "public",
      },
      commandResponse: rejectedCommandResponse({
        commandId: request.commandId,
        message,
        recoveryActions: ["open_settings", "retry_command"],
      }),
      inquiryResult: null,
      generatedAt: now,
    },
    error: null,
    cursor: null,
    generatedAt: now,
  };
}

export function missingAccessibilityRuntimeInputResponse(
  request: RuntimeInputRouteRequest,
): QueryResponse<RuntimeInputRouteResult> {
  const response = commandRejectedRuntimeInputResponse(request);
  const message =
    "当前执行环境不支持微信发送能力。没有发送消息。 错误代码：wechat_not_ready 错误信息：macOS computer-use readiness: missing_accessibility. Plato Computer Use Helper 尚未获得辅助功能权限。";

  if (response.data === null) {
    throw new Error("runtime input test response must contain data");
  }
  return {
    ...response,
    data: {
      ...response.data,
      outcome: {
        ...response.data.outcome,
        userMessage: message,
        recoveryActions: ["open_settings", "retry_command"],
      },
      activity:
        response.data.activity === null || response.data.activity === undefined
          ? null
          : {
              ...response.data.activity,
              body: message,
            },
      commandResponse: rejectedCommandResponse({
        commandId: request.commandId,
        message,
        recoveryActions: ["open_settings", "retry_command"],
      }),
    },
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
