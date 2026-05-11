import { SendHorizonal } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import type { SessionId, TaskId } from "../../api/contracts";
import { useAppendSessionMessage, useAppendTaskMessage } from "../../api/client";

type Props = {
  sessionId: SessionId;
  selectedTaskId: TaskId | null;
};

export function ComposerBar({ selectedTaskId, sessionId }: Props) {
  const [value, setValue] = useState("");
  const [mode, setMode] = useState<"global" | "task_scoped">(
    selectedTaskId ? "task_scoped" : "global",
  );
  const appendSessionMessage = useAppendSessionMessage(sessionId);
  const appendTaskMessage = useAppendTaskMessage(sessionId, selectedTaskId);

  const taskScoped = mode === "task_scoped" && selectedTaskId !== null;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = value.trim();
    if (!content) return;
    if (taskScoped) {
      appendTaskMessage.mutate({
        sessionId,
        taskId: selectedTaskId,
        content,
        mode: "task_scoped",
      });
    } else {
      appendSessionMessage.mutate({ sessionId, content, mode: "global" });
    }
    setValue("");
  }

  return (
    <form className="composer" onSubmit={submit}>
      <div className="composer-mode" role="group" aria-label="Input mode">
        <button
          className={mode === "global" ? "active" : ""}
          onClick={() => setMode("global")}
          type="button"
        >
          Global
        </button>
        <button
          className={taskScoped ? "active" : ""}
          disabled={!selectedTaskId}
          onClick={() => setMode("task_scoped")}
          type="button"
        >
          Task
        </button>
      </div>
      <input
        aria-label={taskScoped ? "Task-scoped message" : "Global session message"}
        onChange={(event) => setValue(event.target.value)}
        placeholder={
          taskScoped
            ? "Add guidance to the selected task..."
            : "Describe a global goal or update..."
        }
        value={value}
      />
      <button className="send-button" type="submit">
        <SendHorizonal size={18} />
        Send
      </button>
    </form>
  );
}
