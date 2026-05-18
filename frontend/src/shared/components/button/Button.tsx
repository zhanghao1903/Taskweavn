import { Slot } from "@radix-ui/react-slot";
import type { ButtonHTMLAttributes, ElementType } from "react";

import { cx } from "../../utils/cx";
import styles from "./Button.module.css";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "icon";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  asChild?: boolean;
  size?: ButtonSize;
  variant?: ButtonVariant;
};

export function Button({
  asChild = false,
  className,
  size = "md",
  type = "button",
  variant = "secondary",
  ...props
}: ButtonProps) {
  const Component: ElementType = asChild ? Slot : "button";

  return (
    <Component
      className={cx(styles.button, styles[variant], styles[size], className)}
      type={asChild ? undefined : type}
      {...props}
    />
  );
}
