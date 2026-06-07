import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AppProviders } from "../app/providers";
import { createHttpMainPageAdapter } from "../pages/main-page/httpMainPageAdapter";
import { MainPage } from "../pages/main-page/MainPage";
import { deriveMainPageMetadataFromSnapshot } from "../pages/main-page/runtime/metadata";
import { createHttpPlatoApi } from "../shared/api/platoApi";

const requiredEnv = {
  baseUrl: process.env.PLATO_E2E_SIDECAR_BASE_URL,
  sessionId: process.env.PLATO_E2E_SESSION_ID,
  taskId: process.env.PLATO_E2E_TASK_ID,
};

const describeSidecarE2E = Object.values(requiredEnv).every(Boolean)
  ? describe
  : describe.skip;

describeSidecarE2E("Main Page command failure recovery real sidecar E2E", () => {
  afterEach(() => {
    globalThis.history.pushState(null, "", "/");
  });

  it("renders recovery labels for a rejected retry command", async () => {
    globalThis.history.pushState(null, "", "/");
    const baseUrl = requiredEnv.baseUrl ?? "";
    const sessionId = requiredEnv.sessionId ?? "";
    const taskId = requiredEnv.taskId ?? "";
    const api = createHttpPlatoApi({ baseUrl });
    const initialSnapshotResponse = await api.getSessionSnapshot(sessionId);
    if (!initialSnapshotResponse.ok || initialSnapshotResponse.data === null) {
      throw new Error("Sidecar fixture did not return the initial snapshot.");
    }
    const initialSnapshot = initialSnapshotResponse.data;
    expect(
      initialSnapshot.taskTree?.nodes.find((node) => node.id === taskId)?.status,
    ).toBe("failed");

    const primerResponse = await api.retryTask(sessionId, taskId, {
      commandId: `prime-retry-${taskId}-${Date.now()}`,
      payload: {
        startImmediately: true,
      },
      sessionId,
    });
    expect(primerResponse.ok).toBe(true);

    const adapter = {
      ...createHttpMainPageAdapter({
        api,
        sessionId,
      }),
      async loadSnapshot() {
        return {
          metadata: deriveMainPageMetadataFromSnapshot(
            initialSnapshot,
            {
              id: "sidecar-command-failure",
              label: "Live Session",
            },
          ),
          snapshot: initialSnapshot,
        };
      },
      subscribeSessionEvents() {
        return () => {};
      },
    };

    render(
      <AppProviders>
        <MainPage adapter={adapter} />
      </AppProviders>,
    );

    await waitFor(
      () => {
        expect(screen.getAllByText("Diagnostics smoke").length).toBeGreaterThan(0);
      },
      { timeout: 10_000 },
    );
    expect(screen.getAllByText(`Run ${requiredEnv.taskId}`).length).toBeGreaterThan(0);

    const retryButton = await screen.findByRole("button", { name: "Retry" });
    fireEvent.click(retryButton);

    expect(
      await screen.findByText("only failed tasks can be retried", {}, { timeout: 10_000 }),
    ).toBeInTheDocument();
    expect(screen.getByText("Refresh session")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Refresh session" }),
    ).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("command_rejected");
    expect(document.body).not.toHaveTextContent("recoveryActions");
    expect(document.body).not.toHaveTextContent("productCategory");
    expect(document.body).not.toHaveTextContent("TaskStoreError");
  });
});
