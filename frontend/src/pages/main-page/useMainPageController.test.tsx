import { act, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  QueryResponse,
  RuntimeInputRouteRequest,
  RuntimeInputRouteResult,
} from "../../shared/api/types";
import type {
  AppendSessionInputCommand,
  AppendTaskInputCommand,
  AnswerAuthoringAskBatchCommand,
  AnswerAskCommand,
  ArchivePlanCommand,
  CancelAskCommand,
  DeferAskCommand,
  GenerateTaskTreeCommand,
  LoadMainPageSnapshot,
  RepairAuthoringStateCommand,
  RouteRuntimeInputCommand,
  RetryTaskCommand,
  StopTaskCommand,
  SubscribeSessionEvents,
} from "./runtime/adapter";
import {
  acceptedCommandResponse,
  answeredRuntimeInputResponse,
  commandRejectedRuntimeInputResponse,
  dispatchedRuntimeInputResponse,
  loadImmediateSnapshot,
  needsClarificationRuntimeInputResponse,
  rejectedCommandResponse,
  rejectedRuntimeInputResponse,
  renderMainPageController,
  testAdapter,
} from "./useMainPageController.testUtils";

describe("useMainPageController", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the initial runtime snapshot and subscribes to the session event stream", async () => {
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);
    const subscribeSessionEvents = vi.fn<SubscribeSessionEvents>(() => () => {
      // No-op unsubscribe for the controller boundary test.
    });

    const { result } = renderMainPageController({
      adapter: testAdapter({
        loadSnapshot,
        subscribeSessionEvents,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    expect(result.current.stateId).toBe("s3-draft-ready");
    expect(result.current.eventConnectionStatus).toBe("connected");
    expect(loadSnapshot).toHaveBeenCalledWith("s3-draft-ready", null, null);
    expect(subscribeSessionEvents).toHaveBeenCalledWith(
      "session-website-plan",
      "cursor-s3-draft-ready",
      expect.any(Function),
      null,
    );
  });

  it("uses a route task target once when the initial snapshot contains it", async () => {
    const { result } = renderMainPageController({
      initialStateId: "s3-draft-ready",
      initialTaskNodeId: "task-visual-direction",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    await waitFor(() => {
      expect(result.current.selectedTaskNodeId).toBe("task-visual-direction");
    });
  });

  it("resets local coordination state when switching fixture states", async () => {
    const { result } = renderMainPageController({
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.selectTask("task-visual-direction");
      result.current.actions.showResult();
      result.current.actions.changeInputDraft("temporary guidance");
    });

    expect(result.current.selectedTaskNodeId).toBe("task-visual-direction");
    expect(result.current.selectionTarget).toBe("task");
    expect(result.current.detailOverride).toBe("result");
    expect(result.current.inputDraft).toBe("temporary guidance");

    act(() => {
      result.current.actions.selectTaskPlan();
    });

    expect(result.current.selectedTaskNodeId).toBe(null);
    expect(result.current.selectionTarget).toBe("plan");

    act(() => {
      result.current.actions.changeState("s9-file-changes");
    });

    expect(result.current.stateId).toBe("s9-file-changes");
    expect(result.current.selectedTaskNodeId).toBe(null);
    expect(result.current.selectionTarget).toBe("auto");
    expect(result.current.detailOverride).toBe("auto");
    expect(result.current.inputDraft).toBe("");
    expect(result.current.inputError).toBe(null);
    expect(result.current.taskTreeCommandError).toBe(null);
  });

  it("routes read-only questions through Runtime Input Router without mutating input commands", async () => {
    const routeRuntimeInput = vi.fn<RouteRuntimeInputCommand>(
      async (request) => answeredRuntimeInputResponse(request),
    );
    const appendSessionInput = vi.fn<AppendSessionInputCommand>(
      async (request) =>
        acceptedCommandResponse({
          commandId: request.commandId,
          sessionId: request.sessionId,
        }),
    );
    const appendTaskInput = vi.fn<AppendTaskInputCommand>(
      async (sessionId, taskNodeId, request) =>
        acceptedCommandResponse({
          commandId: request.commandId,
          sessionId,
          taskNodeId,
        }),
    );
    const generateTaskTree = vi.fn<GenerateTaskTreeCommand>(
      async (request) =>
        acceptedCommandResponse({
          commandId: request.commandId,
          sessionId: request.sessionId,
        }),
    );

    const { result } = renderMainPageController({
      adapter: testAdapter({
        appendSessionInput,
        appendTaskInput,
        generateTaskTree,
        routeRuntimeInput,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.changeInputDraft("What is this task doing?");
    });
    act(() => {
      result.current.actions.submitInput({
        mode: "append_task_input",
        sessionId: "session-website-plan",
        target: "task",
        taskNodeId: "task-visual-direction",
      });
    });

    await waitFor(() => {
      expect(routeRuntimeInput).toHaveBeenCalledWith(
        expect.objectContaining({
          content: "What is this task doing?",
          mode: "ask",
          selection: expect.objectContaining({
            scopeKind: "task",
            taskNodeId: "task-visual-direction",
          }),
          sessionId: "session-website-plan",
        }),
        null,
      );
    });

    expect(appendSessionInput).not.toHaveBeenCalled();
    expect(appendTaskInput).not.toHaveBeenCalled();
    expect(generateTaskTree).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(result.current.uiNotice).toContain("Read-only answer");
    });
    expect(result.current.runtimeActivityItems).toHaveLength(2);
    expect(result.current.runtimeActivityItems[0]).toMatchObject({
      body: "What is this task doing?",
      kind: "user_input",
      sideEffect: "context_effect",
      sourceKind: "router",
      taskNodeId: "task-visual-direction",
      title: "User input",
    });
    expect(result.current.runtimeActivityItems[1]).toMatchObject({
      kind: "answer",
      sideEffect: "no_effect",
      sourceKind: "router",
      taskNodeId: "task-visual-direction",
    });
    expect(result.current.inputDraft).toBe("");
    expect(result.current.inputError).toBe(null);
  });

  it("exposes the pending runtime ASK mode while routing a read-only question", async () => {
    let capturedRequest: RuntimeInputRouteRequest | null = null;
    let resolveRoute:
      | ((response: QueryResponse<RuntimeInputRouteResult>) => void)
      | null = null;
    const routeRuntimeInput = vi.fn<RouteRuntimeInputCommand>((request) => {
      capturedRequest = request;
      return new Promise((resolve) => {
        resolveRoute = resolve;
      });
    });

    const { result } = renderMainPageController({
      adapter: testAdapter({
        routeRuntimeInput,
      }),
      initialStateId: "s1-empty",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s1-empty");
    });

    act(() => {
      result.current.actions.changeInputDraft("明天世界杯有哪些比赛？");
    });
    act(() => {
      result.current.actions.submitInput({
        mode: "generate_task_tree",
        sessionId: "session-website-plan",
        target: "session",
        taskNodeId: null,
      });
    });

    await waitFor(() => {
      expect(routeRuntimeInput).toHaveBeenCalledTimes(1);
    });
    expect(result.current.activeRuntimeInputMode).toBe("ask");
    expect(result.current.inputDraft).toBe("");
    expect(result.current.runtimeActivityItems).toHaveLength(2);
    expect(result.current.runtimeActivityItems[0]).toMatchObject({
      body: "明天世界杯有哪些比赛？",
      kind: "user_input",
      sourceKind: "router",
      title: "User input",
    });
    expect(result.current.runtimeActivityItems[1]).toMatchObject({
      body: "Understanding your request...",
      kind: "router_interpretation",
      sourceKind: "router",
      title: "Plato is understanding",
    });

    const request = capturedRequest;
    if (!request) {
      throw new Error("Runtime input request was not captured.");
    }
    const response = answeredRuntimeInputResponse(request);

    act(() => {
      if (resolveRoute === null) {
        throw new Error("Runtime input resolver was not captured.");
      }
      resolveRoute(response);
    });

    await waitFor(() => {
      expect(result.current.activeRuntimeInputMode).toBe(null);
    });
  });

  it("routes task guidance through Runtime Input Router by default", async () => {
    const routeRuntimeInput = vi.fn<RouteRuntimeInputCommand>(
      async (request) => dispatchedRuntimeInputResponse(request),
    );
    const appendTaskInput = vi.fn<AppendTaskInputCommand>(
      async (sessionId, taskNodeId, request) =>
        acceptedCommandResponse({
          commandId: request.commandId,
          sessionId,
          taskNodeId,
        }),
    );

    const { result } = renderMainPageController({
      adapter: testAdapter({
        appendTaskInput,
        routeRuntimeInput,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.changeInputDraft("Keep this implementation small.");
    });
    act(() => {
      result.current.actions.submitInput({
        mode: "append_task_input",
        sessionId: "session-website-plan",
        target: "task",
        taskNodeId: "task-visual-direction",
      });
    });

    await waitFor(() => {
      expect(routeRuntimeInput).toHaveBeenCalledWith(
        expect.objectContaining({
          content: "Keep this implementation small.",
          mode: "guide",
          selection: expect.objectContaining({
            scopeKind: "task",
            taskNodeId: "task-visual-direction",
          }),
          sessionId: "session-website-plan",
        }),
        null,
      );
    });

    expect(appendTaskInput).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(result.current.uiNotice).toBe("Guidance was recorded.");
    });
    expect(result.current.inputDraft).toBe("");
    expect(result.current.inputError).toBe(null);
  });

  it("keeps pending runtime clarification and sends it with the follow-up input", async () => {
    let routeCallCount = 0;
    const routeRuntimeInput = vi.fn<RouteRuntimeInputCommand>(
      async (request) => {
        routeCallCount += 1;
        return routeCallCount === 1
          ? needsClarificationRuntimeInputResponse(request)
          : dispatchedRuntimeInputResponse(request);
      },
    );

    const { result } = renderMainPageController({
      adapter: testAdapter({
        routeRuntimeInput,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.changeInputDraft("给微信文件传输助手发消息");
    });
    act(() => {
      result.current.actions.submitInput({
        mode: "append_session_input",
        sessionId: "session-website-plan",
        target: "session",
        taskNodeId: null,
      });
    });

    await waitFor(() => {
      expect(result.current.inputError).toBe(
        "要发送给文件传输助手的消息内容是什么？没有创建发送任务。",
      );
    });

    act(() => {
      result.current.actions.changeInputDraft("Plato 补全消息");
    });
    act(() => {
      result.current.actions.submitInput({
        mode: "append_session_input",
        sessionId: "session-website-plan",
        target: "session",
        taskNodeId: null,
      });
    });

    await waitFor(() => {
      expect(routeRuntimeInput).toHaveBeenCalledTimes(2);
    });
    expect(routeRuntimeInput.mock.calls[1]?.[0]).toMatchObject({
      clientState: {
        pendingClarification: {
          contactDisplayName: "文件传输助手",
          kind: "wechat_send",
          missingSlots: ["messageText"],
        },
      },
      content: "Plato 补全消息",
    });
    await waitFor(() => {
      expect(result.current.uiNotice).toBe("Guidance was recorded.");
    });
    expect(result.current.inputError).toBe(null);
  });

  it("surfaces rejected runtime input as conversation-visible Router reply", async () => {
    const routeRuntimeInput = vi.fn<RouteRuntimeInputCommand>(
      async (request) => rejectedRuntimeInputResponse(request),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    const { result } = renderMainPageController({
      adapter: testAdapter({
        loadSnapshot,
        routeRuntimeInput,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.changeInputDraft("给微信的文件传输助手发送“你好”");
    });
    act(() => {
      result.current.actions.submitInput({
        mode: "append_session_input",
        sessionId: "session-website-plan",
        target: "session",
        taskNodeId: null,
      });
    });

    await waitFor(() => {
      expect(result.current.inputError).toBe(
        "当前执行环境不支持微信发送能力。没有发送消息。",
      );
    });
    expect(result.current.inputDraft).toBe("");

    expect(result.current.runtimeActivityItems).toMatchObject([
      {
        body: "给微信的文件传输助手发送“你好”",
        kind: "user_input",
        title: "User input",
      },
      {
        body: expect.stringContaining("建议的恢复操作"),
        kind: "recovery_note",
        sourceId: expect.stringContaining("decision-route-input-"),
        title: "Router reply",
      },
      {
        body: "当前执行环境不支持微信发送能力。没有发送消息。",
        kind: "recovery_note",
        title: "Runtime input routed",
      },
    ]);
    expect(result.current.runtimeActivityItems[1]?.body).toContain(
      "解决问题后再次运行命令。",
    );
    expect(result.current.inputRecoveryActions).toEqual(["retry_command"]);
    expect(loadSnapshot).toHaveBeenCalledTimes(2);
  });

  it("keeps command-response rejections visible as user input and Router reply", async () => {
    const routeRuntimeInput = vi.fn<RouteRuntimeInputCommand>(
      async (request) => commandRejectedRuntimeInputResponse(request),
    );

    const { result } = renderMainPageController({
      adapter: testAdapter({
        routeRuntimeInput,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.changeInputDraft("给微信的文件传输助手发送“你好”");
    });
    act(() => {
      result.current.actions.submitInput({
        mode: "append_session_input",
        sessionId: "session-website-plan",
        target: "session",
        taskNodeId: null,
      });
    });

    await waitFor(() => {
      expect(result.current.inputError).toContain("capability_not_available");
    });

    expect(result.current.runtimeActivityItems).toMatchObject([
      {
        body: "给微信的文件传输助手发送“你好”",
        kind: "user_input",
        title: "User input",
      },
      {
        body: expect.stringContaining("当前执行环境不支持微信发送能力"),
        kind: "recovery_note",
        title: "Router reply",
      },
      {
        body: expect.stringContaining("当前执行环境不支持微信发送能力"),
        kind: "recovery_note",
        title: "Runtime input routed",
      },
    ]);
    expect(result.current.inputRecoveryActions).toEqual([
      "open_settings",
      "retry_command",
    ]);
  });

  it("submits a manual retry command for the selected failed task", async () => {
    const retryTask = vi.fn<RetryTaskCommand>(async (sessionId, taskNodeId, request) =>
      acceptedCommandResponse({
        commandId: request.commandId,
        sessionId,
        taskNodeId,
      }),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    const { result } = renderMainPageController({
      adapter: testAdapter({
        loadSnapshot,
        retryTask,
      }),
      initialStateId: "s13-command-failed",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe(
        "s13-command-failed",
      );
    });

    act(() => {
      result.current.actions.retryTask({
        sessionId: "session-website-plan",
        taskNodeId: "task-implementation",
      });
    });

    await waitFor(() => {
      expect(retryTask).toHaveBeenCalledWith(
        "session-website-plan",
        "task-implementation",
        expect.objectContaining({
          sessionId: "session-website-plan",
          payload: { startImmediately: true },
        }),
        null,
      );
    });
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });

    expect(result.current.taskTreeCommandError).toBe(null);
  });

  it("submits a stop command for an active task", async () => {
    const stopTask = vi.fn<StopTaskCommand>(async (sessionId, taskNodeId, request) =>
      acceptedCommandResponse({
        commandId: request.commandId,
        sessionId,
        taskNodeId,
      }),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    const { result } = renderMainPageController({
      adapter: testAdapter({
        loadSnapshot,
        stopTask,
      }),
      initialStateId: "s6-running",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s6-running");
    });

    act(() => {
      result.current.actions.stopTask({
        sessionId: "session-website-plan",
        taskNodeId: "task-implementation",
      });
    });

    await waitFor(() => {
      expect(stopTask).toHaveBeenCalledWith(
        "session-website-plan",
        "task-implementation",
        expect.objectContaining({
          sessionId: "session-website-plan",
          payload: { reason: "user requested stop" },
        }),
        null,
      );
    });
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });

    expect(result.current.taskTreeCommandError).toBe(null);
    expect(result.current.uiNotice).toBe("Stop requested.");
  });

  it("submits an archive plan command and refetches the session projection", async () => {
    const archivePlan = vi.fn<ArchivePlanCommand>(
      async (sessionId, _planId, request) =>
        acceptedCommandResponse({
          commandId: request.commandId,
          sessionId,
        }),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    const { result } = renderMainPageController({
      adapter: testAdapter({
        archivePlan,
        loadSnapshot,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.archivePlan({
        expectedVersion: 7,
        planId: "plan-website",
        sessionId: "session-website-plan",
      });
    });

    await waitFor(() => {
      expect(archivePlan).toHaveBeenCalledWith(
        "session-website-plan",
        "plan-website",
        expect.objectContaining({
          expectedVersion: 7,
          sessionId: "session-website-plan",
          payload: {
            reason: "user requested archive",
          },
        }),
        null,
      );
    });
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });

    expect(result.current.taskTreeCommandError).toBe(null);
    expect(result.current.uiNotice).toBe("Plan archived.");
  });

  it("submits authoring ASK answers as one batch and refetches projection", async () => {
    const answerAuthoringAskBatch = vi.fn<AnswerAuthoringAskBatchCommand>(
      async (sessionId, _rawTaskId, request) =>
        acceptedCommandResponse({
          commandId: request.commandId,
          sessionId,
        }),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    const { result } = renderMainPageController({
      adapter: testAdapter({
        answerAuthoringAskBatch,
        loadSnapshot,
      }),
      initialStateId: "s2-understanding",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s2-understanding");
    });

    act(() => {
      result.current.actions.answerAuthoringAskBatch({
        answers: [
          { askId: "authoring-ask-site-type", value: "portfolio" },
          { askId: "authoring-ask-style", value: "quiet_editorial" },
        ],
        rawTaskId: "raw-task-website-goal",
        sessionId: "session-website-plan",
      });
    });

    await waitFor(() => {
      expect(answerAuthoringAskBatch).toHaveBeenCalledWith(
        "session-website-plan",
        "raw-task-website-goal",
        expect.objectContaining({
          sessionId: "session-website-plan",
          payload: {
            answers: [
              { askId: "authoring-ask-site-type", value: "portfolio" },
              { askId: "authoring-ask-style", value: "quiet_editorial" },
            ],
          },
        }),
        null,
      );
    });
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });

    expect(result.current.authoringAskError).toBe(null);
    expect(result.current.uiNotice).toBe("Authoring answers submitted.");
  });

  it("repairs dirty authoring state and refetches projection", async () => {
    const repairAuthoringState = vi.fn<RepairAuthoringStateCommand>(
      async (request) =>
        acceptedCommandResponse({
          commandId: request.commandId,
          sessionId: request.sessionId,
        }),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    const { result } = renderMainPageController({
      adapter: testAdapter({
        loadSnapshot,
        repairAuthoringState,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.repairAuthoringState({
        sessionId: "session-website-plan",
      });
    });

    await waitFor(() => {
      expect(repairAuthoringState).toHaveBeenCalledWith(
        expect.objectContaining({
          sessionId: "session-website-plan",
          payload: {
            reason: "dirty_authoring_state",
          },
        }),
        null,
      );
    });
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });

    expect(result.current.taskTreeCommandError).toBe(null);
    expect(result.current.uiNotice).toBe("Authoring state repaired.");
  });

  it("answers an execution ASK through its concrete ask id", async () => {
    const answerAsk = vi.fn<AnswerAskCommand>(
      async (sessionId, _askId, request) =>
        acceptedCommandResponse({
          commandId: request.commandId,
          sessionId,
        }),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    const { result } = renderMainPageController({
      adapter: testAdapter({
        answerAsk,
        loadSnapshot,
      }),
      initialStateId: "s14-execution-ask",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s14-execution-ask");
    });

    act(() => {
      result.current.actions.answerAsk({
        askId: "ask-deployment-target",
        selectedOptionIds: ["vercel"],
        sessionId: "session-website-plan",
        text: null,
      });
    });

    await waitFor(() => {
      expect(answerAsk).toHaveBeenCalledWith(
        "session-website-plan",
        "ask-deployment-target",
        expect.objectContaining({
          sessionId: "session-website-plan",
          payload: {
            selectedOptionIds: ["vercel"],
            text: null,
          },
        }),
        null,
      );
    });
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });

    expect(result.current.executionAskError).toBe(null);
    expect(result.current.uiNotice).toBe("Answer submitted.");
  });

  it("refetches after a rejected execution ASK answer with refresh hints", async () => {
    const answerAsk = vi.fn<AnswerAskCommand>(
      async (_sessionId, _askId, request) =>
        rejectedCommandResponse({
          commandId: request.commandId,
          message: "Choose an option or enter text, not both.",
          recoveryActions: ["answer_ask", "refresh_snapshot"],
        }),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    const { result } = renderMainPageController({
      adapter: testAdapter({
        answerAsk,
        loadSnapshot,
      }),
      initialStateId: "s14-execution-ask",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s14-execution-ask");
    });

    act(() => {
      result.current.actions.answerAsk({
        askId: "ask-deployment-target",
        selectedOptionIds: ["vercel"],
        sessionId: "session-website-plan",
        text: null,
      });
    });

    await waitFor(() => {
      expect(result.current.executionAskError).toBe(
        "Choose an option or enter text, not both.",
      );
    });
    expect(result.current.executionAskRecoveryActions).toEqual([
      "answer_ask",
      "refresh_snapshot",
    ]);
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });
  });

  it("defer and cancel execution ASK commands target the concrete ask id", async () => {
    const deferAsk = vi.fn<DeferAskCommand>(
      async (sessionId, _askId, request) =>
        acceptedCommandResponse({
          commandId: request.commandId,
          sessionId,
        }),
    );
    const cancelAsk = vi.fn<CancelAskCommand>(
      async (sessionId, _askId, request) =>
        acceptedCommandResponse({
          commandId: request.commandId,
          sessionId,
        }),
    );
    const { result } = renderMainPageController({
      adapter: testAdapter({
        cancelAsk,
        deferAsk,
      }),
      initialStateId: "s14-execution-ask",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s14-execution-ask");
    });

    act(() => {
      result.current.actions.deferAsk({
        askId: "ask-deployment-target",
        reason: "user deferred ASK",
        sessionId: "session-website-plan",
      });
    });

    await waitFor(() => {
      expect(deferAsk).toHaveBeenCalledWith(
        "session-website-plan",
        "ask-deployment-target",
        expect.objectContaining({
          payload: {
            reason: "user deferred ASK",
          },
        }),
        null,
      );
    });

    act(() => {
      result.current.actions.cancelAsk({
        askId: "ask-deployment-target",
        reason: "user cancelled ASK",
        sessionId: "session-website-plan",
      });
    });

    await waitFor(() => {
      expect(cancelAsk).toHaveBeenCalledWith(
        "session-website-plan",
        "ask-deployment-target",
        expect.objectContaining({
          payload: {
            reason: "user cancelled ASK",
          },
        }),
        null,
      );
    });
  });

});
