import type { MainPageSnapshot } from "../../../shared/api/types";
import { selectSessionStatusPresentation } from "../mainPageSelectors";
import type {
  MainPageDetail,
  MainPageInputScope,
  MainPageStateMetadata,
} from "./adapter";

export type MainPageMetadataOptions = {
  id: string;
  label: string;
};

export function deriveMainPageMetadataFromSnapshot(
  snapshot: MainPageSnapshot,
  { id, label }: MainPageMetadataOptions,
): MainPageStateMetadata {
  const selectedTaskNodeId = selectInitialTaskNodeId(snapshot);
  const sessionStatus = selectSessionStatusPresentation(snapshot.session.status);

  return {
    id,
    label,
    detail: detailFromSnapshot(snapshot, selectedTaskNodeId),
    initialSelectedTaskNodeId: selectedTaskNodeId,
    inputScope: inputScopeFromSnapshot(selectedTaskNodeId),
    topStatus: sessionStatus.label,
    topStatusTone: sessionStatus.tone,
  };
}

function selectInitialTaskNodeId(snapshot: MainPageSnapshot): string | null {
  return (
    snapshot.pendingConfirmations[0]?.taskNodeId ??
    snapshot.taskTree?.nodes.find((node) =>
      ["waiting_user", "running"].includes(node.status),
    )?.id ??
    snapshot.taskTree?.nodes[0]?.id ??
    null
  );
}

function detailFromSnapshot(
  snapshot: MainPageSnapshot,
  selectedTaskNodeId: string | null,
): MainPageDetail {
  const confirmation = snapshot.pendingConfirmations[0];
  if (confirmation) {
    return {
      mode: "confirmation",
      eyebrow: "Waiting for user",
      title: confirmation.title,
      body: confirmation.body,
    };
  }

  if (snapshot.fileChangeSummary) {
    return {
      mode: "fileChanges",
      eyebrow: "File changes",
      title: "Changed files",
      body: snapshot.fileChangeSummary.summary,
    };
  }

  if (snapshot.result) {
    return {
      mode: "result",
      eyebrow: "Result",
      title: snapshot.result.title,
      body: snapshot.result.summary,
    };
  }

  if (selectedTaskNodeId !== null) {
    const selectedTask = snapshot.taskTree?.nodes.find(
      (node) => node.id === selectedTaskNodeId,
    );

    return {
      mode: "task",
      eyebrow: "Task",
      title: selectedTask?.title ?? "Selected task",
      body: selectedTask?.summary ?? "Review or refine the selected task.",
    };
  }

  if (snapshot.taskTree) {
    return {
      mode: "session",
      eyebrow: "Session",
      title: snapshot.taskTree.title,
      body: "Review the generated task plan before execution continues.",
    };
  }

  return {
    mode: "workflow",
    eyebrow: "Workflow",
    title: snapshot.workflow.name,
    body:
      snapshot.workflow.inputHint ??
      "Describe the goal you want Plato to turn into a task plan.",
  };
}

function inputScopeFromSnapshot(
  selectedTaskNodeId: string | null,
): MainPageInputScope {
  if (selectedTaskNodeId !== null) {
    return {
      label: "Scope: selected task",
      placeholder: "Add guidance, constraints, or clarification for this task.",
    };
  }

  return {
    label: "Scope: session",
    placeholder: "Describe the goal or add guidance for this session.",
  };
}
