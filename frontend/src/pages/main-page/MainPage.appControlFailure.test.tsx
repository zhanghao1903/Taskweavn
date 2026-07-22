import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MainPage } from "./MainPage";
import { createMainPageMockAdapter } from "./mockPlatoApi";
import type { RouteRuntimeInputCommand } from "./runtime/adapter";
import { missingAccessibilityRuntimeInputResponse } from "./useMainPageController.testUtils";

describe("MainPage app-control failures", () => {
  it("keeps the user input and concrete missing-accessibility reason in Conversation", async () => {
    const user = userEvent.setup();
    const routeRuntimeInput = vi.fn<RouteRuntimeInputCommand>(async (request) =>
      missingAccessibilityRuntimeInputResponse(request),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MainPage
          adapter={createMainPageMockAdapter({
            routeRuntimeInput,
            showStatePicker: false,
          })}
          initialStateId="s3-draft-ready"
        />
      </QueryClientProvider>,
    );

    const content = "给微信的文件传输助手发送“你好”";
    const input = await screen.findByLabelText("Context message");
    await user.type(input, content);
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(routeRuntimeInput).toHaveBeenCalledOnce();
    expect(await screen.findByText(content)).toBeInTheDocument();
    expect(
      await screen.findAllByText(/missing_accessibility/u),
    ).not.toHaveLength(0);
    expect(screen.getAllByText(/Plato Computer Use Helper/u)).not.toHaveLength(0);
    expect(screen.getByText("Open settings")).toBeInTheDocument();
    expect(screen.getByText("Retry command")).toBeInTheDocument();
  });
});
