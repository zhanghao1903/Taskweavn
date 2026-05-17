import type { HTMLAttributes } from "react";

import { cx } from "../../utils/cx";
import styles from "./Badge.module.css";

export type BadgeTone =
  | "neutral"
  | "blue"
  | "success"
  | "warning"
  | "danger";

export type BadgeSize = "sm" | "md";

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  size?: BadgeSize;
  tone?: BadgeTone;
};

export function Badge({
  className,
  size = "md",
  tone = "neutral",
  ...props
}: BadgeProps) {
  return (
    <span
      className={cx(styles.badge, styles[tone], styles[size], className)}
      {...props}
    />
  );
}
