import { describe, expect, it, vi } from "vitest";

import { ApiClient, ApiClientError } from "./client";
import type { FetchFn } from "./client";

describe("ApiClient", () => {
  it("trims the base URL and sends JSON requests", async () => {
    const fetcher = vi.fn<FetchFn>(async () =>
      jsonResponse({
        ok: true,
      }),
    );
    const client = new ApiClient({
      baseUrl: "https://plato.test/",
      fetcher,
    });

    await expect(
      client.postJson("/api/v1/sessions/session-1/input", {
        hello: "world",
      }),
    ).resolves.toEqual({ ok: true });

    expect(client.baseUrl).toBe("https://plato.test");
    expect(fetcher).toHaveBeenCalledWith(
      "https://plato.test/api/v1/sessions/session-1/input",
      expect.objectContaining({
        body: JSON.stringify({ hello: "world" }),
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        method: "POST",
      }),
    );
  });

  it("sends GET requests without a JSON body", async () => {
    const fetcher = vi.fn<FetchFn>(async () =>
      jsonResponse({
        data: "snapshot",
      }),
    );
    const client = new ApiClient({
      baseUrl: "https://plato.test",
      fetcher,
    });

    await client.getJson("/api/v1/sessions/session-1/snapshot");

    expect(fetcher).toHaveBeenCalledWith(
      "https://plato.test/api/v1/sessions/session-1/snapshot",
      expect.objectContaining({
        body: undefined,
        headers: {
          Accept: "application/json",
        },
        method: "GET",
      }),
    );
  });

  it("raises ApiClientError for non-2xx responses", async () => {
    const fetcher = vi.fn<FetchFn>(async () =>
      jsonResponse(
        {
          error: {
            code: "not_found",
            message: "Session missing.",
          },
        },
        404,
      ),
    );
    const client = new ApiClient({
      baseUrl: "https://plato.test",
      fetcher,
    });

    await expect(client.getJson("/missing")).rejects.toMatchObject({
      method: "GET",
      name: "ApiClientError",
      path: "/missing",
      responseBody: {
        error: {
          code: "not_found",
          message: "Session missing.",
        },
      },
      status: 404,
    } satisfies Partial<ApiClientError>);
  });
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    headers: {
      "Content-Type": "application/json",
    },
    status,
  });
}
