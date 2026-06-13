import { describe, expect, it, vi } from "vitest";

import {
  markStartupTiming,
  STARTUP_TIMING_PREFIX,
} from "./startupTiming.mjs";

describe("startup timing logs", () => {
  it("emits sanitized startup timing JSON lines", () => {
    const log = vi.spyOn(console, "log").mockImplementation(() => {});

    const payload = markStartupTiming("renderer_app_ready", {
      ignoredObject: { unsafe: true },
      "invalid key": "ignored",
      numericValue: 12.3456,
      source: "renderer",
      startupId: "startup-test",
    });

    expect(payload).toMatchObject({
      event: "renderer_app_ready",
      numericValue: 12.35,
      schemaVersion: "plato.startup_timing.v1",
      source: "renderer",
      startupId: "startup-test",
    });
    expect(payload).not.toHaveProperty("ignoredObject");
    expect(payload).not.toHaveProperty("invalid key");
    expect(log).toHaveBeenCalledWith(
      expect.stringMatching(new RegExp(`^${escapeRegExp(STARTUP_TIMING_PREFIX)} \\{`)),
    );

    log.mockRestore();
  });
});

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
