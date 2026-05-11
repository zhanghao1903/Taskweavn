import { useEffect, useMemo, useState } from "react";

import type { TaskId } from "../api/contracts";
import { buildTaskRoute, readRoute } from "./router";
import { SessionWorkspace } from "../features/session-shell/SessionWorkspace";

export function App() {
  const initialRoute = useMemo(() => readRoute(), []);
  const [sessionId] = useState(initialRoute.sessionId);
  const [selectedTaskId, setSelectedTaskId] = useState<TaskId | null>(
    initialRoute.taskId,
  );

  useEffect(() => {
    const nextPath = buildTaskRoute(sessionId, selectedTaskId);
    if (window.location.pathname !== nextPath) {
      window.history.replaceState(null, "", nextPath);
    }
  }, [selectedTaskId, sessionId]);

  return (
    <SessionWorkspace
      sessionId={sessionId}
      selectedTaskId={selectedTaskId}
      onSelectTask={setSelectedTaskId}
    />
  );
}
