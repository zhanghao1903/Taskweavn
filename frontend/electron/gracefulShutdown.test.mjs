import { EventEmitter } from "node:events";

import { describe, expect, it, vi } from "vitest";

import { installIdempotentShutdownSignalHandlers } from "./gracefulShutdown.mjs";

describe("graceful shutdown signal handlers", () => {
  it("keeps signal listeners installed while requesting shutdown once", () => {
    const processLike = new EventEmitter();
    const onShutdown = vi.fn();
    const lifecycle = installIdempotentShutdownSignalHandlers({
      onShutdown,
      processLike,
    });

    processLike.emit("SIGINT");
    processLike.emit("SIGINT");
    processLike.emit("SIGTERM");

    expect(onShutdown).toHaveBeenCalledTimes(1);
    expect(onShutdown).toHaveBeenCalledWith("SIGINT");
    expect(lifecycle.shutdownRequested).toBe(true);
    expect(processLike.listenerCount("SIGINT")).toBe(1);
    expect(processLike.listenerCount("SIGTERM")).toBe(1);
  });

  it("can remove the installed handlers", () => {
    const processLike = new EventEmitter();
    const onShutdown = vi.fn();
    const lifecycle = installIdempotentShutdownSignalHandlers({
      onShutdown,
      processLike,
    });

    lifecycle.dispose();
    processLike.emit("SIGINT");

    expect(onShutdown).not.toHaveBeenCalled();
    expect(processLike.listenerCount("SIGINT")).toBe(0);
    expect(processLike.listenerCount("SIGTERM")).toBe(0);
  });
});
