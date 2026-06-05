import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { AppErrorBoundary } from "./AppErrorBoundary";
import { AppProviders } from "./providers";
import { MainPage } from "../pages/main-page/MainPage";
import type { CommandResponse, UiEvent } from "../shared/api/types";
import type {
  AppendSessionInputCommand,
  AppendTaskInputCommand,
  GenerateTaskTreeCommand,
  LoadMainPageSnapshot,
  MainPageAdapter,
  PublishTaskTreeCommand,
  ResolveConfirmationCommand,
  SubscribeSessionEvents,
} from "../pages/main-page/runtime/adapter";
import type { MainPageStateId } from "../pages/main-page/mockPlatoApi";
import {
  createMainPageMockAdapter,
  getMainPageMockSnapshot,
  listMainPageStateOptions,
} from "../pages/main-page/mockPlatoApi";

describe("App", () => {
  it("renders the Plato main page shell", async () => {
    render(
      <AppProviders>
        <App />
      </AppProviders>,
    );

    expect(screen.getByRole("banner")).toHaveTextContent("Plato");
    expect(screen.queryByText(/Task-first Intelligent/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Workbench")).not.toBeInTheDocument();
    expect(await screen.findByText("Personal Website")).toBeInTheDocument();
    expect(screen.queryByLabelText("State")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Task workspace")).toBeInTheDocument();
    expect(screen.getByLabelText("Context message")).toBeInTheDocument();
    expect(screen.queryByText("Message")).not.toBeInTheDocument();
    expect(screen.getByText("Requirement analysis")).toBeInTheDocument();
  });

  it("keeps the fixture state picker available when explicitly enabled", () => {
    renderFixtureMainPageWithStatePicker();

    const statePicker = screen.getByLabelText("State");

    for (const state of listMainPageStateOptions()) {
      expect(statePicker).toHaveTextContent(state.label);
    }
  });

  it("opens and closes the activity overlay from latest activity", async () => {
    const user = userEvent.setup();

    render(
      <AppProviders>
        <App />
      </AppProviders>,
    );

    expect(await screen.findByLabelText("Latest activity")).toBeInTheDocument();
    expect(screen.queryByText("Session messages")).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Open activity overlay" }),
    );

    expect(screen.getByLabelText("Activity overlay")).toBeInTheDocument();
    expect(screen.getByText("Task updates")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(screen.queryByLabelText("Activity overlay")).not.toBeInTheDocument();
  });

  it("renders confirmation and file-change fixture states when explicitly requested", async () => {
    const confirmationView = renderFixtureMainPageWithStatePicker("s7-confirmation");
    expect(await screen.findByText("Confirm baseline")).toBeInTheDocument();

    confirmationView.unmount();
    renderFixtureMainPageWithStatePicker("s9-file-changes");
    expect(await screen.findByText("package.json")).toBeInTheDocument();
  });

  it("selects a TaskNode and scopes the input to that task", async () => {
    const user = userEvent.setup();

    render(
      <AppProviders>
        <App />
      </AppProviders>,
    );

    await user.click(
      await screen.findByRole("button", { name: /Initial implementation/i }),
    );

    expect(screen.getByRole("heading", { name: "Initial implementation" })).toBeInTheDocument();
    expect(screen.getByText("Task details")).toBeInTheDocument();
    expect(screen.getByText("Scope: selected task / Initial implementation")).toBeInTheDocument();
    expect(screen.getByLabelText("Latest activity")).toBeInTheDocument();
  });

  it("projects the latest activity by the selected TaskNode", async () => {
    const user = userEvent.setup();

    renderFixtureMainPageWithStatePicker("s6-running");
    expect(await screen.findByText("Implementation started")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Visual direction/i }));

    expect(screen.queryByText("Implementation started")).not.toBeInTheDocument();
    expect(screen.getByText("1/2 shown")).toBeInTheDocument();
    expect(screen.getByText("Session-wide")).toBeInTheDocument();
    expect(screen.queryByText("Session messages")).not.toBeInTheDocument();
  });

  it("scopes result and file-change detail to the selected TaskNode", async () => {
    const user = userEvent.setup();

    renderFixtureMainPageWithStatePicker("s9-file-changes");
    expect(await screen.findByText("Changed files")).toBeInTheDocument();
    expect(screen.getByText("package.json")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Visual direction/i }));

    expect(screen.getByRole("heading", { name: "Visual direction" })).toBeInTheDocument();
    expect(screen.queryByText("package.json")).not.toBeInTheDocument();
    expect(screen.getByText("Task details")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Initial implementation/i }));

    expect(await screen.findByText("Changed files")).toBeInTheDocument();
    expect(screen.getByText("package.json")).toBeInTheDocument();
  });

  it("refetches backend facts after an accepted confirmation command", async () => {
    const user = userEvent.setup();
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          loadSnapshot,
        })}
        initialStateId="s7-confirmation"
      />,
    );

    await user.click(await screen.findByRole("button", { name: "Confirm baseline" }));
    await user.click(screen.getByRole("button", { name: "Resolve decision" }));

    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });
    expect(screen.queryByText("User decision captured")).not.toBeInTheDocument();
    expect(screen.getByText("Decision needed")).toBeInTheDocument();
  });

  it("shows command pending state while resolving a confirmation", async () => {
    const user = userEvent.setup();
    const pendingResolve: ResolveConfirmationCommand = () =>
      new Promise(() => {
        // Keep the command pending so the pending UI can be asserted.
      });

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          loadSnapshot: loadImmediateSnapshot,
          resolveConfirmation: pendingResolve,
        })}
        initialStateId="s7-confirmation"
      />,
    );

    await user.click(await screen.findByRole("button", { name: "Confirm baseline" }));
    await user.click(screen.getByRole("button", { name: "Resolve decision" }));

    expect(screen.getByText("Resolving decision")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resolving" })).toBeDisabled();
  });

  it("shows command error state when resolving a confirmation fails", async () => {
    const user = userEvent.setup();
    const failingResolve: ResolveConfirmationCommand = async () => {
      throw new Error("command unavailable");
    };

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          loadSnapshot: loadImmediateSnapshot,
          resolveConfirmation: failingResolve,
        })}
        initialStateId="s7-confirmation"
      />,
    );

    await user.click(await screen.findByRole("button", { name: "Confirm baseline" }));
    await user.click(screen.getByRole("button", { name: "Resolve decision" }));

    expect(
      await screen.findByText("Confirmation command failed. Please retry."),
    ).toBeInTheDocument();
    expect(screen.getByText("Decision needed")).toBeInTheDocument();
  });

  it("hides the fixture StatePicker when the adapter disables it", async () => {
    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          runtimeKind: "http",
          sessionId: "session-website-plan",
          showStatePicker: false,
        })}
      />,
    );

    expect(await screen.findByText("Personal Website")).toBeInTheDocument();
    expect(screen.queryByLabelText("State")).not.toBeInTheDocument();
  });

  it("submits session-scoped input when no TaskNode is selected", async () => {
    const user = userEvent.setup();
    const appendSessionInput = vi.fn<AppendSessionInputCommand>(
      async (request) => acceptedCommandResponse(request.commandId),
    );
    const appendTaskInput = vi.fn<AppendTaskInputCommand>(
      async (_sessionId, _taskNodeId, request) =>
        acceptedCommandResponse(request.commandId),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          appendSessionInput,
          appendTaskInput,
          loadSnapshot,
        })}
      />,
    );

    const input = await screen.findByLabelText("Context message");
    await user.type(
      input,
      "Please make the plan smaller.",
    );
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(appendSessionInput).toHaveBeenCalledOnce();
    expect(appendTaskInput).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });
    expect(input).toHaveValue("");
    expect(screen.queryByText("Session guidance captured")).not.toBeInTheDocument();
  });

  it("generates a TaskTree from session input when none exists", async () => {
    const user = userEvent.setup();
    const appendSessionInput = vi.fn<AppendSessionInputCommand>(
      async (request) => acceptedCommandResponse(request.commandId),
    );
    const generateTaskTree = vi.fn<GenerateTaskTreeCommand>(
      async (request) => acceptedCommandResponse(request.commandId),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          appendSessionInput,
          generateTaskTree,
          loadSnapshot,
        })}
        initialStateId="s1-empty"
      />,
    );

    const input = await screen.findByLabelText("Context message");
    await user.type(input, "Plan my personal website.");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(generateTaskTree).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: {
          prompt: "Plan my personal website.",
        },
      }),
    );
    expect(appendSessionInput).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });
  });

  it("publishes a draft task plan through the adapter boundary", async () => {
    const user = userEvent.setup();
    const publishTaskTree = vi.fn<PublishTaskTreeCommand>(
      async (request) => acceptedCommandResponse(request.commandId),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          loadSnapshot,
          publishTaskTree,
        })}
      />,
    );

    await user.click(await screen.findByRole("button", { name: "Publish plan" }));

    expect(publishTaskTree).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: {
          taskTreeId: "task-tree-website",
          startImmediately: true,
        },
      }),
    );
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });
  });

  it("submits task-scoped input when a TaskNode is selected", async () => {
    const user = userEvent.setup();
    const appendSessionInput = vi.fn<AppendSessionInputCommand>(
      async (request) => acceptedCommandResponse(request.commandId),
    );
    const appendTaskInput = vi.fn<AppendTaskInputCommand>(
      async (_sessionId, _taskNodeId, request) =>
        acceptedCommandResponse(request.commandId),
    );
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          appendSessionInput,
          appendTaskInput,
          loadSnapshot,
        })}
        initialStateId="s4-task-selected"
      />,
    );

    const input = await screen.findByLabelText("Context message");
    await user.type(
      input,
      "Use warmer typography.",
    );
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(appendSessionInput).not.toHaveBeenCalled();
    expect(appendTaskInput).toHaveBeenCalledWith(
      "session-website-plan",
      "task-visual-direction",
      expect.objectContaining({
        payload: {
          content: "Use warmer typography.",
          mode: "guidance",
        },
      }),
    );
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });
    expect(input).toHaveValue("");
    expect(screen.queryByText("Task guidance captured")).not.toBeInTheDocument();
  });

  it("refetches snapshot facts for lightweight message events", async () => {
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);
    const subscribeSessionEvents = vi.fn<SubscribeSessionEvents>(
      (sessionId, _cursor, onEvent) => {
        onEvent({
          eventId: "event-message-appended",
          sessionId,
          eventType: "message.appended",
          cursor: "cursor-after-event",
          taskNodeIds: [],
          messageIds: ["message-from-event"],
          payload: {
            title: "Worker update",
            body: "The event stream appended a message.",
            kind: "informational",
          },
          createdAt: "2026-05-17T10:21:00+08:00",
        });

        return () => undefined;
      },
    );

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          loadSnapshot,
          subscribeSessionEvents,
        })}
      />,
    );

    expect(await screen.findByText("Events live")).toBeInTheDocument();
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledTimes(2);
    });
    expect(screen.queryByText("Worker update")).not.toBeInTheDocument();
    expect(subscribeSessionEvents).toHaveBeenCalledWith(
      "session-website-plan",
      "cursor-s3-draft-ready",
      expect.any(Function),
    );
  });

  it("refetches the snapshot when the event stream requests resync", async () => {
    let emitted = false;
    let loadCount = 0;
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(async (stateId) => {
      loadCount += 1;

      if (loadCount > 1) {
        await new Promise((resolve) => {
          window.setTimeout(resolve, 80);
        });
      }

      return getMainPageMockSnapshot(stateId as MainPageStateId);
    });
    const subscribeSessionEvents: SubscribeSessionEvents = (
      sessionId,
      _cursor,
      onEvent,
    ) => {
      if (!emitted) {
        emitted = true;
        onEvent(resyncRequiredEvent(sessionId));
      }

      return () => undefined;
    };

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          loadSnapshot,
          subscribeSessionEvents,
        })}
      />,
    );

    expect(await screen.findByText("Resyncing")).toBeInTheDocument();
    await screen.findByText("Events live");
    expect(loadSnapshot).toHaveBeenCalledTimes(2);
  });

  it("toggles between file changes and result detail views", async () => {
    const user = userEvent.setup();

    renderFixtureMainPageWithStatePicker("s9-file-changes");
    expect(await screen.findByText("Changed files")).toBeInTheDocument();
    expect(screen.getByText("3 files")).toBeInTheDocument();
    expect(screen.queryByText("Recursive subtree summary")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Updated frontend dependencies and scripts."),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "View result" }));

    expect(screen.getByText("Result summary")).toBeInTheDocument();
    expect(
      screen.getByText(
        "The first implementation plan is ready, including page structure, styling direction, and build tasks.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Delivered structure")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "View full result" }));

    expect(screen.getByLabelText("Full result")).toBeInTheDocument();
    expect(screen.getByText("Delivered structure")).toBeInTheDocument();
  });

  it("creates a new session from the sidebar", async () => {
    const user = userEvent.setup();
    const createSession = vi.fn(async () => ({
      session: {
        id: "session-new",
        name: "Launch session",
      },
      sessionId: "session-new",
    }));
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          createSession,
          loadSnapshot,
          runtimeKind: "http",
          sessionId: "session-website-plan",
          showStatePicker: false,
        })}
      />,
    );

    await user.click(await screen.findByRole("button", { name: "New" }));
    await user.clear(screen.getByRole("textbox", { name: "Session name" }));
    await user.type(
      screen.getByRole("textbox", { name: "Session name" }),
      "Launch session",
    );
    await user.click(screen.getByRole("button", { name: "Create session" }));

    expect(createSession).toHaveBeenCalledWith({ name: "Launch session" });
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledWith("s3-draft-ready", "session-new");
    });
  });

  it("validates and cancels the inline session create flow", async () => {
    const user = userEvent.setup();
    const createSession = vi.fn(async () => ({
      sessionId: "session-new",
    }));

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          createSession,
          loadSnapshot: loadImmediateSnapshot,
        })}
      />,
    );

    await user.click(await screen.findByRole("button", { name: "New" }));
    await user.clear(screen.getByRole("textbox", { name: "Session name" }));
    await user.click(screen.getByRole("button", { name: "Create session" }));

    expect(createSession).not.toHaveBeenCalled();
    expect(screen.getByText("Session name must not be empty.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      screen.queryByRole("form", { name: "Create session form" }),
    ).not.toBeInTheDocument();
  });

  it("renames the active session by double-clicking it in the sidebar", async () => {
    const user = userEvent.setup();
    const renameSession = vi.fn(async () => ({
      session: {
        id: "session-website-plan",
        name: "Renamed session",
      },
    }));

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          loadSnapshot: loadImmediateSnapshot,
          renameSession,
        })}
      />,
    );

    await user.dblClick(
      await screen.findByRole("button", { name: "Personal website plan" }),
    );
    await user.clear(screen.getByRole("textbox", { name: "Session name" }));
    await user.type(
      screen.getByRole("textbox", { name: "Session name" }),
      "Renamed session",
    );
    await user.click(screen.getByRole("button", { name: "Rename session" }));

    expect(renameSession).toHaveBeenCalledWith({
      name: "Renamed session",
      sessionId: "session-website-plan",
    });
    expect(await screen.findByText("Renamed session to Renamed session.")).toBeInTheDocument();
  });

  it("confirms session delete from the sidebar context menu", async () => {
    const user = userEvent.setup();
    const deleteSession = vi.fn(async () => ({
      deletedSessionId: "session-website-plan",
      nextSessionId: "session-archive",
    }));

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          deleteSession,
          loadSnapshot: loadImmediateSnapshot,
        })}
      />,
    );

    fireEvent.contextMenu(
      await screen.findByRole("button", { name: "Personal website plan" }),
    );
    await user.click(screen.getByRole("menuitem", { name: "Delete session" }));
    expect(
      screen.getByText(/Plato will archive the local workspace state/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete session" }));

    expect(deleteSession).toHaveBeenCalledWith("session-website-plan");
    expect(await screen.findByText("Session deleted.")).toBeInTheDocument();
  });

  it("renders Audit as a route-ready entry once the Audit Page UI exists", async () => {
    renderWithQueryClient(
      <MainPage adapter={testAdapter({ loadSnapshot: loadImmediateSnapshot })} />,
    );

    const auditLink = await screen.findByRole("link", {
      name: "View audit",
    });

    expect(auditLink).toHaveAttribute(
      "href",
      expect.stringContaining("/sessions/session-website-plan/audit"),
    );
    expect(
      screen.queryByText(
        "Audit entry is reserved until the Audit Page UI is implemented.",
      ),
    ).not.toBeInTheDocument();
  });

  it("switches sessions from the sidebar", async () => {
    const user = userEvent.setup();
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          loadSnapshot,
          runtimeKind: "http",
          sessionId: "session-website-plan",
          showStatePicker: false,
        })}
      />,
    );

    await user.click(await screen.findByRole("button", { name: "Product intro" }));

    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledWith(
        "s3-draft-ready",
        "session-product-intro",
      );
    });
  });

  it("shows a loading frame while the snapshot query is pending", () => {
    const pendingLoader: LoadMainPageSnapshot = () =>
      new Promise(() => {
        // Keep the promise pending so the loading state remains visible.
      });

    renderWithQueryClient(
      <MainPage adapter={testAdapter({ loadSnapshot: pendingLoader })} />,
    );

    expect(screen.getByText("Loading session snapshot")).toBeInTheDocument();
    expect(screen.getByLabelText("State")).toBeInTheDocument();
  });

  it("shows an error frame when the snapshot query fails", async () => {
    const failingLoader: LoadMainPageSnapshot = async () => {
      throw new Error("snapshot unavailable");
    };

    renderWithQueryClient(
      <MainPage adapter={testAdapter({ loadSnapshot: failingLoader })} />,
    );

    expect(
      await screen.findByText("Unable to load session snapshot"),
    ).toBeInTheDocument();
  });

  it("keeps the main page visible when event subscription is unavailable", async () => {
    const subscribeSessionEvents: SubscribeSessionEvents = () => {
      throw new Error("event source missing");
    };

    renderWithQueryClient(
      <MainPage
        adapter={testAdapter({
          subscribeSessionEvents,
        })}
      />,
    );

    expect(await screen.findByText("Personal Website")).toBeInTheDocument();
    expect(screen.getByText("Events offline")).toBeInTheDocument();
    expect(
      screen.getByText("Event stream unavailable: event source missing"),
    ).toBeInTheDocument();
  });

  it("shows a render error boundary when the app view crashes", () => {
    const BrokenView = () => {
      throw new Error("panel crashed");
    };

    render(
      <AppErrorBoundary>
        <BrokenView />
      </AppErrorBoundary>,
    );

    expect(screen.getByText("Plato could not render this view")).toBeInTheDocument();
    expect(screen.getByText("Error: panel crashed")).toBeInTheDocument();
  });
});

function renderWithQueryClient(children: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>,
  );
}

function renderFixtureMainPageWithStatePicker(initialStateId?: MainPageStateId) {
  return renderWithQueryClient(
    <MainPage
      adapter={testAdapter({
        showStatePicker: true,
      })}
      initialStateId={initialStateId}
    />,
  );
}

const loadImmediateSnapshot: LoadMainPageSnapshot = async (stateId) =>
  getMainPageMockSnapshot(stateId as MainPageStateId);

function testAdapter(overrides: Partial<MainPageAdapter> = {}): MainPageAdapter {
  return createMainPageMockAdapter({
    loadSnapshot: loadImmediateSnapshot,
    ...overrides,
  });
}

function acceptedCommandResponse(commandId: string): CommandResponse {
  return {
    requestId: `request-${commandId}`,
    ok: true,
    result: {
      commandId,
      status: "accepted",
      message: "accepted",
      affectedTaskRefs: [],
      objectRefs: [],
      affectedObjects: [],
      emittedMessageIds: [`message-${commandId}`],
      publishedTaskIds: [],
      debugRefs: {},
    },
    error: null,
    refresh: {
      waitForEvents: true,
      suggestedQueries: [],
      affectedTaskRefs: [],
      affectedScopes: [],
    },
  };
}

function resyncRequiredEvent(sessionId: string): UiEvent {
  return {
    eventId: "event-resync-required",
    sessionId,
    eventType: "session.resync_required",
    cursor: "cursor-resync",
    taskNodeIds: [],
    messageIds: [],
    payload: {
      reason: "cursor_expired",
    },
    createdAt: "2026-05-17T10:22:00+08:00",
  };
}
