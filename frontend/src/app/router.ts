import type { SessionId, TaskId } from "../api/contracts";

const DEFAULT_SESSION_ID: SessionId = "demo-session";

export type AppRoute = {
  sessionId: SessionId;
  taskId: TaskId | null;
};

export function readRoute(pathname = window.location.pathname): AppRoute {
  const parts = pathname.split("/").filter(Boolean);
  const sessionIndex = parts.indexOf("sessions");
  const taskIndex = parts.indexOf("tasks");
  return {
    sessionId:
      sessionIndex >= 0 && parts[sessionIndex + 1]
        ? parts[sessionIndex + 1]
        : DEFAULT_SESSION_ID,
    taskId:
      taskIndex >= 0 && parts[taskIndex + 1] ? parts[taskIndex + 1] : null,
  };
}

export function buildTaskRoute(sessionId: SessionId, taskId: TaskId | null) {
  if (!taskId) {
    return `/sessions/${sessionId}`;
  }
  return `/sessions/${sessionId}/tasks/${taskId}`;
}
