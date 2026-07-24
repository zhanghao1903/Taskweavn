import type { AskRequestView } from "../../../shared/api/types";
import { Badge, Button, Text } from "../../../shared/components";
import { useUiText } from "../../../shared/ui-text";
import styles from "./ExecutionAskStatusPanel.module.css";

export type ExecutionAskStatusPanelProps = {
  ask: AskRequestView;
  onViewInConversation: () => void;
};

export function ExecutionAskStatusPanel({
  ask,
  onViewInConversation,
}: ExecutionAskStatusPanelProps) {
  const askText = useUiText().main.interaction.ask;

  return (
    <section className={styles.root} data-ask-id={ask.id}>
      <div className={styles.statusRow}>
        <Text as="strong" variant="label">
          {askText.labels.taskInputRequired}
        </Text>
        <Badge tone={ask.status === "pending" ? "warning" : "neutral"}>
          {askText.statuses[ask.status]}
        </Badge>
      </div>
      <Text as="h3" variant="subheading">
        {ask.question}
      </Text>
      {ask.reason ? <Text variant="muted">{ask.reason}</Text> : null}
      <Button onClick={onViewInConversation} variant="secondary">
        {askText.actions.viewInConversation}
      </Button>
    </section>
  );
}
