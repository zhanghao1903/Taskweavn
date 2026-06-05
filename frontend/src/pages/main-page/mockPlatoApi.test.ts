import { describe, expect, it } from "vitest";

import {
  mainPageStates,
  type MainPageStateId,
} from "./fixtures";
import {
  appendTaskInputMockCommand,
  createMainPageMockAdapter,
  getMainPageMockSnapshot,
  listMainPageStateOptions,
  mainPageMockAdapter,
  updateTaskNodeMockCommand,
} from "./mockPlatoApi";
import {
  getMainPageStateCatalogEntry,
  mainPageStateCatalog,
} from "./mainPageStateCatalog";

describe("mock Plato API adapter", () => {
  it("exposes the Figma baseline states as API-backed state options", () => {
    expect(listMainPageStateOptions()).toHaveLength(mainPageStates.length);
  });

  it("keeps the state catalog aligned with fixture states", () => {
    const fixtureIds = mainPageStates.map((state) => state.id);
    const catalogIds = mainPageStateCatalog.map((state) => state.id);

    expect(catalogIds).toEqual(fixtureIds);
    expect(listMainPageStateOptions()).toEqual(
      mainPageStates.map((state) => ({
        id: state.id,
        label: state.label,
      })),
    );
  });

  it("documents every state with user-facing lifecycle intent", () => {
    for (const state of mainPageStateCatalog) {
      expect(state.userSituation).not.toHaveLength(0);
      expect(state.pageFocus).not.toHaveLength(0);
      expect(state.expectedUserAction).not.toHaveLength(0);
      expect(state.primarySurfaces.length).toBeGreaterThan(0);
    }
  });

  it("keeps fixture and catalog copy free of internal implementation language", () => {
    const fixtureCopy = mainPageStates.flatMap((state) => [
      state.detail.eyebrow,
      state.detail.title,
      state.detail.body,
      "actionLabel" in state.detail ? state.detail.actionLabel : undefined,
      state.inputScope.label,
      state.inputScope.placeholder,
      ...state.messages.flatMap((message) => [message.title, message.body]),
      state.result?.title,
      state.result?.summary,
    ]);
    const catalogCopy = mainPageStateCatalog.flatMap((state) => [
      state.userSituation,
      state.pageFocus,
      ...state.primarySurfaces,
      state.expectedUserAction,
    ]);

    const copy = [...fixtureCopy, ...catalogCopy].filter(Boolean).join("\n");

    expect(copy).not.toMatch(
      /TaskTree|task tree|TaskNode|Context inspector|ResultCard|Session Workspace/i,
    );
    expect(copy).not.toMatch(/\bASK\b/);
  });

  it("can retrieve a catalog entry for each baseline state", () => {
    const ids = mainPageStates.map((state) => state.id as MainPageStateId);

    for (const id of ids) {
      expect(getMainPageStateCatalogEntry(id).id).toBe(id);
    }
  });

  it("exposes a single adapter boundary for the main page runtime", async () => {
    const customLoader = async () => getMainPageMockSnapshot("s1-empty");
    const adapter = createMainPageMockAdapter({
      loadSnapshot: customLoader,
    });

    expect(mainPageMockAdapter.loadSnapshot).toBeTypeOf("function");
    expect(adapter.loadSnapshot).toBe(customLoader);
    expect((await adapter.loadSnapshot("s8-completed")).metadata.id).toBe(
      "s1-empty",
    );
  });

  it("projects confirmation fixture state into pending confirmations", () => {
    const { snapshot } = getMainPageMockSnapshot("s7-confirmation");

    expect(snapshot.pendingConfirmations).toHaveLength(1);
    expect(snapshot.pendingAsks).toEqual([]);
    expect(snapshot.activeAsk).toBeNull();
    expect(snapshot.pendingConfirmations[0]).toMatchObject({
      id: "confirmation-visual-baseline",
      status: "pending",
      taskNodeId: "task-visual-direction",
    });
    expect(snapshot.messages.some((message) => message.kind === "actionable")).toBe(true);
  });

  it("projects file changes into structured file change items", () => {
    const { snapshot } = getMainPageMockSnapshot("s9-file-changes");

    expect(snapshot.fileChangeSummary?.recursive).toBe(true);
    expect(snapshot.fileChangeSummary?.summary).toBe(
      "Recursive summary: 3 files changed in the selected task and its children.",
    );
    expect(snapshot.fileChangeSummary?.changedFiles).toEqual([
      expect.objectContaining({
        path: "package.json",
        changeType: "modified",
        summary: "Updated frontend dependencies and scripts.",
      }),
      expect.objectContaining({
        path: "src/App.tsx",
        changeType: "created",
        summary: "Added Plato app shell and Main Page entry.",
      }),
      expect.objectContaining({
        path: "src/styles.css",
        changeType: "created",
        summary: "Added baseline styling for the first prototype.",
      }),
    ]);
  });

  it("keeps task command feedback free of raw task ids", async () => {
    const appendResponse = await appendTaskInputMockCommand(
      "session-1",
      "task-internal-id",
      {
        commandId: "command-append",
        payload: {
          content: "Add more guidance.",
          mode: "guidance",
        },
        sessionId: "session-1",
      },
    );
    const updateResponse = await updateTaskNodeMockCommand(
      "session-1",
      "task-internal-id",
      {
        commandId: "command-update",
        payload: {
          summary: "Refine the task.",
        },
        sessionId: "session-1",
      },
    );

    expect(appendResponse.result).not.toBeNull();
    expect(updateResponse.result).not.toBeNull();
    if (appendResponse.result === null || updateResponse.result === null) {
      throw new Error("Expected accepted command responses.");
    }

    expect(appendResponse.result.message).toBe("Task input accepted.");
    expect(updateResponse.result.message).toBe("Task update accepted.");
    expect(appendResponse.result.message).not.toContain("task-internal-id");
    expect(updateResponse.result.message).not.toContain("task-internal-id");
  });

  it("projects completed results into structured result sections", () => {
    const { snapshot } = getMainPageMockSnapshot("s8-completed");

    expect(snapshot.result?.sections).toEqual([
      expect.objectContaining({
        title: "Delivered structure",
        kind: "list",
      }),
      expect.objectContaining({
        title: "Next review focus",
        kind: "text",
      }),
    ]);
  });

  it("projects separated canonical dimensions into mock snapshots", () => {
    const { snapshot } = getMainPageMockSnapshot("s7-confirmation");

    expect(snapshot.schemaVersion).toBe("plato.main.v1");
    expect(snapshot.planning?.state).toBe("published");
    expect(snapshot.taskTree?.readiness).toBe("published");
    expect(snapshot.taskTree?.executionRollup?.blockedByConfirmation).toBe(1);
    expect(
      snapshot.taskTree?.nodes.find((node) => node.status === "waiting_user"),
    ).toMatchObject({
      confirmation: "pending",
      execution: "pending",
      readiness: "published",
    });
  });
});
