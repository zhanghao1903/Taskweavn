import type { ReactNode } from "react";

import type { BadgeTone } from "../../shared/components";
import { Badge } from "../../shared/components";
import { useUiText } from "../../shared/ui-text";
import styles from "./MainPage.module.css";
import { PlatoProductMark } from "./PlatoProductMark";

export type MainPageTopBarStatus = {
  label: string;
  tone: BadgeTone;
};

export type MainPageTopBarProps = {
  brandLabel: string;
  contextItems: string[];
  statuses: MainPageTopBarStatus[];
  trailing?: ReactNode;
};

export function MainPageTopBar({
  brandLabel,
  contextItems,
  statuses,
  trailing = null,
}: MainPageTopBarProps) {
  const uiText = useUiText();
  const [
    workspaceName = uiText.workspace.labels.workspace,
    maybeSessionName,
    legacySessionName,
  ] = contextItems;
  const sessionName = legacySessionName ?? maybeSessionName;

  return (
    <header aria-label={brandLabel} className={styles.topBar}>
      <div className={styles.brandBlock}>
        <PlatoProductMark className={styles.brandMark} />
        <div className={styles.brandCopy}>
          <div className={styles.brandName}>Plato</div>
        </div>
      </div>

      <div className={styles.topBarContextBlock}>
        <span className={styles.topBarLabel}>
          {uiText.workspace.labels.workspace}
        </span>
        <span className={styles.topBarValue}>{workspaceName}</span>
      </div>

      <div className={styles.sessionContextBlock}>
        <span className={styles.sessionValue}>
          {sessionName
            ? uiText.main.labels.sessionName({ name: sessionName })
            : uiText.main.labels.noSessionSelected}
        </span>
      </div>

      <div className={styles.statusCluster}>
        {statuses.map((status, index) => (
          <Badge
            className={styles.topBarStatusBadge}
            key={`${status.label}-${index}`}
            tone={status.tone}
          >
            {status.label}
          </Badge>
        ))}
      </div>

      <div className={styles.topBarActions}>
        {trailing ? (
          <div className={styles.topBarTrailing}>{trailing}</div>
        ) : null}
      </div>
    </header>
  );
}
