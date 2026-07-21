const DEFAULT_SIGNALS = ["SIGINT", "SIGTERM"];

export function installIdempotentShutdownSignalHandlers({
  onShutdown,
  processLike = process,
  signals = DEFAULT_SIGNALS,
}) {
  let shutdownRequested = false;
  const handlers = new Map();

  for (const signal of signals) {
    const handler = () => {
      if (shutdownRequested) {
        return;
      }
      shutdownRequested = true;
      onShutdown(signal);
    };
    handlers.set(signal, handler);
    processLike.on(signal, handler);
  }

  return {
    dispose() {
      for (const [signal, handler] of handlers) {
        processLike.off(signal, handler);
      }
    },
    get shutdownRequested() {
      return shutdownRequested;
    },
  };
}
