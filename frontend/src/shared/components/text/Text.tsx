import type { ElementType, HTMLAttributes } from "react";

import { cx } from "../../utils/cx";
import styles from "./Text.module.css";

export type TextVariant =
  | "eyebrow"
  | "heading"
  | "subheading"
  | "body"
  | "muted"
  | "label";

export type TextProps = HTMLAttributes<HTMLElement> & {
  as?: ElementType;
  variant?: TextVariant;
};

export function Text({
  as: Component = "p",
  className,
  variant = "body",
  ...props
}: TextProps) {
  return <Component className={cx(styles[variant], className)} {...props} />;
}
