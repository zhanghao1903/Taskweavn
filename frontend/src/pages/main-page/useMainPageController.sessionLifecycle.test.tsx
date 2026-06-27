import { act, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LoadMainPageSnapshot } from "./runtime/adapter";
import {
  loadImmediateSnapshot,
  renderMainPageController,
  testAdapter,
} from "./useMainPageController.testUtils";

describe("useMainPageController session lifecycle", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("switches the active session after creating a session", async () => {
    const createSession = vi.fn(async () => ({
      session: {
        id: "session-new",
        name: "New session",
      },
      sessionId: "session-new",
    }));
    const loadSnapshot = vi.fn<LoadMainPageSnapshot>(loadImmediateSnapshot);
    const loadWorkspaceCatalog = vi.fn(async () => ({
      currentWorkspaceId: "workspace-1",
      workspaces: [],
    }));

    const { result } = renderMainPageController({
      adapter: testAdapter({
        createSession,
        loadSnapshot,
        loadWorkspaceCatalog,
        runtimeKind: "http",
        sessionId: "session-website-plan",
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });
    await waitFor(() => {
      expect(loadWorkspaceCatalog).toHaveBeenCalledTimes(1);
    });

    act(() => {
      result.current.actions.createSession();
    });
    act(() => {
      result.current.actions.changeSessionDialogDraft("New session");
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    await waitFor(() => {
      expect(createSession).toHaveBeenCalledWith(
        { name: "New session" },
        "workspace-1",
      );
    });
    await waitFor(() => {
      expect(loadSnapshot).toHaveBeenCalledWith(
        "s3-draft-ready",
        "session-new",
        "workspace-1",
      );
    });

    expect(result.current.activeSessionId).toBe("session-new");
    expect(result.current.sessionDialog.mode).toBe("idle");
    await waitFor(() => {
      expect(loadWorkspaceCatalog).toHaveBeenCalledTimes(2);
    });
  });

  it("cancels and validates session create before calling the adapter", async () => {
    const createSession = vi.fn(async () => ({
      sessionId: "session-new",
    }));
    const { result } = renderMainPageController({
      adapter: testAdapter({
        createSession,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.createSession();
    });
    act(() => {
      result.current.actions.cancelSessionDialog();
    });

    expect(result.current.sessionDialog.mode).toBe("idle");
    expect(createSession).not.toHaveBeenCalled();

    act(() => {
      result.current.actions.createSession();
    });
    act(() => {
      result.current.actions.changeSessionDialogDraft("   ");
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    expect(createSession).not.toHaveBeenCalled();
    expect(result.current.sessionDialog).toMatchObject({
      error: "Session name must not be empty.",
      mode: "create",
    });
  });

  it("keeps the create flow open with pending and error states", async () => {
    const createSession = vi.fn(
      () =>
        new Promise<never>((_resolve, reject) => {
          setTimeout(() => reject(new Error("create failed")), 0);
        }),
    );
    const { result } = renderMainPageController({
      adapter: testAdapter({
        createSession,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.metadata.id).toBe("s3-draft-ready");
    });

    act(() => {
      result.current.actions.createSession();
    });
    act(() => {
      result.current.actions.changeSessionDialogDraft("New session");
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    await waitFor(() => {
      expect(result.current.isCreatingSession).toBe(true);
    });

    await waitFor(() => {
      expect(result.current.sessionDialog).toMatchObject({
        error: "Create session failed. Please retry.",
        mode: "create",
      });
    });
  });

  it("validates and submits session rename inline", async () => {
    const renameSession = vi.fn(async () => ({
      session: {
        id: "session-website-plan",
        name: "Renamed session",
      },
    }));
    const loadWorkspaceCatalog = vi.fn(async () => ({
      currentWorkspaceId: "workspace-1",
      workspaces: [],
    }));
    const { result } = renderMainPageController({
      adapter: testAdapter({
        loadWorkspaceCatalog,
        renameSession,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.snapshot.session.name).toBe(
        "Personal website plan",
      );
    });
    await waitFor(() => {
      expect(loadWorkspaceCatalog).toHaveBeenCalledTimes(1);
    });

    const activeSession = result.current.snapshotData?.snapshot.session;
    if (!activeSession) {
      throw new Error("Expected active session.");
    }

    act(() => {
      result.current.actions.renameSession(activeSession);
    });
    act(() => {
      result.current.actions.changeSessionDialogDraft("");
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    expect(renameSession).not.toHaveBeenCalled();
    expect(result.current.sessionDialog).toMatchObject({
      error: "Session name must not be empty.",
      mode: "rename",
    });

    act(() => {
      result.current.actions.changeSessionDialogDraft("Renamed session");
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    await waitFor(() => {
      expect(renameSession).toHaveBeenCalledWith({
        name: "Renamed session",
        sessionId: "session-website-plan",
      }, "workspace-1");
    });
    expect(result.current.sessionDialog.mode).toBe("idle");
    await waitFor(() => {
      expect(loadWorkspaceCatalog).toHaveBeenCalledTimes(2);
    });
  });

  it("keeps the rename flow open on command errors", async () => {
    const renameSession = vi.fn(async () => {
      throw new Error("rename failed");
    });
    const { result } = renderMainPageController({
      adapter: testAdapter({
        renameSession,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.snapshot.session.id).toBe(
        "session-website-plan",
      );
    });

    const activeSession = result.current.snapshotData?.snapshot.session;
    if (!activeSession) {
      throw new Error("Expected active session.");
    }

    act(() => {
      result.current.actions.renameSession(activeSession);
    });
    act(() => {
      result.current.actions.changeSessionDialogDraft("Renamed session");
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    await waitFor(() => {
      expect(result.current.sessionDialog).toMatchObject({
        error: "Rename session failed. Please retry.",
        mode: "rename",
      });
    });
  });

  it("cancels and confirms session delete inline", async () => {
    const deleteSession = vi.fn(async () => ({
      deletedSessionId: "session-website-plan",
      nextSessionId: "session-next",
    }));
    const loadWorkspaceCatalog = vi.fn(async () => ({
      currentWorkspaceId: "workspace-1",
      workspaces: [],
    }));
    const { result } = renderMainPageController({
      adapter: testAdapter({
        deleteSession,
        loadWorkspaceCatalog,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.snapshot.session.id).toBe(
        "session-website-plan",
      );
    });
    await waitFor(() => {
      expect(loadWorkspaceCatalog).toHaveBeenCalledTimes(1);
    });

    const activeSession = result.current.snapshotData?.snapshot.session;
    if (!activeSession) {
      throw new Error("Expected active session.");
    }

    act(() => {
      result.current.actions.deleteSession(activeSession);
    });
    act(() => {
      result.current.actions.cancelSessionDialog();
    });

    expect(deleteSession).not.toHaveBeenCalled();
    expect(result.current.sessionDialog.mode).toBe("idle");

    act(() => {
      result.current.actions.deleteSession(activeSession);
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    await waitFor(() => {
      expect(deleteSession).toHaveBeenCalledWith(
        "session-website-plan",
        "workspace-1",
      );
    });
    expect(result.current.activeSessionId).toBe("session-next");
    expect(result.current.sessionDialog.mode).toBe("idle");
    await waitFor(() => {
      expect(loadWorkspaceCatalog).toHaveBeenCalledTimes(2);
    });
  });

  it("keeps the delete confirmation open during pending and error states", async () => {
    const deleteSession = vi.fn(
      () =>
        new Promise<never>((_resolve, reject) => {
          setTimeout(() => reject(new Error("delete failed")), 0);
        }),
    );
    const { result } = renderMainPageController({
      adapter: testAdapter({
        deleteSession,
      }),
      initialStateId: "s3-draft-ready",
    });

    await waitFor(() => {
      expect(result.current.snapshotData?.snapshot.session.id).toBe(
        "session-website-plan",
      );
    });

    const activeSession = result.current.snapshotData?.snapshot.session;
    if (!activeSession) {
      throw new Error("Expected active session.");
    }

    act(() => {
      result.current.actions.deleteSession(activeSession);
    });
    act(() => {
      result.current.actions.submitSessionDialog();
    });

    await waitFor(() => {
      expect(result.current.isDeletingSession).toBe(true);
    });

    await waitFor(() => {
      expect(result.current.sessionDialog).toMatchObject({
        error: "Delete session failed. Please retry.",
        mode: "delete",
      });
    });
  });
});
