import { describe, expect, it } from "vitest";

import type { SessionMessageView } from "../../../shared/api/types";
import {
  createInitialPendingRuntimeState,
  mainPagePendingRuntimeReducer,
  projectPendingRuntimeActivityItems,
} from "./mainPagePendingRuntime";

describe("mainPagePendingRuntime", () => {
  it("projects local user input and understanding items immediately", () => {
    const state = mainPagePendingRuntimeReducer(
      createInitialPendingRuntimeState({
        sessionId: "session-1",
        workspaceId: "workspace-1",
      }),
      {
        body: "What is done?",
        commandId: "command-1",
        createdAt: "2026-06-26T00:00:00Z",
        scope: {
          planId: null,
          scopeKind: "session",
          taskNodeId: null,
        },
        sessionId: "session-1",
        type: "runtime_input.submit_started",
        workspaceId: "workspace-1",
      },
    );

    expect(projectPendingRuntimeActivityItems(state)).toMatchObject([
      {
        body: "What is done?",
        kind: "user_input",
        sourceId: "command-1",
        title: "User input",
      },
      {
        body: "Understanding your request...",
        kind: "router_interpretation",
        sourceId: "command-1",
        title: "Plato is understanding",
      },
    ]);
  });

  it("keeps the submitted input visible when routing fails", () => {
    const pendingState = pendingRuntimeState({ workspaceId: null });

    const failedState = mainPagePendingRuntimeReducer(pendingState, {
      commandId: "command-1",
      message: "Question routing failed. Please retry.",
      recoveryActions: [],
      type: "runtime_input.command_failed",
    });

    expect(projectPendingRuntimeActivityItems(failedState)).toMatchObject([
      {
        body: "What is done?",
        kind: "user_input",
      },
      {
        body: "Question routing failed. Please retry.",
        kind: "recovery_note",
        title: "Runtime input failed",
      },
    ]);
  });

  it("marks accepted commands without losing local feedback before reconciliation", () => {
    const acceptedState = mainPagePendingRuntimeReducer(pendingRuntimeState(), {
      commandId: "command-1",
      type: "runtime_input.command_accepted",
    });

    expect(projectPendingRuntimeActivityItems(acceptedState)).toMatchObject([
      {
        body: "What is done?",
        kind: "user_input",
      },
      {
        body: "Understanding your request...",
        kind: "router_interpretation",
      },
    ]);
  });

  it("keeps rejected input and explains the rejected state", () => {
    const rejectedState = mainPagePendingRuntimeReducer(pendingRuntimeState(), {
      commandId: "command-1",
      message: "Plato needs a clearer request.",
      recoveryActions: [],
      type: "runtime_input.command_rejected",
    });

    expect(projectPendingRuntimeActivityItems(rejectedState)).toMatchObject([
      {
        body: "What is done?",
        kind: "user_input",
      },
      {
        body: "Plato needs a clearer request.",
        kind: "recovery_note",
        title: "Runtime input rejected",
      },
    ]);
  });

  it("removes local items after command reconciliation", () => {
    const pendingState = pendingRuntimeState({ workspaceId: null });

    const reconciledState = mainPagePendingRuntimeReducer(pendingState, {
      commandId: "command-1",
      type: "runtime_input.command_reconciled",
    });

    expect(projectPendingRuntimeActivityItems(reconciledState)).toEqual([]);
  });

  it("removes only the local user item when a durable user message arrives", () => {
    const hydratedState = mainPagePendingRuntimeReducer(pendingRuntimeState(), {
      activities: [],
      messages: [
        durableMessage({
          body: "What is done?",
          id: "message-user",
          relatedCommandId: "command-1",
          title: "User input",
        }),
      ],
      sessionId: "session-1",
      type: "snapshot.hydrated",
      workspaceId: "workspace-1",
    });

    expect(projectPendingRuntimeActivityItems(hydratedState)).toMatchObject([
      {
        body: "Understanding your request...",
        kind: "router_interpretation",
      },
    ]);
  });

  it("removes only the local understanding item when a durable result arrives", () => {
    const hydratedState = mainPagePendingRuntimeReducer(pendingRuntimeState(), {
      activities: [],
      messages: [
        durableMessage({
          body: "It is complete.",
          id: "message-answer",
          relatedCommandId: "command-1",
          title: "Read-only answer",
        }),
      ],
      sessionId: "session-1",
      type: "snapshot.hydrated",
      workspaceId: "workspace-1",
    });

    expect(projectPendingRuntimeActivityItems(hydratedState)).toMatchObject([
      {
        body: "What is done?",
        kind: "user_input",
      },
    ]);
  });

  it("uses weak body and time matching only for the local user item", () => {
    const hydratedState = mainPagePendingRuntimeReducer(pendingRuntimeState(), {
      activities: [],
      messages: [
        durableMessage({
          body: "What is done?",
          id: "message-user",
          relatedCommandId: null,
          title: "Input",
        }),
      ],
      sessionId: "session-1",
      type: "snapshot.hydrated",
      workspaceId: "workspace-1",
    });

    expect(projectPendingRuntimeActivityItems(hydratedState)).toMatchObject([
      {
        body: "Understanding your request...",
        kind: "router_interpretation",
      },
    ]);
  });

  it("does not weak-match old durable messages", () => {
    const hydratedState = mainPagePendingRuntimeReducer(pendingRuntimeState(), {
      activities: [],
      messages: [
        durableMessage({
          body: "What is done?",
          createdAt: "2026-06-25T23:00:00Z",
          id: "message-user",
          relatedCommandId: null,
          title: "Input",
        }),
      ],
      sessionId: "session-1",
      type: "snapshot.hydrated",
      workspaceId: "workspace-1",
    });

    expect(projectPendingRuntimeActivityItems(hydratedState)).toHaveLength(2);
  });

  it("reconciles local pending items when durable user and result messages arrive", () => {
    const pendingState = pendingRuntimeState();

    const durableMessages = [
      durableMessage({
        body: "What is done?",
        id: "message-user",
        relatedCommandId: "command-1",
        title: "User input",
      }),
      durableMessage({
        body: "It is complete.",
        id: "message-answer",
        relatedCommandId: "command-1",
        title: "Read-only answer",
      }),
    ];

    const hydratedState = mainPagePendingRuntimeReducer(pendingState, {
      activities: [],
      messages: durableMessages,
      sessionId: "session-1",
      type: "snapshot.hydrated",
      workspaceId: "workspace-1",
    });

    expect(projectPendingRuntimeActivityItems(hydratedState)).toEqual([]);
  });

  it("does not remove failed items during snapshot hydration", () => {
    const failedState = mainPagePendingRuntimeReducer(pendingRuntimeState(), {
      commandId: "command-1",
      message: "Question routing failed. Please retry.",
      recoveryActions: [],
      type: "runtime_input.command_failed",
    });

    const hydratedState = mainPagePendingRuntimeReducer(failedState, {
      activities: [],
      messages: [
        durableMessage({
          body: "What is done?",
          id: "message-user",
          relatedCommandId: "command-1",
          title: "User input",
        }),
        durableMessage({
          body: "It is complete.",
          id: "message-answer",
          relatedCommandId: "command-1",
          title: "Read-only answer",
        }),
      ],
      sessionId: "session-1",
      type: "snapshot.hydrated",
      workspaceId: "workspace-1",
    });

    expect(projectPendingRuntimeActivityItems(hydratedState)).toHaveLength(2);
  });

  it("clears pending state when the runtime scope resets", () => {
    const resetState = mainPagePendingRuntimeReducer(pendingRuntimeState(), {
      sessionId: "session-2",
      type: "runtime.reset_scope",
      workspaceId: "workspace-1",
    });

    expect(projectPendingRuntimeActivityItems(resetState)).toEqual([]);
  });
});

function pendingRuntimeState({
  workspaceId = "workspace-1",
}: {
  workspaceId?: string | null;
} = {}) {
  return mainPagePendingRuntimeReducer(
    createInitialPendingRuntimeState({
      sessionId: "session-1",
      workspaceId,
    }),
    {
      body: "What is done?",
      commandId: "command-1",
      createdAt: "2026-06-26T00:00:00Z",
      scope: {
        planId: null,
        scopeKind: "session",
        taskNodeId: null,
      },
      sessionId: "session-1",
      type: "runtime_input.submit_started",
      workspaceId,
    },
  );
}

function durableMessage({
  body,
  createdAt = "2026-06-26T00:00:01Z",
  id,
  relatedCommandId,
  title,
}: {
  body: string;
  createdAt?: string;
  id: string;
  relatedCommandId: string | null;
  title: string;
}): SessionMessageView {
  return {
    body,
    createdAt,
    id,
    kind: "informational",
    relatedCommandId,
    sessionId: "session-1",
    taskNodeId: null,
    title,
  };
}
