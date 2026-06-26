import { useMutation } from "@tanstack/react-query";

import type { ProductRecoveryAction } from "../../shared/api/platoApi";
import type { TaskNodeId, WorkspaceId } from "../../shared/api/types";
import type { InputTarget } from "./mainPageUiTypes";
import type { MainPageInputCommandMode } from "./mainPageViewModel";
import { handleCommandResponse } from "./runtime/commandRefresh";
import type {
  MainPageAdapter,
  MainPageRuntimeSnapshot,
} from "./runtime/adapter";

type SnapshotRefetchResult = {
  data?: MainPageRuntimeSnapshot;
  status: string;
};

type CommandErrorSetter = (
  message: string | null,
  recoveryActions?: ProductRecoveryAction[],
) => void;

export type InputSubmitContext = {
  mode: MainPageInputCommandMode;
  sessionId: string;
  target: InputTarget;
  taskNodeId: TaskNodeId | null;
};

export type UseMainPageInputCommandMutationOptions = {
  activeWorkspaceId: WorkspaceId | null;
  adapter: MainPageAdapter;
  refetchSnapshot: () => Promise<SnapshotRefetchResult>;
  setInputCommandError: CommandErrorSetter;
  setInputDraft: (draft: string) => void;
};

export function useMainPageInputCommandMutation({
  activeWorkspaceId,
  adapter,
  refetchSnapshot,
  setInputCommandError,
  setInputDraft,
}: UseMainPageInputCommandMutationOptions) {
  return useMutation({
    mutationFn: async ({
      content,
      mode,
      sessionId,
      target,
      taskNodeId,
    }: {
      content: string;
      mode: MainPageInputCommandMode;
      sessionId: string;
      target: InputTarget;
      taskNodeId: TaskNodeId | null;
    }) => {
      const commandId = `append-${target}-${Date.now()}`;

      if (mode === "append_task_input" && taskNodeId) {
        return adapter.appendTaskInput(
          sessionId,
          taskNodeId,
          {
            commandId,
            sessionId,
            payload: {
              content,
              mode: "guidance",
            },
          },
          activeWorkspaceId,
        );
      }

      if (mode === "generate_task_tree") {
        return adapter.generateTaskTree(
          {
            commandId: `generate-task-tree-${Date.now()}`,
            sessionId,
            payload: {
              prompt: content,
            },
          },
          activeWorkspaceId,
        );
      }

      return adapter.appendSessionInput(
        {
          commandId,
          sessionId,
          payload: {
            content,
            mode: "global_guidance",
          },
        },
        activeWorkspaceId,
      );
    },
    onError: () => {
      setInputCommandError("Input submission failed. Please retry.");
    },
    onSuccess: (response) => {
      const result = handleCommandResponse(
        response,
        "Input submission was rejected.",
      );

      if (result.errorMessage) {
        setInputCommandError(result.errorMessage, result.recoveryActions);
        return;
      }

      setInputCommandError(null);
      setInputDraft("");
      if (result.shouldRefetch) {
        void refetchSnapshot();
      }
    },
  });
}
