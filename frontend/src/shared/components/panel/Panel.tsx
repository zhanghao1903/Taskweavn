import type { ElementType, HTMLAttributes, ReactNode } from "react";

import { cx } from "../../utils/cx";
import styles from "./Panel.module.css";

export type PanelTone = "surface" | "muted";

export type PanelProps = HTMLAttributes<HTMLElement> & {
  actions?: ReactNode;
  as?: ElementType;
  icon?: ReactNode;
  title?: ReactNode;
  titleId?: string;
  tone?: PanelTone;
};

export function Panel({
  actions,
  as: Component = "section",
  children,
  className,
  icon,
  title,
  titleId,
  tone = "surface",
  ...props
}: PanelProps) {
  return (
    <Component
      aria-labelledby={titleId}
      className={cx(styles.panel, styles[tone], className)}
      {...props}
    >
      {(title || actions) && (
        <div className={styles.header}>
          <div className={styles.titleGroup}>
            {icon}
            {title && (
              <h2 className={styles.title} id={titleId}>
                {title}
              </h2>
            )}
          </div>
          {actions && <div className={styles.actions}>{actions}</div>}
        </div>
      )}
      {children}
    </Component>
  );
}
