import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  AppendSessionMessageRequest,
  AppendTaskMessageRequest,
  ResolveConfirmationRequest,
  SessionId,
  TaskId,
  TaskMessageScope,
} from "./contracts";
import { useApi } from "./useApi";

export const queryKeys = {
  overview: (sessionId: SessionId) => ["session", sessionId, "overview"] as const,
  taskTrees: (sessionId: SessionId) => ["session", sessionId, "taskTrees"] as const,
  task: (sessionId: SessionId, taskId: TaskId | null) =>
    ["session", sessionId, "task", taskId] as const,
  sessionMessages: (sessionId: SessionId) =>
    ["session", sessionId, "messages"] as const,
  taskMessages: (
    sessionId: SessionId,
    taskId: TaskId | null,
    scope: TaskMessageScope,
  ) => ["session", sessionId, "taskMessages", taskId, scope] as const,
  confirmations: (sessionId: SessionId, taskId?: TaskId) =>
    ["session", sessionId, "confirmations", taskId ?? "all"] as const,
  fileChanges: (sessionId: SessionId, taskId: TaskId | null, recursive: boolean) =>
    ["session", sessionId, "fileChanges", taskId, recursive] as const,
};

export function useSessionOverview(sessionId: SessionId) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.overview(sessionId),
    queryFn: () => api.getSessionOverview(sessionId),
  });
}

export function useTaskTrees(sessionId: SessionId) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.taskTrees(sessionId),
    queryFn: () => api.listTaskTrees(sessionId),
  });
}

export function useTaskNode(sessionId: SessionId, taskId: TaskId | null) {
  const api = useApi();
  return useQuery({
    enabled: taskId !== null,
    queryKey: queryKeys.task(sessionId, taskId),
    queryFn: () => api.getTaskNode(sessionId, taskId as TaskId),
  });
}

export function useSessionMessages(sessionId: SessionId) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.sessionMessages(sessionId),
    queryFn: () => api.listSessionMessages(sessionId),
  });
}

export function useTaskMessages(
  sessionId: SessionId,
  taskId: TaskId | null,
  scope: TaskMessageScope,
) {
  const api = useApi();
  return useQuery({
    enabled: taskId !== null,
    queryKey: queryKeys.taskMessages(sessionId, taskId, scope),
    queryFn: () => api.listTaskMessages(sessionId, taskId as TaskId, scope),
  });
}

export function usePendingConfirmations(sessionId: SessionId, taskId?: TaskId) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.confirmations(sessionId, taskId),
    queryFn: () => api.listPendingConfirmations(sessionId, { taskId }),
  });
}

export function useTaskFileChanges(
  sessionId: SessionId,
  taskId: TaskId | null,
  recursive: boolean,
) {
  const api = useApi();
  return useQuery({
    enabled: taskId !== null,
    queryKey: queryKeys.fileChanges(sessionId, taskId, recursive),
    queryFn: () =>
      api.getTaskFileChanges(sessionId, taskId as TaskId, { recursive }),
  });
}

export function useAppendSessionMessage(sessionId: SessionId) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: AppendSessionMessageRequest) =>
      api.appendSessionMessage(request),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.sessionMessages(sessionId),
      });
    },
  });
}

export function useAppendTaskMessage(sessionId: SessionId, taskId: TaskId | null) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: AppendTaskMessageRequest) =>
      api.appendTaskMessage(request),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.taskMessages(sessionId, taskId, "direct"),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.sessionMessages(sessionId),
      });
    },
  });
}

export function useResolveConfirmation(sessionId: SessionId, taskId: TaskId | null) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: ResolveConfirmationRequest) =>
      api.resolveConfirmation(request),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.confirmations(sessionId, taskId ?? undefined),
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.sessionMessages(sessionId),
      });
    },
  });
}
