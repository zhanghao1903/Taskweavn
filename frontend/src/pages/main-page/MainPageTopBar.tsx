import type { ReactNode } from "react";

import type { BadgeTone } from "../../shared/components";
import { Badge } from "../../shared/components";
import styles from "./MainPage.module.css";

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
  return (
    <header className={styles.topBar}>
      <div className={styles.brand}>{brandLabel}</div>
      <div className={styles.contextStack}>
        {contextItems.map((item, index) => (
          <span key={`${item}-${index}`}>{item}</span>
        ))}
      </div>
      {statuses.map((status, index) => (
        <Badge key={`${status.label}-${index}`} tone={status.tone}>
          {status.label}
        </Badge>
      ))}
      {trailing}
    </header>
  );
}
